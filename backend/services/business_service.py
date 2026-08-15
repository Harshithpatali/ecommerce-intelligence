"""
Business intelligence service for the E-Commerce Intelligence API.

Responsibilities:
- Load the customer retention/recommendation dataset produced by notebook 07.
- Provide portfolio-level business KPIs.
- Provide customer-level retention recommendations.
- Identify high-value inactive customers.
- Provide priority and action summaries.

This service intentionally uses deterministic analytical outputs.
It does not train models and does not generate free-form AI text.
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RETENTION_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "retention_recommendations.csv"
)

SEGMENTS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "customer_segments.csv"
)

CLV_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "customer_clv_predictions.csv"
)

EVALUATION_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "portfolio_evaluation_report.csv"
)


# ---------------------------------------------------------------------------
# SERVICE
# ---------------------------------------------------------------------------

class BusinessService:
    """Business intelligence and retention analytics service."""

    _retention: pd.DataFrame | None = None
    _segments: pd.DataFrame | None = None
    _clv: pd.DataFrame | None = None
    _evaluation: pd.DataFrame | None = None

    _lock = Lock()

    @classmethod
    def load(cls) -> None:
        """Load business datasets once."""
        if cls._retention is not None:
            return

        with cls._lock:
            if cls._retention is not None:
                return

            if not RETENTION_PATH.exists():
                raise FileNotFoundError(
                    f"Retention dataset not found: {RETENTION_PATH}. "
                    "Run notebook 07 first."
                )

            retention = pd.read_csv(
                RETENTION_PATH
            )

            required_columns = [
                "customer_unique_id",
                "predicted_future_revenue",
                "recency_days",
                "order_count",
                "retention_priority",
                "recommended_action",
                "recommendation_reason",
                "retention_strategy",
                "opportunity_score",
            ]

            missing = [
                column
                for column in required_columns
                if column not in retention.columns
            ]

            if missing:
                raise ValueError(
                    "Retention dataset is missing columns: "
                    + ", ".join(missing)
                )

            cls._retention = retention

            if SEGMENTS_PATH.exists():
                cls._segments = pd.read_csv(
                    SEGMENTS_PATH
                )

            if CLV_PATH.exists():
                cls._clv = pd.read_csv(
                    CLV_PATH
                )

            if EVALUATION_PATH.exists():
                cls._evaluation = pd.read_csv(
                    EVALUATION_PATH
                )

    @classmethod
    def portfolio_summary(cls) -> dict[str, Any]:
        """Return high-level portfolio KPIs."""
        cls.load()

        assert cls._retention is not None

        df = cls._retention

        predicted_value = pd.to_numeric(
            df["predicted_future_revenue"],
            errors="coerce",
        ).fillna(0)

        recency = pd.to_numeric(
            df["recency_days"],
            errors="coerce",
        ).fillna(0)

        return {
            "customer_count": int(
                df["customer_unique_id"].nunique()
            ),
            "predicted_future_revenue": float(
                predicted_value.sum()
            ),
            "average_predicted_customer_value": float(
                predicted_value.mean()
            ),
            "average_recency_days": float(
                recency.mean()
            ),
            "critical_retention_customers": int(
                (
                    df["retention_priority"]
                    == "Critical"
                ).sum()
            ),
            "high_retention_customers": int(
                (
                    df["retention_priority"]
                    == "High"
                ).sum()
            ),
            "medium_retention_customers": int(
                (
                    df["retention_priority"]
                    == "Medium"
                ).sum()
            ),
            "low_retention_customers": int(
                (
                    df["retention_priority"]
                    == "Low"
                ).sum()
            ),
        }

    @classmethod
    def retention_priority_summary(
        cls,
    ) -> list[dict[str, Any]]:
        """Return customer counts and value by retention priority."""
        cls.load()

        assert cls._retention is not None

        df = cls._retention.copy()

        summary = (
            df.groupby(
                "retention_priority",
                dropna=False,
            )
            .agg(
                customers=(
                    "customer_unique_id",
                    "nunique",
                ),
                predicted_future_revenue=(
                    "predicted_future_revenue",
                    "sum",
                ),
                average_predicted_value=(
                    "predicted_future_revenue",
                    "mean",
                ),
                average_recency_days=(
                    "recency_days",
                    "mean",
                ),
                average_opportunity_score=(
                    "opportunity_score",
                    "mean",
                ),
            )
            .reset_index()
        )

        priority_order = {
            "Critical": 0,
            "High": 1,
            "Medium": 2,
            "Low": 3,
        }

        summary["_order"] = (
            summary["retention_priority"]
            .map(priority_order)
            .fillna(99)
        )

        summary = (
            summary
            .sort_values("_order")
            .drop(columns="_order")
        )

        return summary.to_dict(
            orient="records"
        )

    @classmethod
    def action_summary(
        cls,
    ) -> list[dict[str, Any]]:
        """Return the number of customers assigned to each action."""
        cls.load()

        assert cls._retention is not None

        summary = (
            cls._retention
            .groupby(
                [
                    "retention_priority",
                    "recommended_action",
                ],
                dropna=False,
            )
            .agg(
                customers=(
                    "customer_unique_id",
                    "nunique",
                ),
                predicted_future_revenue=(
                    "predicted_future_revenue",
                    "sum",
                ),
            )
            .reset_index()
            .sort_values(
                [
                    "retention_priority",
                    "customers",
                ],
                ascending=[True, False],
            )
        )

        return summary.to_dict(
            orient="records"
        )

    @classmethod
    def get_customer_recommendation(
        cls,
        customer_id: str,
    ) -> dict[str, Any]:
        """Return retention recommendation for one customer."""
        cls.load()

        assert cls._retention is not None

        matches = cls._retention[
            cls._retention[
                "customer_unique_id"
            ].astype(str)
            == str(customer_id)
        ]

        if matches.empty:
            raise KeyError(
                f"Customer {customer_id} not found."
            )

        row = matches.iloc[0]

        result = {
            "customer_unique_id": str(
                row["customer_unique_id"]
            ),
            "predicted_future_revenue": float(
                row["predicted_future_revenue"]
            ),
            "recency_days": float(
                row["recency_days"]
            ),
            "order_count": float(
                row["order_count"]
            ),
            "retention_priority": str(
                row["retention_priority"]
            ),
            "recommended_action": str(
                row["recommended_action"]
            ),
            "recommendation_reason": str(
                row["recommendation_reason"]
            ),
            "retention_strategy": str(
                row["retention_strategy"]
            ),
            "opportunity_score": float(
                row["opportunity_score"]
            ),
        }

        optional_columns = [
            "customer_segment",
            "segment",
            "cluster_id",
            "average_review_score",
            "total_revenue",
        ]

        for column in optional_columns:
            if column in row.index and pd.notna(
                row[column]
            ):
                value = row[column]

                if isinstance(
                    value,
                    (int, float),
                ):
                    result[column] = float(value)
                else:
                    result[column] = str(value)

        return result

    @classmethod
    def high_value_inactive_customers(
        cls,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Return high-value customers with high historical recency.

        Thresholds are calculated from the current retention dataset using
        the 75th percentile for both predicted value and recency.
        """
        cls.load()

        assert cls._retention is not None

        if limit < 1 or limit > 500:
            raise ValueError(
                "limit must be between 1 and 500."
            )

        df = cls._retention.copy()

        value_cutoff = df[
            "predicted_future_revenue"
        ].quantile(0.75)

        recency_cutoff = df[
            "recency_days"
        ].quantile(0.75)

        opportunity = df[
            (
                df["predicted_future_revenue"]
                >= value_cutoff
            )
            & (
                df["recency_days"]
                >= recency_cutoff
            )
        ].copy()

        opportunity = opportunity.sort_values(
            "predicted_future_revenue",
            ascending=False,
        ).head(limit)

        columns = [
            "customer_unique_id",
            "predicted_future_revenue",
            "recency_days",
            "order_count",
            "retention_priority",
            "recommended_action",
            "recommendation_reason",
            "opportunity_score",
        ]

        return opportunity[columns].to_dict(
            orient="records"
        )

    @classmethod
    def segment_summary(
        cls,
    ) -> list[dict[str, Any]]:
        """Return business metrics by customer segment."""
        cls.load()

        if cls._segments is None:
            raise FileNotFoundError(
                f"Segment dataset not found: {SEGMENTS_PATH}"
            )

        df = cls._segments.copy()

        required = [
            "segment",
            "customer_unique_id",
            "total_revenue",
            "recency_days",
            "order_count",
        ]

        missing = [
            column
            for column in required
            if column not in df.columns
        ]

        if missing:
            raise ValueError(
                "Segment dataset is missing columns: "
                + ", ".join(missing)
            )

        summary = (
            df.groupby("segment", dropna=False)
            .agg(
                customers=(
                    "customer_unique_id",
                    "nunique",
                ),
                total_revenue=(
                    "total_revenue",
                    "sum",
                ),
                average_revenue=(
                    "total_revenue",
                    "mean",
                ),
                average_recency_days=(
                    "recency_days",
                    "mean",
                ),
                average_order_count=(
                    "order_count",
                    "mean",
                ),
            )
            .reset_index()
        )

        total_customers = summary[
            "customers"
        ].sum()

        total_revenue = summary[
            "total_revenue"
        ].sum()

        summary["customer_share_pct"] = (
            100
            * summary["customers"]
            / total_customers
            if total_customers
            else 0
        )

        summary["revenue_share_pct"] = (
            100
            * summary["total_revenue"]
            / total_revenue
            if total_revenue
            else 0
        )

        return summary.to_dict(
            orient="records"
        )

    @classmethod
    def evaluation_report(
        cls,
    ) -> list[dict[str, Any]]:
        """Return the saved portfolio evaluation report."""
        cls.load()

        if cls._evaluation is None:
            raise FileNotFoundError(
                f"Evaluation report not found: {EVALUATION_PATH}"
            )

        return cls._evaluation.to_dict(
            orient="records"
        )

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        """Return business-service artifact metadata."""
        cls.load()

        return {
            "retention_artifact": str(
                RETENTION_PATH.relative_to(
                    PROJECT_ROOT
                )
            ),
            "segments_available": (
                cls._segments is not None
            ),
            "clv_available": (
                cls._clv is not None
            ),
            "evaluation_available": (
                cls._evaluation is not None
            ),
        }


# ---------------------------------------------------------------------------
# CONVENIENCE FUNCTIONS
# ---------------------------------------------------------------------------

def get_portfolio_summary() -> dict[str, Any]:
    """Return portfolio KPIs."""
    return BusinessService.portfolio_summary()


def get_customer_recommendation(
    customer_id: str,
) -> dict[str, Any]:
    """Return one customer's retention recommendation."""
    return BusinessService.get_customer_recommendation(
        customer_id
    )
