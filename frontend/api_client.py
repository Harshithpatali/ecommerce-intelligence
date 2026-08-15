"""
FastAPI client used by the Streamlit frontend.

The Streamlit application communicates with the FastAPI backend only through
this module. This keeps HTTP handling out of individual dashboard pages.

Production configuration:
    BACKEND_URL must be configured in Streamlit Cloud Secrets.

Example Streamlit Secret:

    BACKEND_URL = "https://ecommerce-intelligence-xod0.onrender.com"
"""

from __future__ import annotations

from typing import Any

import requests
import streamlit as st


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

def get_backend_url() -> str:
    """
    Get the production FastAPI backend URL from Streamlit Secrets.

    BACKEND_URL must be configured in Streamlit Cloud.
    """

    try:
        backend_url = st.secrets["BACKEND_URL"]
    except Exception as exc:
        raise RuntimeError(
            "BACKEND_URL is not configured in Streamlit Secrets. "
            "Please add BACKEND_URL to the Streamlit app secrets."
        ) from exc

    backend_url = str(backend_url).strip().rstrip("/")

    if not backend_url:
        raise RuntimeError(
            "BACKEND_URL is empty. "
            "Please configure a valid FastAPI backend URL."
        )

    return backend_url


BACKEND_URL = get_backend_url()

DEFAULT_TIMEOUT = 30


# ---------------------------------------------------------------------------
# EXCEPTIONS
# ---------------------------------------------------------------------------

class APIClientError(RuntimeError):
    """Raised when the FastAPI backend cannot satisfy a request."""


# ---------------------------------------------------------------------------
# CLIENT
# ---------------------------------------------------------------------------

class APIClient:
    """Small, reusable HTTP client for the Streamlit frontend."""

    def __init__(
        self,
        base_url: str = BACKEND_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # -----------------------------------------------------------------------
    # INTERNAL REQUEST
    # -----------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Execute an HTTP request and normalize backend failures.
        """

        url = f"{self.base_url}{path}"

        try:
            response = requests.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs,
            )

        except requests.Timeout as exc:
            raise APIClientError(
                f"Backend request timed out after "
                f"{self.timeout} seconds: {url}"
            ) from exc

        except requests.ConnectionError as exc:
            raise APIClientError(
                f"Unable to connect to backend: {url}"
            ) from exc

        except requests.RequestException as exc:
            raise APIClientError(
                f"Backend request failed: {exc}"
            ) from exc

        # -------------------------------------------------------------------
        # HTTP ERROR HANDLING
        # -------------------------------------------------------------------

        if not response.ok:

            try:
                error_data = response.json()

                if isinstance(error_data, dict):
                    detail = error_data.get(
                        "detail",
                        response.text,
                    )
                else:
                    detail = response.text

            except ValueError:
                detail = response.text

            raise APIClientError(
                f"Backend returned HTTP {response.status_code}: "
                f"{detail}"
            )

        return response

    # -----------------------------------------------------------------------
    # GET
    # -----------------------------------------------------------------------

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """
        Send a GET request and return JSON.
        """

        response = self._request(
            "GET",
            path,
            params=params,
        )

        try:
            return response.json()

        except ValueError as exc:
            raise APIClientError(
                "Backend returned an invalid JSON response."
            ) from exc

    # -----------------------------------------------------------------------
    # POST
    # -----------------------------------------------------------------------

    def post(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        """
        Send a POST request and return JSON.
        """

        response = self._request(
            "POST",
            path,
            json=payload,
        )

        try:
            return response.json()

        except ValueError as exc:
            raise APIClientError(
                "Backend returned an invalid JSON response."
            ) from exc

    # -----------------------------------------------------------------------
    # HEALTH
    # -----------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Return backend health information."""

        return self.get("/health")

    def artifact_health(self) -> dict[str, Any]:
        """Return analytical artifact availability."""

        return self.get("/health/artifacts")

    # -----------------------------------------------------------------------
    # PREDICTION
    # -----------------------------------------------------------------------

    def predict_customer(
        self,
        features: dict[str, Any],
    ) -> dict[str, Any]:
        """Predict future customer lifetime value."""

        return self.post(
            "/api/v1/predict",
            features,
        )

    def predict_batch(
        self,
        customers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Predict CLV for multiple customers."""

        return self.post(
            "/api/v1/predict/batch",
            {"customers": customers},
        )

    def model_info(self) -> dict[str, Any]:
        """Return CLV model metadata."""

        return self.get(
            "/api/v1/predict/model-info"
        )

    # -----------------------------------------------------------------------
    # SHAP EXPLAINABILITY
    # -----------------------------------------------------------------------

    def explain_customer(
        self,
        features: dict[str, Any],
        top_n: int = 5,
    ) -> dict[str, Any]:
        """Return customer-level SHAP explanation."""

        payload = {
            **features,
            "top_n": top_n,
        }

        return self.post(
            "/api/v1/explain",
            payload,
        )

    def global_shap(
        self,
        top_n: int = 10,
    ) -> list[dict[str, Any]]:
        """Return global SHAP feature importance."""

        return self.get(
            "/api/v1/explain/global",
            params={"top_n": top_n},
        )

    # -----------------------------------------------------------------------
    # RECOMMENDATIONS
    # -----------------------------------------------------------------------

    def recommendations(
        self,
        customer_id: str,
        k: int = 10,
    ) -> dict[str, Any]:
        """Return personalized product recommendations."""

        return self.get(
            f"/api/v1/recommendations/{customer_id}",
            params={"k": k},
        )

    def saved_recommendations(
        self,
        customer_id: str,
        k: int = 10,
    ) -> dict[str, Any]:
        """Return precomputed product recommendations."""

        return self.get(
            f"/api/v1/recommendations/{customer_id}/saved",
            params={"k": k},
        )

    def customer_history(
        self,
        customer_id: str,
    ) -> dict[str, Any]:
        """Return customer purchase history."""

        return self.get(
            f"/api/v1/recommendations/{customer_id}/history"
        )

    def recommendation_metadata(
        self,
    ) -> dict[str, Any]:
        """Return recommendation-system metadata."""

        return self.get(
            "/api/v1/recommendations/metadata"
        )

    # -----------------------------------------------------------------------
    # BUSINESS INTELLIGENCE
    # -----------------------------------------------------------------------

    def business_summary(
        self,
    ) -> dict[str, Any]:
        """Return portfolio KPIs."""

        return self.get(
            "/api/v1/business/summary"
        )

    def retention_priorities(
        self,
    ) -> list[dict[str, Any]]:
        """Return retention-priority summary."""

        return self.get(
            "/api/v1/business/retention-priorities"
        )

    def retention_actions(
        self,
    ) -> list[dict[str, Any]]:
        """Return recommended retention actions."""

        return self.get(
            "/api/v1/business/actions"
        )

    def customer_business_intelligence(
        self,
        customer_id: str,
    ) -> dict[str, Any]:
        """Return retention intelligence for one customer."""

        return self.get(
            f"/api/v1/business/customer/{customer_id}"
        )

    def high_value_inactive(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return high-value inactive customers."""

        return self.get(
            "/api/v1/business/high-value-inactive",
            params={"limit": limit},
        )

    def segment_summary(
        self,
    ) -> list[dict[str, Any]]:
        """Return customer segment metrics."""

        return self.get(
            "/api/v1/business/segments"
        )

    def evaluation_report(
        self,
    ) -> list[dict[str, Any]]:
        """Return end-to-end model evaluation results."""

        return self.get(
            "/api/v1/business/evaluation"
        )

    def business_metadata(
        self,
    ) -> dict[str, Any]:
        """Return business-service metadata."""

        return self.get(
            "/api/v1/business/metadata"
        )

    # -----------------------------------------------------------------------
    # AI INSIGHTS
    # -----------------------------------------------------------------------

    def ai_status(
        self,
    ) -> dict[str, Any]:
        """Return Groq AI service status."""

        return self.get(
            "/api/v1/ai-insights/status"
        )

    def ai_portfolio_report(
        self,
    ) -> dict[str, Any]:
        """Generate an executive portfolio AI report."""

        return self.get(
            "/api/v1/ai-insights/report"
        )

    def ai_customer_insight(
        self,
        customer_id: str,
    ) -> dict[str, Any]:
        """Generate a customer-level AI insight."""

        return self.get(
            f"/api/v1/ai-insights/customer/{customer_id}"
        )


# ---------------------------------------------------------------------------
# SHARED CLIENT
# ---------------------------------------------------------------------------

api_client = APIClient()