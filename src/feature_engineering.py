from __future__ import annotations

import logging
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sqlalchemy import text

# Allow execution with:
#     python src/feature_engineering.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database import get_engine

logger = logging.getLogger(__name__)


OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_FILE = OUTPUT_DIR / "customer_features.csv"


def load_customer_base(engine) -> pd.DataFrame:
    """Create the main customer-level transactional feature table."""
    query = text(
        """
        WITH order_base AS (
            SELECT
                c.customer_unique_id,
                o.order_id,
                o.order_status,
                o.order_purchase_timestamp,
                o.order_delivered_customer_date,
                o.order_estimated_delivery_date
            FROM olist_customers c
            JOIN olist_orders o
                ON c.customer_id = o.customer_id
        ),
        item_agg AS (
            SELECT
                order_id,
                SUM(price) AS product_revenue,
                SUM(freight_value) AS freight_revenue,
                COUNT(*) AS item_count,
                COUNT(DISTINCT product_id) AS unique_products
            FROM olist_order_items
            GROUP BY order_id
        ),
        review_agg AS (
            SELECT
                order_id,
                AVG(review_score) AS average_review_score,
                COUNT(review_id) AS review_count,
                COUNT(*) FILTER (
                    WHERE review_score <= 2
                ) AS negative_review_count
            FROM olist_order_reviews
            GROUP BY order_id
        ),
        payment_agg AS (
            SELECT
                order_id,
                SUM(payment_value) AS payment_value,
                COUNT(*) AS payment_record_count,
                COUNT(DISTINCT payment_type) AS payment_type_count
            FROM olist_order_payments
            GROUP BY order_id
        )
        SELECT
            ob.customer_unique_id,
            ob.order_id,
            ob.order_status,
            ob.order_purchase_timestamp,
            ob.order_delivered_customer_date,
            ob.order_estimated_delivery_date,

            COALESCE(ia.product_revenue, 0) AS product_revenue,
            COALESCE(ia.freight_revenue, 0) AS freight_revenue,
            COALESCE(ia.item_count, 0) AS item_count,
            COALESCE(ia.unique_products, 0) AS unique_products,

            COALESCE(ra.average_review_score, 0) AS average_review_score,
            COALESCE(ra.review_count, 0) AS review_count,
            COALESCE(ra.negative_review_count, 0)
                AS negative_review_count,

            COALESCE(pa.payment_value, 0) AS payment_value,
            COALESCE(pa.payment_record_count, 0)
                AS payment_record_count,
            COALESCE(pa.payment_type_count, 0)
                AS payment_type_count

        FROM order_base ob
        LEFT JOIN item_agg ia
            ON ob.order_id = ia.order_id
        LEFT JOIN review_agg ra
            ON ob.order_id = ra.order_id
        LEFT JOIN payment_agg pa
            ON ob.order_id = pa.order_id
        """
    )

    with engine.connect() as connection:
        return pd.read_sql(query, connection)


def build_customer_features(order_level: pd.DataFrame) -> pd.DataFrame:
    """Aggregate order-level information into customer-level features."""
    df = order_level.copy()

    timestamp_columns = [
        "order_purchase_timestamp",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]

    for column in timestamp_columns:
        df[column] = pd.to_datetime(df[column], errors="coerce")

    numeric_columns = [
        "product_revenue",
        "freight_revenue",
        "item_count",
        "unique_products",
        "average_review_score",
        "review_count",
        "negative_review_count",
        "payment_value",
        "payment_record_count",
        "payment_type_count",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    # Order-level revenue.
    df["order_revenue"] = (
        df["product_revenue"] + df["freight_revenue"]
    )

    # The observation cutoff is the latest purchase in the available data.
    observation_date = df["order_purchase_timestamp"].max()

    if pd.isna(observation_date):
        raise ValueError(
            "No valid order_purchase_timestamp values were found."
        )

    # Customer-level transactional aggregation.
    customer = (
        df.groupby("customer_unique_id")
        .agg(
            order_count=("order_id", "nunique"),
            total_revenue=("order_revenue", "sum"),
            total_product_revenue=("product_revenue", "sum"),
            total_freight_revenue=("freight_revenue", "sum"),
            total_items=("item_count", "sum"),
            unique_products_purchased=("unique_products", "sum"),
            average_order_value=("order_revenue", "mean"),
            first_purchase_date=(
                "order_purchase_timestamp",
                "min",
            ),
            last_purchase_date=(
                "order_purchase_timestamp",
                "max",
            ),
            average_review_score=(
                "average_review_score",
                lambda x: x[x > 0].mean()
                if (x > 0).any()
                else np.nan,
            ),
            total_reviews=("review_count", "sum"),
            negative_review_count=("negative_review_count", "sum"),
            total_payment_value=("payment_value", "sum"),
            payment_record_count=(
                "payment_record_count",
                "sum",
            ),
            payment_type_count=("payment_type_count", "sum"),
        )
        .reset_index()
    )

    # Recency and customer lifetime.
    customer["recency_days"] = (
        observation_date - customer["last_purchase_date"]
    ).dt.total_seconds() / 86400.0

    customer["customer_age_days"] = (
        customer["last_purchase_date"]
        - customer["first_purchase_date"]
    ).dt.total_seconds() / 86400.0

    customer["customer_age_days"] = customer["customer_age_days"].clip(
        lower=0
    )

    # Frequency and monetary features.
    customer["average_items_per_order"] = (
        customer["total_items"]
        / customer["order_count"].replace(0, np.nan)
    )

    customer["average_freight_per_order"] = (
        customer["total_freight_revenue"]
        / customer["order_count"].replace(0, np.nan)
    )

    customer["revenue_per_item"] = (
        customer["total_product_revenue"]
        / customer["total_items"].replace(0, np.nan)
    )

    customer["orders_per_active_day"] = (
        customer["order_count"]
        / customer["customer_age_days"].replace(0, np.nan)
    )

    # Repeat-purchase indicator.
    customer["is_repeat_customer"] = (
        customer["order_count"] > 1
    ).astype(int)

    # Review quality features.
    customer["negative_review_rate"] = (
        customer["negative_review_count"]
        / customer["total_reviews"].replace(0, np.nan)
    )

    # Delivery behavior at order level, then customer level.
    delivered = df.dropna(
        subset=[
            "order_delivered_customer_date",
            "order_purchase_timestamp",
        ]
    ).copy()

    if not delivered.empty:
        delivered["delivery_days"] = (
            delivered["order_delivered_customer_date"]
            - delivered["order_purchase_timestamp"]
        ).dt.total_seconds() / 86400.0

        delivered["delivery_vs_estimate_days"] = (
            delivered["order_delivered_customer_date"]
            - delivered["order_estimated_delivery_date"]
        ).dt.total_seconds() / 86400.0

        delivery_customer = (
            delivered.groupby("customer_unique_id")
            .agg(
                average_delivery_days=("delivery_days", "mean"),
                median_delivery_days=("delivery_days", "median"),
                average_delivery_vs_estimate_days=(
                    "delivery_vs_estimate_days",
                    "mean",
                ),
                late_delivery_order_count=(
                    "delivery_vs_estimate_days",
                    lambda x: int((x > 0).sum()),
                ),
                delivered_order_count=("order_id", "nunique"),
            )
            .reset_index()
        )

        customer = customer.merge(
            delivery_customer,
            on="customer_unique_id",
            how="left",
        )

    # Customer spending quantile is useful for segmentation.
    # Rank-based percentile avoids hardcoding currency thresholds.
    customer["spend_percentile"] = (
        customer["total_revenue"]
        .rank(method="average", pct=True)
    )

    customer["recency_percentile"] = (
        customer["recency_days"]
        .rank(method="average", pct=True)
    )

    # Basic RFM-style score components.
    # Higher recency score means more recent activity.
    customer["recency_score"] = pd.qcut(
        customer["recency_days"].rank(method="first"),
        q=5,
        labels=False,
        duplicates="drop",
    )

    customer["frequency_score"] = pd.qcut(
        customer["order_count"].rank(method="first"),
        q=5,
        labels=False,
        duplicates="drop",
    )

    customer["monetary_score"] = pd.qcut(
        customer["total_revenue"].rank(method="first"),
        q=5,
        labels=False,
        duplicates="drop",
    )

    # Convert quintiles to intuitive 1–5 scores.
    customer["recency_score"] = 5 - customer["recency_score"]
    customer["frequency_score"] = customer["frequency_score"] + 1
    customer["monetary_score"] = customer["monetary_score"] + 1

    customer["rfm_score"] = (
        customer["recency_score"]
        + customer["frequency_score"]
        + customer["monetary_score"]
    )

    # Customer activity buckets for descriptive segmentation.
    customer["customer_segment"] = np.select(
        [
            (
                (customer["recency_score"] >= 4)
                & (customer["frequency_score"] >= 4)
                & (customer["monetary_score"] >= 4)
            ),
            (
                (customer["recency_score"] >= 4)
                & (customer["frequency_score"] >= 3)
            ),
            (
                (customer["recency_score"] <= 2)
                & (customer["monetary_score"] >= 4)
            ),
            (
                (customer["frequency_score"] >= 4)
                & (customer["monetary_score"] >= 4)
            ),
        ],
        [
            "Champions",
            "Loyal Active",
            "At Risk High Value",
            "High Value",
        ],
        default="Needs Attention",
    )

    # Replace mathematical NaNs from divisions with zero where the
    # feature is not meaningful for a customer with no denominator.
    ratio_columns = [
        "average_items_per_order",
        "average_freight_per_order",
        "revenue_per_item",
        "orders_per_active_day",
        "negative_review_rate",
    ]

    for column in ratio_columns:
        customer[column] = customer[column].replace(
            [np.inf, -np.inf],
            np.nan,
        )

    customer[ratio_columns] = customer[ratio_columns].fillna(0)

    customer["average_review_score"] = (
        customer["average_review_score"].fillna(0)
    )

    customer["average_delivery_days"] = (
        customer["average_delivery_days"].fillna(0)
    )

    customer["median_delivery_days"] = (
        customer["median_delivery_days"].fillna(0)
    )

    customer["average_delivery_vs_estimate_days"] = (
        customer["average_delivery_vs_estimate_days"].fillna(0)
    )

    customer["late_delivery_order_count"] = (
        customer["late_delivery_order_count"].fillna(0).astype(int)
    )

    customer["delivered_order_count"] = (
        customer["delivered_order_count"].fillna(0).astype(int)
    )

    # Sort by business value.
    customer = customer.sort_values(
        ["total_revenue", "order_count"],
        ascending=[False, False],
    ).reset_index(drop=True)

    return customer


def save_features(customer_features: pd.DataFrame) -> Path:
    """Save the customer feature table to the processed-data directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    customer_features.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    return OUTPUT_FILE


def main() -> None:
    """Run the complete customer feature-engineering pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    logger.info("Creating database engine...")
    engine = get_engine()

    logger.info("Loading order-level analytical data...")
    order_level = load_customer_base(engine)

    if order_level.empty:
        raise ValueError(
            "The analytical query returned zero rows. "
            "Verify that Olist data has been loaded into Supabase."
        )

    logger.info(
        "Order-level rows loaded: %s",
        f"{len(order_level):,}",
    )

    logger.info("Building customer-level features...")
    customer_features = build_customer_features(order_level)

    logger.info(
        "Customers represented: %s",
        f"{len(customer_features):,}",
    )

    output_path = save_features(customer_features)

    logger.info("Feature table saved to: %s", output_path)
    logger.info(
        "Feature count: %s",
        len(customer_features.columns),
    )

    print("\nCustomer feature engineering completed successfully.")
    print(f"Customers: {len(customer_features):,}")
    print(f"Features: {len(customer_features.columns):,}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
