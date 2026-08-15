"""
FastAPI Business Intelligence endpoints.

Endpoints:
    GET /api/v1/business/summary
    GET /api/v1/business/retention-priorities
    GET /api/v1/business/actions
    GET /api/v1/business/customer/{customer_id}
    GET /api/v1/business/high-value-inactive
    GET /api/v1/business/segments
    GET /api/v1/business/evaluation
    GET /api/v1/business/metadata

The endpoint layer delegates analytical logic to BusinessService.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.business_service import BusinessService


router = APIRouter()


# ---------------------------------------------------------------------------
# RESPONSE SCHEMAS
# ---------------------------------------------------------------------------

class PortfolioSummaryResponse(BaseModel):
    """High-level portfolio KPIs."""

    customer_count: int
    predicted_future_revenue: float
    average_predicted_customer_value: float
    average_recency_days: float
    critical_retention_customers: int
    high_retention_customers: int
    medium_retention_customers: int
    low_retention_customers: int


class CustomerRecommendationResponse(BaseModel):
    """Retention recommendation for one customer."""

    customer_unique_id: str
    predicted_future_revenue: float
    recency_days: float
    order_count: float
    retention_priority: str
    recommended_action: str
    recommendation_reason: str
    retention_strategy: str
    opportunity_score: float

    # Optional fields are intentionally supported because different
    # analytical notebooks may include additional customer descriptors.
    customer_segment: str | None = None
    segment: str | None = None
    cluster_id: float | None = None
    average_review_score: float | None = None
    total_revenue: float | None = None


class HighValueInactiveResponse(BaseModel):
    """High-value inactive customer."""

    customer_unique_id: str
    predicted_future_revenue: float
    recency_days: float
    order_count: float
    retention_priority: str
    recommended_action: str
    recommendation_reason: str
    opportunity_score: float


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _handle_service_error(
    exc: Exception,
) -> HTTPException:
    """Translate service-layer errors into API responses."""
    if isinstance(exc, FileNotFoundError):
        return HTTPException(
            status_code=503,
            detail=str(exc),
        )

    if isinstance(exc, (ValueError, KeyError)):
        return HTTPException(
            status_code=422,
            detail=str(exc),
        )

    return HTTPException(
        status_code=500,
        detail="Business intelligence service failed.",
    )


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@router.get(
    "/summary",
    response_model=PortfolioSummaryResponse,
    summary="Get portfolio business KPIs",
)
def portfolio_summary() -> PortfolioSummaryResponse:
    """Return high-level customer and retention KPIs."""
    try:
        return PortfolioSummaryResponse(
            **BusinessService.portfolio_summary()
        )

    except Exception as exc:
        raise _handle_service_error(exc) from exc


@router.get(
    "/retention-priorities",
    summary="Get retention priority summary",
)
def retention_priority_summary() -> list[dict[str, Any]]:
    """
    Return customer counts and predicted value by retention priority.
    """
    try:
        return BusinessService.retention_priority_summary()

    except Exception as exc:
        raise _handle_service_error(exc) from exc


@router.get(
    "/actions",
    summary="Get recommended retention actions",
)
def action_summary() -> list[dict[str, Any]]:
    """
    Return recommended actions grouped by retention priority.
    """
    try:
        return BusinessService.action_summary()

    except Exception as exc:
        raise _handle_service_error(exc) from exc


@router.get(
    "/customer/{customer_id}",
    response_model=CustomerRecommendationResponse,
    summary="Get customer retention intelligence",
)
def customer_business_intelligence(
    customer_id: str,
) -> CustomerRecommendationResponse:
    """
    Return the business recommendation and retention context for one
    customer.
    """
    try:
        result = BusinessService.get_customer_recommendation(
            customer_id=customer_id,
        )

        return CustomerRecommendationResponse(
            **result
        )

    except Exception as exc:
        raise _handle_service_error(exc) from exc


@router.get(
    "/high-value-inactive",
    response_model=list[HighValueInactiveResponse],
    summary="Get high-value inactive customers",
)
def high_value_inactive(
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of customers to return.",
    ),
) -> list[HighValueInactiveResponse]:
    """
    Identify high-value customers with high recency.

    The service uses the 75th percentile of predicted future revenue and
    recency as deterministic opportunity thresholds.
    """
    try:
        result = BusinessService.high_value_inactive_customers(
            limit=limit,
        )

        return [
            HighValueInactiveResponse(**row)
            for row in result
        ]

    except Exception as exc:
        raise _handle_service_error(exc) from exc


@router.get(
    "/segments",
    summary="Get customer segment business summary",
)
def segment_summary() -> list[dict[str, Any]]:
    """Return revenue and behavioral metrics by customer segment."""
    try:
        return BusinessService.segment_summary()

    except Exception as exc:
        raise _handle_service_error(exc) from exc


@router.get(
    "/evaluation",
    summary="Get portfolio model evaluation report",
)
def evaluation_report() -> list[dict[str, Any]]:
    """Return the saved end-to-end evaluation report."""
    try:
        return BusinessService.evaluation_report()

    except Exception as exc:
        raise _handle_service_error(exc) from exc


@router.get(
    "/metadata",
    summary="Get business service metadata",
)
def business_metadata() -> dict[str, Any]:
    """Return non-sensitive metadata about business artifacts."""
    try:
        return BusinessService.metadata()

    except Exception as exc:
        raise _handle_service_error(exc) from exc
