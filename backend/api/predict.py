"""
FastAPI prediction endpoints.

Endpoints:
    POST /api/v1/predict
    POST /api/v1/predict/batch

The endpoint layer is intentionally thin. ML inference is delegated to
PredictionService in backend/services/prediction_service.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.services.prediction_service import PredictionService


router = APIRouter()


# ---------------------------------------------------------------------------
# REQUEST / RESPONSE SCHEMAS
# ---------------------------------------------------------------------------

class CustomerPredictionRequest(BaseModel):
    """
    Feature payload for one customer.

    The fields mirror the exact feature set used by the trained CLV model.
    Extra fields are rejected so that accidental feature-name mistakes do not
    silently pass through the API.
    """

    model_config = ConfigDict(extra="forbid")

    historical_recency_days: float = Field(
        ...,
        ge=0,
        description="Days since the customer's most recent historical purchase.",
    )

    historical_order_count: float = Field(
        ...,
        ge=0,
        description="Number of historical orders in the observation period.",
    )

    historical_revenue: float = Field(
        ...,
        ge=0,
        description="Historical customer revenue.",
    )

    historical_item_count: float = Field(
        ...,
        ge=0,
        description="Number of purchased items in the observation period.",
    )

    historical_unique_products: float = Field(
        ...,
        ge=0,
        description="Number of unique products purchased historically.",
    )

    historical_average_order_value: float = Field(
        ...,
        ge=0,
        description="Historical average order value.",
    )

    historical_average_items_per_order: float = Field(
        ...,
        ge=0,
        description="Historical average number of items per order.",
    )

    historical_orders_per_active_day: float = Field(
        ...,
        ge=0,
        description="Historical order frequency normalized by active customer days.",
    )


class CustomerPredictionResponse(BaseModel):
    """Single-customer prediction response."""

    customer_id: str | None = Field(
        default=None,
        description="Optional client-side customer identifier.",
    )

    predicted_future_revenue: float = Field(
        ...,
        ge=0,
        description="Predicted future customer revenue.",
    )

    model_target: str = Field(
        default="future_revenue",
    )


class BatchPredictionRequest(BaseModel):
    """
    Batch prediction payload.

    Each dictionary must contain the same eight model features required by
    CustomerPredictionRequest. An optional customer_id can be included for
    client-side tracking.
    """

    model_config = ConfigDict(extra="forbid")

    customers: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Customer feature records to score.",
    )


class BatchPredictionResponse(BaseModel):
    """Batch prediction response."""

    rows_processed: int
    predictions: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

MODEL_FEATURES = [
    "historical_recency_days",
    "historical_order_count",
    "historical_revenue",
    "historical_item_count",
    "historical_unique_products",
    "historical_average_order_value",
    "historical_average_items_per_order",
    "historical_orders_per_active_day",
]


def _prediction_features(
    request: CustomerPredictionRequest,
) -> dict[str, float]:
    """Convert the validated Pydantic request into model features."""
    values = request.model_dump()

    return {
        feature: float(values[feature])
        for feature in MODEL_FEATURES
    }


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=CustomerPredictionResponse,
    summary="Predict future customer revenue",
)
def predict_customer(
    request: CustomerPredictionRequest,
) -> CustomerPredictionResponse:
    """
    Predict future revenue for one customer.

    The endpoint accepts historical behavioral features and returns the
    model's predicted future revenue.
    """
    try:
        prediction = PredictionService.predict_one(
            _prediction_features(request)
        )

        return CustomerPredictionResponse(
            predicted_future_revenue=prediction,
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Prediction service failed.",
        ) from exc


@router.post(
    "/batch",
    response_model=BatchPredictionResponse,
    summary="Predict future revenue for multiple customers",
)
def predict_batch(
    request: BatchPredictionRequest,
) -> BatchPredictionResponse:
    """
    Score multiple customer records in one request.

    This endpoint is intended for application-level batch requests.
    A later CSV upload endpoint can reuse the same service method.
    """
    import pandas as pd

    records = request.customers

    validated_records = []

    for index, record in enumerate(records):
        customer_id = record.get("customer_id")

        missing = [
            feature
            for feature in MODEL_FEATURES
            if feature not in record
        ]

        if missing:
            raise HTTPException(
                status_code=422,
                detail={
                    "row": index,
                    "message": "Missing required model features.",
                    "missing_features": missing,
                },
            )

        try:
            feature_values = {
                feature: float(record[feature])
                for feature in MODEL_FEATURES
            }
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "row": index,
                    "message": "Model features must be numeric.",
                },
            ) from exc

        validated_records.append({
            "customer_id": customer_id,
            **feature_values,
        })

    feature_frame = pd.DataFrame(
        [
            {
                feature: record[feature]
                for feature in MODEL_FEATURES
            }
            for record in validated_records
        ]
    )

    try:
        predictions = PredictionService.predict_batch(
            feature_frame
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Batch prediction service failed.",
        ) from exc

    output = []

    for record, prediction in zip(
        validated_records,
        predictions,
    ):
        output.append({
            "customer_id": record.get("customer_id"),
            "predicted_future_revenue": float(prediction),
        })

    return BatchPredictionResponse(
        rows_processed=len(output),
        predictions=output,
    )


@router.get(
    "/model-info",
    summary="Get CLV model metadata",
)
def model_info() -> dict[str, Any]:
    """
    Return non-sensitive metadata about the loaded prediction model.

    This is useful for debugging and deployment verification.
    """
    try:
        return PredictionService.get_model_metadata()

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to load model metadata.",
        ) from exc
