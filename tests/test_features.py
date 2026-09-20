import numpy as np
import pandas as pd
import pytest

from src.feature_engineering import build_customer_features


def make_order_data():
    return pd.DataFrame({
        "customer_unique_id": ["c1", "c1", "c2"],
        "order_id": ["o1", "o2", "o3"],
        "order_status": ["delivered"] * 3,
        "order_purchase_timestamp": ["2024-01-01", "2024-01-11", "2024-01-21"],
        "order_delivered_customer_date": ["2024-01-03", "2024-01-14", "2024-01-23"],
        "order_estimated_delivery_date": ["2024-01-04", "2024-01-15", "2024-01-24"],
        "product_revenue": [100.0, 50.0, 25.0],
        "freight_revenue": [10.0, 5.0, 2.0],
        "item_count": [2, 1, 1],
        "unique_products": [2, 1, 1],
        "average_review_score": [5.0, 4.0, 3.0],
        "review_count": [1, 1, 1],
        "negative_review_count": [0, 0, 1],
        "payment_value": [110.0, 55.0, 27.0],
        "payment_record_count": [1, 1, 1],
        "payment_type_count": [1, 1, 1],
    })


def test_customer_feature_aggregation():
    result = build_customer_features(make_order_data())
    assert len(result) == 2
    c1 = result.loc[result["customer_unique_id"] == "c1"].iloc[0]
    assert c1["order_count"] == 2
    assert c1["total_revenue"] == pytest.approx(165.0)
    assert c1["total_items"] == 3
    assert c1["is_repeat_customer"] == 1
    assert c1["rfm_score"] >= 3


def test_customer_features_are_finite():
    result = build_customer_features(make_order_data())
    numeric = result.select_dtypes(include=np.number)
    assert np.isfinite(numeric.to_numpy()).all()


def test_missing_purchase_dates_fail_fast():
    data = make_order_data()
    data["order_purchase_timestamp"] = None
    with pytest.raises(ValueError, match="No valid order_purchase_timestamp"):
        build_customer_features(data)
