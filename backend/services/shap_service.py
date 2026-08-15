"""
SHAP explainability service for the E-Commerce Intelligence API.

Responsibilities:
- Load the trained CLV model once.
- Load the saved customer-level SHAP artifact when available.
- Calculate SHAP contributions for a supplied customer feature vector.
- Return top positive and negative model drivers.
- Expose global feature importance metadata.

The service explains model behavior; it does not claim causal relationships.
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

import joblib
import numpy as np
import pandas as pd
import shap


# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = PROJECT_ROOT / "models" / "clv_xgboost.joblib"

SHAP_VALUES_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "customer_shap_values.csv"
)

GLOBAL_SHAP_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "clv_shap_global_importance.csv"
)


# ---------------------------------------------------------------------------
# SERVICE
# ---------------------------------------------------------------------------

class SHAPService:
    """
    Service wrapper for customer-level and global SHAP explanations.

    The trained model predicts log(1 + future revenue), because the CLV
    training notebook used TransformedTargetRegressor. Therefore the SHAP
    contributions produced by TreeExplainer are contributions in the
    underlying XGBoost/log-target model output space.
    """

    _explainer: Any = None
    _model_artifact: dict[str, Any] | None = None
    _features: list[str] | None = None
    _global_importance: pd.DataFrame | None = None
    _lock = Lock()

    @classmethod
    def load(cls) -> None:
        """Load the model and SHAP explainer once."""
        if cls._explainer is not None:
            return

        with cls._lock:
            if cls._explainer is not None:
                return

            if not MODEL_PATH.exists():
                raise FileNotFoundError(
                    f"CLV model artifact not found: {MODEL_PATH}. "
                    "Run notebook 04 first."
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
                    "Invalid model feature metadata."
                )

            # The saved model is a TransformedTargetRegressor. The underlying
            # XGBoost estimator is the object TreeExplainer understands.
            model = artifact["model"]
            xgb_model = getattr(model, "regressor_", model)

            cls._model_artifact = artifact
            cls._features = features
            cls._explainer = shap.TreeExplainer(xgb_model)

            if GLOBAL_SHAP_PATH.exists():
                global_df = pd.read_csv(
                    GLOBAL_SHAP_PATH
                )

                expected = {
                    "feature",
                    "mean_abs_shap",
                }

                if expected.issubset(global_df.columns):
                    cls._global_importance = (
                        global_df.sort_values(
                            "mean_abs_shap",
                            ascending=False,
                        )
                        .reset_index(drop=True)
                    )

    @classmethod
    def _prepare_features(
        cls,
        features: dict[str, Any],
    ) -> pd.DataFrame:
        """Validate and normalize one customer feature vector."""
        cls.load()

        assert cls._features is not None

        missing = [
            feature
            for feature in cls._features
            if feature not in features
        ]

        if missing:
            raise ValueError(
                "Missing required SHAP features: "
                + ", ".join(missing)
            )

        values = {}

        for feature in cls._features:
            try:
                values[feature] = float(
                    features[feature]
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Feature `{feature}` must be numeric."
                ) from exc

        X = pd.DataFrame(
            [values],
            columns=cls._features,
        )

        X = X.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        if X.isna().any().any():
            raise ValueError(
                "SHAP input contains missing or invalid numeric values."
            )

        return X

    @classmethod
    def explain(
        cls,
        features: dict[str, Any],
        top_n: int = 5,
    ) -> dict[str, Any]:
        """
        Generate a customer-level SHAP explanation.

        Returns:
            base_value
            model_output
            top_positive_factors
            top_negative_factors
        """
        cls.load()

        if top_n < 1 or top_n > 20:
            raise ValueError(
                "top_n must be between 1 and 20."
            )

        X = cls._prepare_features(features)

        assert cls._explainer is not None
        assert cls._features is not None

        shap_values = cls._explainer.shap_values(X)
        shap_values = np.asarray(shap_values)

        # TreeExplainer returns a one-dimensional vector for one row in the
        # common regression case, but normalize the shape defensively.
        if shap_values.ndim == 2:
            row_values = shap_values[0]
        else:
            row_values = shap_values.reshape(-1)

        if len(row_values) != len(cls._features):
            raise ValueError(
                "Unexpected SHAP output shape."
            )

        base_value = cls._explainer.expected_value

        if isinstance(base_value, np.ndarray):
            base_value = float(
                np.asarray(base_value).reshape(-1)[0]
            )
        else:
            base_value = float(base_value)

        model_output = float(
            base_value + row_values.sum()
        )

        contributions = pd.DataFrame({
            "feature": cls._features,
            "feature_value": [
                float(X.iloc[0][feature])
                for feature in cls._features
            ],
            "shap_value": row_values.astype(float),
        })

        positive = (
            contributions[
                contributions["shap_value"] > 0
            ]
            .sort_values(
                "shap_value",
                ascending=False,
            )
            .head(top_n)
            .reset_index(drop=True)
        )

        negative = (
            contributions[
                contributions["shap_value"] < 0
            ]
            .sort_values(
                "shap_value",
                ascending=True,
            )
            .head(top_n)
            .reset_index(drop=True)
        )

        # If there are fewer than top_n positive/negative drivers, return the
        # available drivers rather than manufacturing explanations.
        return {
            "base_value": base_value,
            "model_output": model_output,
            "top_positive_factors": positive.to_dict(
                orient="records"
            ),
            "top_negative_factors": negative.to_dict(
                orient="records"
            ),
            "all_factors": contributions.to_dict(
                orient="records"
            ),
            "interpretation_note": (
                "SHAP values describe model contribution in the "
                "underlying XGBoost output space and should not be "
                "interpreted as causal effects."
            ),
        }

    @classmethod
    def global_importance(
        cls,
        top_n: int = 10,
    ) -> list[dict[str, Any]]:
        """Return global SHAP feature importance."""
        cls.load()

        if top_n < 1 or top_n > 50:
            raise ValueError(
                "top_n must be between 1 and 50."
            )

        if cls._global_importance is not None:
            result = cls._global_importance.head(top_n).copy()

            return result.to_dict(
                orient="records"
            )

        # If the precomputed global CSV is unavailable, calculate global
        # importance from the saved customer-level SHAP matrix when possible.
        if not SHAP_VALUES_PATH.exists():
            raise FileNotFoundError(
                f"Global SHAP artifact not found: "
                f"{SHAP_VALUES_PATH}"
            )

        if cls._features is None:
            raise ValueError(
                "Model feature metadata is unavailable."
            )

        customer_shap = pd.read_csv(
            SHAP_VALUES_PATH
        )

        shap_columns = [
            f"shap_{feature}"
            for feature in cls._features
        ]

        missing = [
            column
            for column in shap_columns
            if column not in customer_shap.columns
        ]

        if missing:
            raise ValueError(
                "Customer SHAP artifact is missing columns: "
                + ", ".join(missing)
            )

        importance = pd.DataFrame({
            "feature": cls._features,
            "mean_abs_shap": [
                float(
                    customer_shap[column]
                    .abs()
                    .mean()
                )
                for column in shap_columns
            ],
        })

        importance = importance.sort_values(
            "mean_abs_shap",
            ascending=False,
        ).head(top_n)

        return importance.to_dict(
            orient="records"
        )


# ---------------------------------------------------------------------------
# CONVENIENCE FUNCTIONS
# ---------------------------------------------------------------------------

def explain_customer(
    features: dict[str, Any],
    top_n: int = 5,
) -> dict[str, Any]:
    """Convenience wrapper for customer-level SHAP explanation."""
    return SHAPService.explain(
        features=features,
        top_n=top_n,
    )


def get_global_shap_importance(
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Convenience wrapper for global SHAP importance."""
    return SHAPService.global_importance(
        top_n=top_n,
    )
