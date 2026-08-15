"""
Streamlit SHAP Explainability page.

Features:
- Enter the same customer-level CLV features used by the prediction page.
- Request a local SHAP explanation from FastAPI.
- Display feature contributions and the global SHAP ranking.
- Clearly distinguish positive and negative model contributions.

The model and SHAP calculations remain in the FastAPI backend.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from api_client import (
    APIClientError,
    api_client,
)


st.set_page_config(
    page_title="Explainability | E-Commerce Intelligence",
    page_icon="🔍",
    layout="wide",
)


# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

FEATURE_DEFAULTS = {
    "historical_recency_days": 30.0,
    "historical_order_count": 3.0,
    "historical_revenue": 5000.0,
    "historical_item_count": 5.0,
    "historical_unique_products": 4.0,
    "historical_average_order_value": 1666.67,
    "historical_average_items_per_order": 1.67,
    "historical_orders_per_active_day": 0.10,
}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def load_global_shap(
    top_n: int = 10,
) -> list[dict]:
    """Load global SHAP feature importance."""
    return api_client.global_shap(
        top_n=top_n
    )


def format_feature_name(
    name: str,
) -> str:
    """Make model feature names readable."""
    return name.replace(
        "_",
        " ",
    ).title()


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------

st.title("🔍 SHAP Explainability")

st.markdown(
    """
    Understand **why the CLV model produced a prediction**.

    SHAP decomposes a model prediction into feature-level contributions.
    Positive contributions push predicted value upward, while negative
    contributions push it downward.
    """
)

st.info(
    "SHAP calculations are performed by the FastAPI backend. "
    "This page only visualizes the resulting explanations."
)


# ---------------------------------------------------------------------------
# LOCAL EXPLANATION INPUT
# ---------------------------------------------------------------------------

st.subheader("Customer-Level Explanation")

st.markdown(
    "Enter the customer's historical features to inspect the local model explanation."
)

with st.form(
    "shap_explanation_form"
):
    col1, col2 = st.columns(2)

    with col1:
        historical_recency_days = st.number_input(
            "Historical Recency (days)",
            min_value=0.0,
            value=FEATURE_DEFAULTS[
                "historical_recency_days"
            ],
            step=1.0,
        )

        historical_order_count = st.number_input(
            "Historical Order Count",
            min_value=0.0,
            value=FEATURE_DEFAULTS[
                "historical_order_count"
            ],
            step=1.0,
        )

        historical_revenue = st.number_input(
            "Historical Revenue",
            min_value=0.0,
            value=FEATURE_DEFAULTS[
                "historical_revenue"
            ],
            step=500.0,
        )

        historical_item_count = st.number_input(
            "Historical Item Count",
            min_value=0.0,
            value=FEATURE_DEFAULTS[
                "historical_item_count"
            ],
            step=1.0,
        )

    with col2:
        historical_unique_products = st.number_input(
            "Historical Unique Products",
            min_value=0.0,
            value=FEATURE_DEFAULTS[
                "historical_unique_products"
            ],
            step=1.0,
        )

        historical_average_order_value = st.number_input(
            "Historical Average Order Value",
            min_value=0.0,
            value=FEATURE_DEFAULTS[
                "historical_average_order_value"
            ],
            step=100.0,
        )

        historical_average_items_per_order = st.number_input(
            "Historical Average Items / Order",
            min_value=0.0,
            value=FEATURE_DEFAULTS[
                "historical_average_items_per_order"
            ],
            step=0.1,
        )

        historical_orders_per_active_day = st.number_input(
            "Historical Orders / Active Day",
            min_value=0.0,
            value=FEATURE_DEFAULTS[
                "historical_orders_per_active_day"
            ],
            step=0.01,
            format="%.4f",
        )

    top_n = st.slider(
        "Number of SHAP features to display",
        min_value=3,
        max_value=15,
        value=8,
    )

    submitted = st.form_submit_button(
        "🔍 Explain Prediction",
        type="primary",
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# LOCAL SHAP RESULT
# ---------------------------------------------------------------------------

if submitted:
    features = {
        "historical_recency_days": historical_recency_days,
        "historical_order_count": historical_order_count,
        "historical_revenue": historical_revenue,
        "historical_item_count": historical_item_count,
        "historical_unique_products": historical_unique_products,
        "historical_average_order_value": (
            historical_average_order_value
        ),
        "historical_average_items_per_order": (
            historical_average_items_per_order
        ),
        "historical_orders_per_active_day": (
            historical_orders_per_active_day
        ),
    }

    with st.spinner(
        "Calculating SHAP explanation..."
    ):
        try:
            result = api_client.explain_customer(
                features,
                top_n=top_n,
            )

        except APIClientError as exc:
            st.error(
                "Unable to generate SHAP explanation."
            )
            st.code(str(exc))
            st.stop()

    st.divider()
    st.subheader("Local Explanation")

    # The backend may expose the prediction using different names depending
    # on the exact PredictionService schema.
    prediction = result.get(
        "predicted_future_revenue"
    )

    if prediction is None:
        prediction = result.get(
            "prediction"
        )

    if prediction is not None:
        st.metric(
            "Predicted Future Revenue",
            f"₹{float(prediction):,.2f}",
        )

    explanation_rows = (
        result.get("explanations")
        or result.get("shap_values")
        or result.get("feature_contributions")
        or []
    )

    if isinstance(
        explanation_rows,
        dict,
    ):
        explanation_rows = [
            {
                "feature": key,
                "shap_value": value,
            }
            for key, value
            in explanation_rows.items()
        ]

    if not explanation_rows:
        st.warning(
            ""
        )
        with st.expander("Raw API Response"):
            st.json(result)
    else:
        explanation_df = pd.DataFrame(
            explanation_rows
        )

        # Normalize common backend field names.
        if (
            "feature"
            not in explanation_df.columns
        ):
            for candidate in [
                "feature_name",
                "name",
            ]:
                if candidate in explanation_df.columns:
                    explanation_df = explanation_df.rename(
                        columns={
                            candidate: "feature"
                        }
                    )
                    break

        if (
            "shap_value"
            not in explanation_df.columns
        ):
            for candidate in [
                "contribution",
                "value",
                "mean_abs_shap",
            ]:
                if candidate in explanation_df.columns:
                    explanation_df = explanation_df.rename(
                        columns={
                            candidate: "shap_value"
                        }
                    )
                    break

        if {
            "feature",
            "shap_value",
        }.issubset(explanation_df.columns):
            explanation_df["shap_value"] = pd.to_numeric(
                explanation_df["shap_value"],
                errors="coerce",
            )

            explanation_df = (
                explanation_df
                .dropna(
                    subset=["shap_value"]
                )
                .sort_values(
                    "shap_value",
                    key=lambda series: series.abs(),
                    ascending=False,
                )
                .head(top_n)
            )

            explanation_df["feature_label"] = (
                explanation_df["feature"]
                .astype(str)
                .map(format_feature_name)
            )

            fig = px.bar(
                explanation_df.sort_values(
                    "shap_value"
                ),
                x="shap_value",
                y="feature_label",
                orientation="h",
                labels={
                    "shap_value": "SHAP Contribution",
                    "feature_label": "Feature",
                },
            )

            fig.add_vline(
                x=0,
                line_width=1,
            )

            fig.update_layout(
                height=max(
                    350,
                    45 * len(
                        explanation_df
                    ),
                ),
                margin=dict(
                    l=20,
                    r=20,
                    t=30,
                    b=20,
                ),
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

            st.subheader(
                "Feature Contributions"
            )

            table_df = explanation_df[
                [
                    "feature_label",
                    "shap_value",
                ]
            ].copy()

            table_df = table_df.rename(
                columns={
                    "feature_label": "Feature",
                    "shap_value": "SHAP Contribution",
                }
            )

            table_df["SHAP Contribution"] = (
                table_df[
                    "SHAP Contribution"
                ]
                .round(4)
            )

            st.dataframe(
                table_df,
                use_container_width=True,
                hide_index=True,
            )

            positive = explanation_df[
                explanation_df["shap_value"] > 0
            ]

            negative = explanation_df[
                explanation_df["shap_value"] < 0
            ]

            insight_col1, insight_col2 = st.columns(2)

            with insight_col1:
                st.markdown(
                    "**Positive contributors**"
                )

                if positive.empty:
                    st.write(
                        "No positive contributions in the displayed features."
                    )
                else:
                    for _, row in positive.iterrows():
                        st.write(
                            "• "
                            f"{format_feature_name(row['feature'])}: "
                            f"+{float(row['shap_value']):.4f}"
                        )

            with insight_col2:
                st.markdown(
                    "**Negative contributors**"
                )

                if negative.empty:
                    st.write(
                        "No negative contributions in the displayed features."
                    )
                else:
                    for _, row in negative.iterrows():
                        st.write(
                            "• "
                            f"{format_feature_name(row['feature'])}: "
                            f"{float(row['shap_value']):.4f}"
                        )

        else:
            st.warning(
                "The API response format did not contain recognizable "
                "feature-level SHAP fields."
            )

    with st.expander("Raw SHAP API Response"):
        st.json(result)


# ---------------------------------------------------------------------------
# GLOBAL EXPLANATION
# ---------------------------------------------------------------------------

st.divider()

st.subheader("🌍 Global Model Drivers")

st.markdown(
    """
    Global SHAP importance shows which features have the largest average
    influence across the model's predictions.
    """
)

try:
    global_rows = load_global_shap(
        top_n=10
    )

except APIClientError as exc:
    st.warning(
        "Global SHAP importance is currently unavailable."
    )
    st.caption(str(exc))
    global_rows = []

if global_rows:
    global_df = pd.DataFrame(
        global_rows
    )

    if "feature" not in global_df.columns:
        for candidate in [
            "feature_name",
            "name",
        ]:
            if candidate in global_df.columns:
                global_df = global_df.rename(
                    columns={
                        candidate: "feature"
                    }
                )
                break

    if "mean_abs_shap" not in global_df.columns:
        for candidate in [
            "importance",
            "shap_importance",
            "mean_absolute_shap",
        ]:
            if candidate in global_df.columns:
                global_df = global_df.rename(
                    columns={
                        candidate: "mean_abs_shap"
                    }
                )
                break

    if {
        "feature",
        "mean_abs_shap",
    }.issubset(global_df.columns):
        global_df["mean_abs_shap"] = pd.to_numeric(
            global_df["mean_abs_shap"],
            errors="coerce",
        )

        global_df = (
            global_df
            .dropna(
                subset=["mean_abs_shap"]
            )
            .sort_values(
                "mean_abs_shap",
                ascending=True,
            )
        )

        global_df["feature_label"] = (
            global_df["feature"]
            .astype(str)
            .map(format_feature_name)
        )

        fig = px.bar(
            global_df,
            x="mean_abs_shap",
            y="feature_label",
            orientation="h",
            labels={
                "mean_abs_shap": "Mean |SHAP|",
                "feature_label": "Feature",
            },
        )

        fig.update_layout(
            height=max(
                350,
                45 * len(global_df),
            ),
            margin=dict(
                l=20,
                r=20,
                t=30,
                b=20,
            ),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

        display_df = global_df[
            [
                "feature_label",
                "mean_abs_shap",
            ]
        ].copy()

        display_df = display_df.rename(
            columns={
                "feature_label": "Feature",
                "mean_abs_shap": "Mean |SHAP|",
            }
        )

        display_df["Mean |SHAP|"] = (
            display_df["Mean |SHAP|"]
            .round(5)
        )

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.warning(
            "Global SHAP response did not contain the expected fields."
        )

else:
    st.info(
        "No global SHAP importance data is currently available."
    )
