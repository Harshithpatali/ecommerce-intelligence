"""
Groq AI Insights service for the E-Commerce Intelligence API.

Responsibilities:
- Load trusted analytical outputs from data/processed/.
- Build a compact, deterministic business context.
- Call Groq only for natural-language interpretation.
- Prevent the LLM from becoming the numerical source of truth.
- Provide portfolio and customer-level AI insight generation.

Environment variables:
    GROQ_API_KEY
    GROQ_MODEL (optional; defaults to llama-3.3-70b-versatile)

The API key is never stored in source code or returned by this service.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd

from dotenv import load_dotenv

load_dotenv()
# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RETENTION_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "retention_recommendations.csv"
)

SEGMENTS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "customer_segments.csv"
)

CLV_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "customer_clv_predictions.csv"
)

SHAP_GLOBAL_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "clv_shap_global_importance.csv"
)


# ---------------------------------------------------------------------------
# PROMPTS
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are an e-commerce business intelligence analyst.

You interpret trusted analytical outputs supplied by a Python data pipeline.

Rules:
1. Use only the metrics supplied in the business context.
2. Never invent, estimate, or fabricate numbers.
3. Do not claim that a relationship is causal unless the supplied data
   explicitly supports causality.
4. Clearly distinguish observed analytical facts from recommendations.
5. Prioritize commercially meaningful insights.
6. Mention uncertainty when the supplied data is insufficient.
7. Do not expose API keys, internal secrets, or implementation details.
8. Keep the response concise and executive-friendly.

For portfolio analysis, return:
1. Executive Summary
2. Key Customer Insights
3. Retention Priorities
4. Recommended Actions
5. Risks / Caveats
6. What to Investigate Next

For customer analysis, return:
1. Customer Status
2. Why This Customer Matters
3. Recommended Action
4. Reasoning
5. Caveat
"""


# ---------------------------------------------------------------------------
# SERVICE
# ---------------------------------------------------------------------------

class GroqAIService:
    """Natural-language interpretation layer backed by Groq."""

    _client: Any = None
    _model: str | None = None
    _lock = Lock()

    @classmethod
    def _get_client(cls) -> Any:
        """Create the Groq client lazily."""
        if cls._client is not None:
            return cls._client

        with cls._lock:
            if cls._client is not None:
                return cls._client

            api_key = os.getenv("GROQ_API_KEY")

            if not api_key:
                raise RuntimeError(
                    "GROQ_API_KEY is not configured."
                )

            try:
                from groq import Groq
            except ImportError as exc:
                raise RuntimeError(
                    "The `groq` package is not installed. "
                    "Install it with: pip install groq"
                ) from exc

            cls._client = Groq(
                api_key=api_key
            )

            cls._model = os.getenv(
                "GROQ_MODEL",
                "llama-3.3-70b-versatile",
            )

            return cls._client

    @classmethod
    def _load_context_tables(cls) -> dict[str, pd.DataFrame]:
        """Load only the analytical tables needed for AI context."""
        if not RETENTION_PATH.exists():
            raise FileNotFoundError(
                f"Retention dataset not found: {RETENTION_PATH}"
            )

        retention = pd.read_csv(
            RETENTION_PATH
        )

        tables = {
            "retention": retention,
        }

        if SEGMENTS_PATH.exists():
            tables["segments"] = pd.read_csv(
                SEGMENTS_PATH
            )

        if CLV_PATH.exists():
            tables["clv"] = pd.read_csv(
                CLV_PATH
            )

        if SHAP_GLOBAL_PATH.exists():
            tables["shap_global"] = pd.read_csv(
                SHAP_GLOBAL_PATH
            )

        return tables

    @classmethod
    def _build_portfolio_context(cls) -> dict[str, Any]:
        """Build compact trusted portfolio context."""
        tables = cls._load_context_tables()

        retention = tables["retention"]

        predicted_value = pd.to_numeric(
            retention["predicted_future_revenue"],
            errors="coerce",
        ).fillna(0)

        recency = pd.to_numeric(
            retention["recency_days"],
            errors="coerce",
        ).fillna(0)

        context: dict[str, Any] = {
            "customer_count": int(
                retention["customer_unique_id"].nunique()
            ),
            "predicted_future_revenue_total": float(
                predicted_value.sum()
            ),
            "average_predicted_customer_value": float(
                predicted_value.mean()
            ),
            "average_recency_days": float(
                recency.mean()
            ),
            "retention_priority_distribution": (
                retention["retention_priority"]
                .value_counts()
                .to_dict()
            ),
            "recommended_action_distribution": (
                retention["recommended_action"]
                .value_counts()
                .to_dict()
            ),
        }

        if "segment" in retention.columns:
            context["segment_distribution"] = (
                retention["segment"]
                .value_counts()
                .to_dict()
            )

        if "segments" in tables:
            segments = tables["segments"]

            if "segment" in segments.columns:
                segment_summary = (
                    segments
                    .groupby("segment", dropna=False)
                    .agg(
                        customers=(
                            "customer_unique_id",
                            "nunique",
                        ),
                        total_revenue=(
                            "total_revenue",
                            "sum",
                        ),
                        average_recency_days=(
                            "recency_days",
                            "mean",
                        ),
                        average_order_count=(
                            "order_count",
                            "mean",
                        ),
                    )
                    .reset_index()
                )

                context["segment_summary"] = (
                    segment_summary.to_dict(
                        orient="records"
                    )
                )

        if "shap_global" in tables:
            shap_global = tables["shap_global"]

            if {
                "feature",
                "mean_abs_shap",
            }.issubset(shap_global.columns):
                context["top_model_drivers"] = (
                    shap_global
                    .sort_values(
                        "mean_abs_shap",
                        ascending=False,
                    )
                    .head(10)
                    .to_dict(
                        orient="records"
                    )
                )

        value_cutoff = predicted_value.quantile(
            0.75
        )
        recency_cutoff = recency.quantile(
            0.75
        )

        opportunity = retention[
            (predicted_value >= value_cutoff)
            & (recency >= recency_cutoff)
        ]

        context["high_value_inactive_customers"] = int(
            len(opportunity)
        )

        context["predicted_value_at_risk_opportunity"] = float(
            opportunity[
                "predicted_future_revenue"
            ].sum()
        )

        return context

    @classmethod
    def _build_customer_context(
        cls,
        customer_id: str,
    ) -> dict[str, Any]:
        """Build trusted context for one customer."""
        tables = cls._load_context_tables()
        retention = tables["retention"]

        matches = retention[
            retention["customer_unique_id"].astype(str)
            == str(customer_id)
        ]

        if matches.empty:
            raise KeyError(
                f"Customer {customer_id} not found."
            )

        row = matches.iloc[0]

        context: dict[str, Any] = {}

        fields = [
            "customer_unique_id",
            "predicted_future_revenue",
            "recency_days",
            "order_count",
            "retention_priority",
            "recommended_action",
            "recommendation_reason",
            "retention_strategy",
            "opportunity_score",
        ]

        for field in fields:
            if field in row.index:
                value = row[field]

                if pd.isna(value):
                    context[field] = None
                elif isinstance(
                    value,
                    (int, float),
                ):
                    context[field] = float(value)
                else:
                    context[field] = str(value)

        optional_fields = [
            "total_revenue",
            "average_order_value",
            "segment",
            "customer_segment",
            "cluster_id",
        ]

        for field in optional_fields:
            if field in row.index and pd.notna(
                row[field]
            ):
                value = row[field]

                if isinstance(
                    value,
                    (int, float),
                ):
                    context[field] = float(value)
                else:
                    context[field] = str(value)

        return context

    @classmethod
    def _call(
        cls,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """Send one constrained request to Groq."""
        client = cls._get_client()

        assert cls._model is not None

        response = client.chat.completions.create(
            model=cls._model,
            temperature=temperature,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        )

        if not response.choices:
            raise RuntimeError(
                "Groq returned no completion choices."
            )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError(
                "Groq returned an empty response."
            )

        return content.strip()

    @classmethod
    def portfolio_insights(cls) -> dict[str, Any]:
        """Generate an executive portfolio insight report."""
        context = cls._build_portfolio_context()

        prompt = f"""
Analyze the following trusted e-commerce analytics context.

Do not calculate new metrics.
Do not invent missing values.
Do not infer customer attributes that are not present.

TRUSTED ANALYTICS CONTEXT:
{json.dumps(context, indent=2, default=str)}

Write the executive-friendly report using the six portfolio sections
specified in the system instructions.
"""

        report = cls._call(
            prompt
        )

        return {
            "model": cls._model,
            "report": report,
            "context_metrics": {
                "customer_count": context["customer_count"],
                "predicted_future_revenue_total": (
                    context[
                        "predicted_future_revenue_total"
                    ]
                ),
                "high_value_inactive_customers": (
                    context[
                        "high_value_inactive_customers"
                    ]
                ),
            },
        }

    @classmethod
    def customer_insight(
        cls,
        customer_id: str,
    ) -> dict[str, Any]:
        """Generate a concise customer-level retention insight."""
        context = cls._build_customer_context(
            customer_id
        )

        prompt = f"""
Create a concise retention insight for the customer described below.

Use only the supplied customer metrics.
Do not invent purchase categories, preferences, demographics, or behavior.
Do not claim causality.

TRUSTED CUSTOMER CONTEXT:
{json.dumps(context, indent=2, default=str)}

Write the customer-level report using:
1. Customer Status
2. Why This Customer Matters
3. Recommended Action
4. Reasoning
5. Caveat
"""

        report = cls._call(
            prompt
        )

        return {
            "customer_id": str(customer_id),
            "model": cls._model,
            "report": report,
            "trusted_context": context,
        }

    @classmethod
    def status(cls) -> dict[str, Any]:
        """Return non-secret AI service configuration status."""
        api_key_configured = bool(
            os.getenv("GROQ_API_KEY")
        )

        return {
            "provider": "Groq",
            "api_key_configured": api_key_configured,
            "model": os.getenv(
                "GROQ_MODEL",
                "llama-3.3-70b-versatile",
            ),
            "retention_data_available": (
                RETENTION_PATH.exists()
            ),
            "segments_data_available": (
                SEGMENTS_PATH.exists()
            ),
            "clv_data_available": (
                CLV_PATH.exists()
            ),
            "shap_global_data_available": (
                SHAP_GLOBAL_PATH.exists()
            ),
        }


# ---------------------------------------------------------------------------
# CONVENIENCE FUNCTIONS
# ---------------------------------------------------------------------------

def generate_portfolio_ai_insights() -> dict[str, Any]:
    """Generate portfolio-level AI insights."""
    return GroqAIService.portfolio_insights()


def generate_customer_ai_insight(
    customer_id: str,
) -> dict[str, Any]:
    """Generate a customer-level AI insight."""
    return GroqAIService.customer_insight(
        customer_id
    )
