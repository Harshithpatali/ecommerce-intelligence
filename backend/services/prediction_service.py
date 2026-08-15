"""
Prediction service for the E-Commerce Intelligence API.

Responsibilities:
- Load the trained CLV model artifact once.
- Validate and normalize prediction inputs.
- Reproduce the exact feature order used during training.
- Generate future-revenue predictions.
- Provide batch prediction support for DataFrames.

This service contains ML inference logic only.
FastAPI request/response handling belongs in backend/api/.
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

import joblib
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "models" / "clv_xgboost.joblib"


# ---------------------------------------------------------------------------
# SERVICE
# ---------------------------------------------------------------------------

class PredictionService:
    """
    Production-oriented wrapper around the trained CLV model.

    The model artifact created by notebook 04 contains:
        - model
        - features
        - target
        - observation_cutoff
        - metrics
    """

    _model: Any = None
    _features: list[str] | None = None
    _artifact: dict[str, Any] | None = None
    _lock = Lock()

    @classmethod
    def load_model(cls) -> None:
        """Load the model artifact once."""
        if cls._model is not None:
            return

        with cls._lock:
            if cls._model is not None:
                return

            if not MODEL_PATH.exists():
                raise FileNotFoundError(
                    f"CLV model artifact not found: {MODEL_PATH}. "
                    "Run notebook 04 before starting prediction inference."
                )

            artifact = joblib.load(MODEL_PATH)

            if not isinstance(artifact, dict):
                raise ValueError(
                    "Invalid CLV model artifact. Expected a dictionary."
                )

            if "model" not in artifact:
                raise ValueError(
                    "Invalid CLV model artifact: missing `model`."
                )

            if "features" not in artifact:
                raise ValueError(
                    "Invalid CLV model artifact: missing `features`."
                )

            features = artifact["features"]

            if not isinstance(features, list) or not features:
                raise ValueError(
                    "Invalid CLV model artifact: `features` must be "
                    "a non-empty list."
                )

            cls._artifact = artifact
            cls._model = artifact["model"]
            cls._features = features

    @classmethod
    def get_model_metadata(cls) -> dict[str, Any]:
        """Return non-sensitive metadata about the loaded model."""
        cls.load_model()

        assert cls._artifact is not None
        assert cls._features is not None

        return {
            "model_type": type(cls._model).__name__,
            "features": cls._features,
            "target": cls._artifact.get(
                "target",
                "future_revenue",
            ),
            "observation_cutoff": str(
                cls._artifact.get(
                    "observation_cutoff",
                    "",
                )
            ),
            "training_metrics": cls._artifact.get(
                "metrics",
                {},
            ),
        }

    @classmethod
    def _prepare_features(
        cls,
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Validate and prepare model features.

        The feature order comes from the saved model artifact.
        """
        cls.load_model()

        assert cls._features is not None

        if not isinstance(data, pd.DataFrame):
            raise TypeError(
                "Prediction input must be a pandas DataFrame."
            )

        missing_features = [
            feature
            for feature in cls._features
            if feature not in data.columns
        ]

        if missing_features:
            raise ValueError(
                "Missing required prediction features: "
                + ", ".join(missing_features)
            )

        X = data[cls._features].copy()

        # Convert all model inputs to numeric values.
        for feature in cls._features:
            X[feature] = pd.to_numeric(
                X[feature],
                errors="coerce",
            )

        X = X.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        # The training notebook used median imputation for the modeling
        # matrix. We reproduce the same inference behavior here.
        X = X.fillna(
            X.median(numeric_only=True)
        )

        # A completely empty/all-null feature column can still contain NaN
        # after median imputation. Fail explicitly rather than silently
        # passing invalid values to the model.
        remaining_missing = X.columns[
            X.isna().any()
        ].tolist()

        if remaining_missing:
            raise ValueError(
                "Unable to prepare numeric values for: "
                + ", ".join(remaining_missing)
            )

        return X

    @classmethod
    def predict_dataframe(
        cls,
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Generate predictions for every row in a DataFrame.

        Returns a copy of the input with:
            predicted_future_revenue
        appended.
        """
        cls.load_model()

        X = cls._prepare_features(data)

        predictions = cls._model.predict(X)

        predictions = np.asarray(
            predictions,
            dtype=float,
        )

        # Future revenue cannot be negative.
        predictions = np.clip(
            predictions,
            a_min=0,
            a_max=None,
        )

        result = data.copy()

        result["predicted_future_revenue"] = predictions

        return result

    @classmethod
    def predict_one(
        cls,
        features: dict[str, Any],
    ) -> float:
        """
        Predict future customer revenue for one customer.

        Parameters
        ----------
        features:
            Dictionary containing all trained model features.

        Returns
        -------
        float
            Predicted future revenue.
        """
        data = pd.DataFrame([features])

        result = cls.predict_dataframe(data)

        return float(
            result.iloc[0]["predicted_future_revenue"]
        )

    @classmethod
    def predict_batch(
        cls,
        data: pd.DataFrame,
    ) -> list[float]:
        """Return predictions as a plain Python list."""
        result = cls.predict_dataframe(data)

        return (
            result["predicted_future_revenue"]
            .astype(float)
            .tolist()
        )


# ---------------------------------------------------------------------------
# CONVENIENCE FUNCTIONS
# ---------------------------------------------------------------------------

def predict_customer(
    features: dict[str, Any],
) -> float:
    """Convenience wrapper for single-customer prediction."""
    return PredictionService.predict_one(features)


def predict_customers(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Convenience wrapper for batch prediction."""
    return PredictionService.predict_dataframe(data)
