"""
Recommendation service for the E-Commerce Intelligence API.

Responsibilities:
- Load the serialized recommendation artifact once.
- Generate personalized product recommendations.
- Fall back to popularity recommendations when personalization evidence
  is unavailable.
- Return ranked product candidates with optional category metadata.

The recommendation artifact is created by notebook 06.
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

import joblib
import pandas as pd


# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ARTIFACT_PATH = (
    PROJECT_ROOT
    / "models"
    / "recommendation_artifact.joblib"
)

RECOMMENDATION_DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "recommendations.csv"
)


# ---------------------------------------------------------------------------
# SERVICE
# ---------------------------------------------------------------------------

class RecommendationService:
    """Application-level wrapper around the recommendation artifact."""

    _artifact: dict[str, Any] | None = None
    _recommendation_data: pd.DataFrame | None = None
    _lock = Lock()

    @classmethod
    def load(cls) -> None:
        """Load recommendation artifacts once."""
        if cls._artifact is not None:
            return

        with cls._lock:
            if cls._artifact is not None:
                return

            if not ARTIFACT_PATH.exists():
                raise FileNotFoundError(
                    f"Recommendation artifact not found: {ARTIFACT_PATH}. "
                    "Run notebook 06 first."
                )

            artifact = joblib.load(ARTIFACT_PATH)

            if not isinstance(artifact, dict):
                raise ValueError(
                    "Invalid recommendation artifact. "
                    "Expected a dictionary."
                )

            required_keys = [
                "customer_history",
                "item_similarity",
                "popularity",
                "popularity_score",
            ]

            missing = [
                key
                for key in required_keys
                if key not in artifact
            ]

            if missing:
                raise ValueError(
                    "Recommendation artifact is missing: "
                    + ", ".join(missing)
                )

            cls._artifact = artifact

            if RECOMMENDATION_DATA_PATH.exists():
                recommendation_data = pd.read_csv(
                    RECOMMENDATION_DATA_PATH
                )

                expected_columns = {
                    "customer_unique_id",
                    "product_id",
                    "rank",
                }

                if expected_columns.issubset(
                    recommendation_data.columns
                ):
                    cls._recommendation_data = (
                        recommendation_data
                    )

    @classmethod
    def _fallback_popularity(
        cls,
        customer_id: str,
        k: int,
    ) -> list[dict[str, Any]]:
        """Return popular products not already purchased."""
        cls.load()

        assert cls._artifact is not None

        history = cls._artifact[
            "customer_history"
        ].get(
            customer_id,
            set(),
        )

        popularity = cls._artifact["popularity"]

        if not isinstance(popularity, pd.DataFrame):
            popularity = pd.DataFrame(popularity)

        results = []

        for row in popularity.itertuples():
            product_id = row.product_id

            if product_id in history:
                continue

            results.append({
                "product_id": str(product_id),
                "rank": len(results) + 1,
                "score": 0.0,
                "method": "popularity_fallback",
            })

            if len(results) >= k:
                break

        return results

    @classmethod
    def recommend(
        cls,
        customer_id: str,
        k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Generate personalized product recommendations.

        Parameters
        ----------
        customer_id:
            Customer unique ID used by the training interaction data.

        k:
            Number of products to return.

        Returns
        -------
        list[dict]
            Ranked recommendation records.
        """
        cls.load()

        if not customer_id:
            raise ValueError(
                "customer_id is required."
            )

        if k < 1 or k > 50:
            raise ValueError(
                "k must be between 1 and 50."
            )

        assert cls._artifact is not None

        history = cls._artifact[
            "customer_history"
        ].get(
            str(customer_id),
            set(),
        )

        # Cold-start customer:
        # use the popularity baseline rather than inventing personalization.
        if not history:
            return cls._fallback_popularity(
                str(customer_id),
                k,
            )

        item_similarity = cls._artifact[
            "item_similarity"
        ]

        popularity_score = cls._artifact[
            "popularity_score"
        ]

        candidate_scores: dict[str, float] = {}

        for purchased_product in history:
            related_products = item_similarity.get(
                purchased_product,
                {},
            )

            for candidate, similarity in (
                related_products.items()
            ):
                candidate = str(candidate)

                if candidate in history:
                    continue

                candidate_scores[candidate] = (
                    candidate_scores.get(candidate, 0.0)
                    + float(similarity)
                )

        if not candidate_scores:
            return cls._fallback_popularity(
                str(customer_id),
                k,
            )

        ranked = sorted(
            candidate_scores.items(),
            key=lambda item: (
                item[1],
                float(
                    popularity_score.get(
                        item[0],
                        0.0,
                    )
                ),
            ),
            reverse=True,
        )

        results = []

        for rank, (product_id, score) in enumerate(
            ranked[:k],
            start=1,
        ):
            results.append({
                "product_id": str(product_id),
                "rank": rank,
                "score": float(score),
                "method": "item_item_similarity",
            })

        return results

    @classmethod
    def get_saved_recommendations(
        cls,
        customer_id: str,
        k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Return recommendations already generated by notebook 06.

        This is useful for fast dashboard/API reads when a precomputed
        recommendation table is preferred over on-demand scoring.
        """
        cls.load()

        if k < 1 or k > 50:
            raise ValueError(
                "k must be between 1 and 50."
            )

        if cls._recommendation_data is None:
            raise FileNotFoundError(
                f"Saved recommendation data not found: "
                f"{RECOMMENDATION_DATA_PATH}"
            )

        customer_rows = cls._recommendation_data[
            cls._recommendation_data[
                "customer_unique_id"
            ].astype(str)
            == str(customer_id)
        ].copy()

        if customer_rows.empty:
            return []

        customer_rows = customer_rows.sort_values(
            "rank"
        ).head(k)

        result = []

        for row in customer_rows.to_dict(
            orient="records"
        ):
            item = {
                "product_id": str(
                    row["product_id"]
                ),
                "rank": int(row["rank"]),
            }

            if "category" in row and pd.notna(
                row["category"]
            ):
                item["category"] = str(
                    row["category"]
                )

            result.append(item)

        return result

    @classmethod
    def get_customer_history(
        cls,
        customer_id: str,
    ) -> list[str]:
        """Return products previously purchased by a customer."""
        cls.load()

        assert cls._artifact is not None

        history = cls._artifact[
            "customer_history"
        ].get(
            str(customer_id),
            set(),
        )

        return [
            str(product_id)
            for product_id in history
        ]

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        """Return non-sensitive recommendation artifact metadata."""
        cls.load()

        assert cls._artifact is not None

        popularity = cls._artifact[
            "popularity"
        ]

        if isinstance(popularity, pd.DataFrame):
            popularity_count = len(popularity)
        else:
            popularity_count = len(popularity)

        return {
            "artifact": str(
                ARTIFACT_PATH.relative_to(
                    PROJECT_ROOT
                )
            ),
            "customers_with_history": len(
                cls._artifact["customer_history"]
            ),
            "products_in_popularity_table": popularity_count,
            "default_top_k": cls._artifact.get(
                "top_k_default",
                10,
            ),
        }


# ---------------------------------------------------------------------------
# CONVENIENCE FUNCTIONS
# ---------------------------------------------------------------------------

def recommend_products(
    customer_id: str,
    k: int = 10,
) -> list[dict[str, Any]]:
    """Convenience wrapper for personalized recommendations."""
    return RecommendationService.recommend(
        customer_id=customer_id,
        k=k,
    )


def get_customer_history(
    customer_id: str,
) -> list[str]:
    """Convenience wrapper for customer purchase history."""
    return RecommendationService.get_customer_history(
        customer_id=customer_id,
    )
