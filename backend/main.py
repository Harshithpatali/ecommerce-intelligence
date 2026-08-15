"""
FastAPI application entry point for the E-Commerce Intelligence Platform.

This module contains application wiring only. Business and ML logic belongs
in backend/services/ and backend/api/.

Registered API groups:
    /api/v1/predict
    /api/v1/explain
    /api/v1/recommendations
    /api/v1/business
    /api/v1/ai-insights
    /api/v1/predict-file
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from importlib import import_module
from pathlib import Path
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# ---------------------------------------------------------------------------
# PROJECT PATHS
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = PROJECT_ROOT / "models"


# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("ecommerce-intelligence")


# ---------------------------------------------------------------------------
# APPLICATION LIFECYCLE
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup/shutdown lifecycle.

    Directory checks are performed here. Model loading remains in service
    classes so startup does not unnecessarily load every ML artifact.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(
        "E-Commerce Intelligence API starting"
    )
    logger.info(
        "Project root: %s",
        PROJECT_ROOT,
    )

    yield

    logger.info(
        "E-Commerce Intelligence API shutting down"
    )


# ---------------------------------------------------------------------------
# APPLICATION
# ---------------------------------------------------------------------------

app = FastAPI(
    title="E-Commerce Customer & Product Intelligence API",
    description=(
        "Production-oriented REST API for customer segmentation, "
        "future customer value prediction, SHAP explainability, "
        "product recommendations, retention intelligence, and "
        "Groq-powered AI business insights."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8501",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# CORE SYSTEM ROUTES
# ---------------------------------------------------------------------------

@app.get(
    "/",
    tags=["System"],
    summary="API information",
)
def root():
    """Return basic API information."""
    return {
        "name": (
            "E-Commerce Customer & Product "
            "Intelligence API"
        ),
        "version": app.version,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
)
def health_check():
    """Return basic API process and directory health."""
    return {
        "status": "healthy",
        "api": True,
        "project_root_exists": PROJECT_ROOT.exists(),
        "processed_data_directory_exists": (
            PROCESSED_DIR.exists()
        ),
        "model_directory_exists": (
            MODEL_DIR.exists()
        ),
    }


@app.get(
    "/health/artifacts",
    tags=["System"],
    summary="Analytical artifact status",
)
def artifact_health():
    """
    Report whether the principal analytical artifacts exist.

    This endpoint does not load models or perform inference.
    """
    expected_artifacts = {
        "customer_features": (
            PROCESSED_DIR
            / "customer_features.csv"
        ),
        "customer_segments": (
            PROCESSED_DIR
            / "customer_segments.csv"
        ),
        "clv_model": (
            MODEL_DIR
            / "clv_xgboost.joblib"
        ),
        "clv_predictions": (
            PROCESSED_DIR
            / "customer_clv_predictions.csv"
        ),
        "shap_values": (
            PROCESSED_DIR
            / "customer_shap_values.csv"
        ),
        "retention_recommendations": (
            PROCESSED_DIR
            / "retention_recommendations.csv"
        ),
        "recommendation_artifact": (
            MODEL_DIR
            / "recommendation_artifact.joblib"
        ),
        "portfolio_evaluation": (
            PROCESSED_DIR
            / "portfolio_evaluation_report.csv"
        ),
    }

    artifacts = {}

    for name, path in expected_artifacts.items():
        try:
            relative_path = str(
                path.relative_to(PROJECT_ROOT)
            )
        except ValueError:
            relative_path = str(path)

        artifacts[name] = {
            "exists": path.exists(),
            "path": relative_path,
        }

    available_count = sum(
        item["exists"]
        for item in artifacts.values()
    )

    expected_count = len(artifacts)

    return {
        "status": (
            "ready"
            if available_count == expected_count
            else "partial"
        ),
        "available_artifacts": available_count,
        "expected_artifacts": expected_count,
        "artifacts": artifacts,
    }


# ---------------------------------------------------------------------------
# ROUTER REGISTRATION
# ---------------------------------------------------------------------------

def register_routers() -> None:
    """
    Register all API routers.

    Every router is loaded explicitly so that missing application modules
    are visible during development instead of being silently ignored.

    The batch CSV endpoint intentionally uses a different prefix:
        /api/v1/predict-file

    This avoids a path collision with the JSON prediction router's
        /api/v1/predict/{...}
    structure.
    """
    router_configs = [
        (
            "backend.api.predict",
            "/api/v1/predict",
            ["Prediction"],
        ),
        (
            "backend.api.explain",
            "/api/v1/explain",
            ["Explainability"],
        ),
        (
            "backend.api.recommendations",
            "/api/v1/recommendations",
            ["Recommendations"],
        ),
        (
            "backend.api.business",
            "/api/v1/business",
            ["Business Intelligence"],
        ),
        (
            "backend.api.ai_insights",
            "/api/v1/ai-insights",
            ["AI Insights"],
        ),
        (
            "backend.api.batch_predict",
            "/api/v1/predict-file",
            ["Batch Prediction"],
        ),
    ]

    for module_name, prefix, tags in router_configs:
        try:
            module = import_module(
                module_name
            )
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                f"Required API module is missing: "
                f"{module_name}"
            ) from exc

        router = getattr(
            module,
            "router",
            None,
        )

        if router is None:
            raise RuntimeError(
                f"API module {module_name} does not expose "
                "a `router` object."
            )

        app.include_router(
            router,
            prefix=prefix,
            tags=tags,
        )

        logger.info(
            "Registered router: %s -> %s",
            module_name,
            prefix,
        )


register_routers()


# ---------------------------------------------------------------------------
# LOCAL DEVELOPMENT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
