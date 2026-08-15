"""
FastAPI SHAP explainability endpoints.

Endpoints:
    POST /api/v1/explain
    GET  /api/v1/explain/global

The endpoint layer delegates all SHAP computation to SHAPService.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.services.shap_service import SHAPService


router = APIRouter()


# ---------------------------------------------------------------------------
# CONSTANTS
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


# ---------------------------------------------------------------------------
# SCHEMAS
# ---------------------------------------------------------------------------

class SHAPExplanationRequest(BaseModel):
    """Validated feature payload for one customer explanation."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = Field(
        default=None,
        description="Optional customer identifier.",
    )

    historical_recency_days: float = Field(
        ...,
        ge=0,
    )

    historical_order_count: float = Field(
        ...,
        ge=0,
    )

    historical_revenue: float = Field(
        ...,
        ge=0,
    )

    historical_item_count: float = Field(
        ...,
        ge=0,
    )

    historical_unique_products: float = Field(
        ...,
        ge=0,
    )

    historical_average_order_value: float = Field(
        ...,
        ge=0,
    )

    historical_average_items_per_order: float = Field(
        ...,
        ge=0,
    )

    historical_orders_per_active_day: float = Field(
        ...,
        ge=0,
    )

    top_n: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of strongest positive and negative drivers.",
    )


class SHAPFactor(BaseModel):
    """One SHAP feature contribution."""

    feature: str
    feature_value: float
    shap_value: float


class SHAPExplanationResponse(BaseModel):
    """Customer-level SHAP explanation."""

    customer_id: str | None = None
    base_value: float
    model_output: float
    top_positive_factors: list[SHAPFactor]
    top_negative_factors: list[SHAPFactor]
    all_factors: list[SHAPFactor]
    interpretation_note: str


class GlobalSHAPItem(BaseModel):
    """Global SHAP feature importance item."""

    feature: str
    mean_abs_shap: float


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _build_feature_dict(
    request: SHAPExplanationRequest,
) -> dict[str, float]:
    """Extract only the model features from the API request."""
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
    response_model=SHAPExplanationResponse,
    summary="Explain a customer CLV prediction",
)
def explain_customer(
    request: SHAPExplanationRequest,
) -> SHAPExplanationResponse:
    """
    Explain the model behavior for one customer's feature vector.

    Positive SHAP values push the underlying model output upward.
    Negative SHAP values push the underlying model output downward.
    """
    try:
        explanation = SHAPService.explain(
            features=_build_feature_dict(request),
            top_n=request.top_n,
        )

        return SHAPExplanationResponse(
            customer_id=request.customer_id,
            **explanation,
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
            detail="SHAP explanation service failed.",
        ) from exc


@router.get(
    "/global",
    response_model=list[GlobalSHAPItem],
    summary="Get global SHAP feature importance",
)
def global_shap_importance(
    top_n: int = 10,
) -> list[GlobalSHAPItem]:
    """
    Return the most influential model features across customers.
    """
    if top_n < 1 or top_n > 50:
        raise HTTPException(
            status_code=422,
            detail="top_n must be between 1 and 50.",
        )

    try:
        importance = SHAPService.global_importance(
            top_n=top_n,
        )

        return [
            GlobalSHAPItem(**item)
            for item in importance
        ]

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
            detail="Unable to retrieve SHAP importance.",
        ) from exc
