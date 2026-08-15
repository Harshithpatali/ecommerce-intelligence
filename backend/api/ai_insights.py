"""
FastAPI AI Insights endpoints.

Endpoints:
    GET /api/v1/ai-insights/status
    GET /api/v1/ai-insights/report
    GET /api/v1/ai-insights/customer/{customer_id}

The endpoint layer delegates all LLM work to GroqAIService.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


from backend.services.groq_service import GroqAIService


router = APIRouter()


# ---------------------------------------------------------------------------
# RESPONSE SCHEMAS
# ---------------------------------------------------------------------------

class AIStatusResponse(BaseModel):
    """Non-secret AI service status."""

    provider: str
    api_key_configured: bool
    model: str
    retention_data_available: bool
    segments_data_available: bool
    clv_data_available: bool
    shap_global_data_available: bool


class PortfolioAIResponse(BaseModel):
    """Executive portfolio AI report."""

    model: str | None
    report: str
    context_metrics: dict[str, Any]


class CustomerAIResponse(BaseModel):
    """Customer-level AI insight."""

    customer_id: str
    model: str | None
    report: str
    trusted_context: dict[str, Any]


# ---------------------------------------------------------------------------
# ERROR HANDLING
# ---------------------------------------------------------------------------

def _service_error(exc: Exception) -> HTTPException:
    """Translate AI service errors into appropriate HTTP responses."""
    if isinstance(exc, FileNotFoundError):
        return HTTPException(
            status_code=503,
            detail=str(exc),
        )

    if isinstance(exc, KeyError):
        return HTTPException(
            status_code=404,
            detail=str(exc),
        )

    if isinstance(exc, (ValueError, TypeError)):
        return HTTPException(
            status_code=422,
            detail=str(exc),
        )

    if isinstance(exc, RuntimeError):
        # RuntimeError is used by the service for missing Groq configuration,
        # missing package, and invalid provider responses.
        return HTTPException(
            status_code=503,
            detail=str(exc),
        )

    return HTTPException(
        status_code=500,
        detail="AI insights service failed.",
    )


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@router.get(
    "/status",
    response_model=AIStatusResponse,
    summary="Get AI service status",
)
def ai_status() -> AIStatusResponse:
    """
    Return non-secret configuration and artifact status.

    The Groq API key value is never returned.
    """
    try:
        return AIStatusResponse(
            **GroqAIService.status()
        )

    except Exception as exc:
        raise _service_error(exc) from exc


@router.get(
    "/report",
    response_model=PortfolioAIResponse,
    summary="Generate executive AI business insights",
)
def portfolio_ai_report() -> PortfolioAIResponse:
    """
    Generate an executive-level business report using trusted analytics.

    The LLM is used only as an interpretation layer. Numerical metrics come
    from the project's analytical artifacts.
    """
    try:
        result = (
            GroqAIService.portfolio_insights()
        )

        return PortfolioAIResponse(
            **result
        )

    except Exception as exc:
        raise _service_error(exc) from exc


@router.get(
    "/customer/{customer_id}",
    response_model=CustomerAIResponse,
    summary="Generate customer-level AI retention insight",
)
def customer_ai_insight(
    customer_id: str,
) -> CustomerAIResponse:
    """
    Generate a concise AI retention insight for one customer.

    The service receives only trusted customer-level analytical context.
    """
    try:
        result = (
            GroqAIService.customer_insight(
                customer_id=customer_id,
            )
        )

        return CustomerAIResponse(
            **result
        )

    except Exception as exc:
        raise _service_error(exc) from exc
