"""
Streamlit customer intelligence page.

Features:
- Search/select a customer.
- Show customer-level business intelligence.
- Show predicted future revenue and retention priority.
- Show purchase history.
- Show personalized product recommendations.
- Provide a direct link to the customer detail workflow.

The page communicates with FastAPI through frontend.api_client.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from api_client import (
    APIClientError,
    api_client,
)

st.set_page_config(
    page_title="Customers | E-Commerce Intelligence",
    page_icon="👥",
    layout="wide",
)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_customer_business(
    customer_id: str,
) -> dict:
    """Load customer business intelligence."""
    return api_client.customer_business_intelligence(
        customer_id
    )


@st.cache_data(ttl=60)
def load_history(
    customer_id: str,
) -> dict:
    """Load customer purchase history."""
    return api_client.customer_history(
        customer_id
    )


@st.cache_data(ttl=60)
def load_recommendations(
    customer_id: str,
    k: int,
) -> dict:
    """Load personalized recommendations."""
    return api_client.recommendations(
        customer_id,
        k=k,
    )


def money(
    value: float | int | None,
) -> str:
    """Format monetary values."""
    if value is None:
        return "—"

    value = float(value)

    if abs(value) >= 1_000_000:
        return f"₹{value / 1_000_000:.2f}M"

    if abs(value) >= 100_000:
        return f"₹{value / 100_000:.2f}L"

    if abs(value) >= 1_000:
        return f"₹{value / 1_000:.1f}K"

    return f"₹{value:,.0f}"


def priority_message(
    priority: str,
) -> str:
    """Return a concise business interpretation."""
    messages = {
        "Critical": (
            "Immediate retention attention is recommended."
        ),
        "High": (
            "This customer should be prioritized for retention."
        ),
        "Medium": (
            "This customer is a moderate retention opportunity."
        ),
        "Low": (
            "No immediate high-priority retention action is indicated."
        ),
    }

    return messages.get(
        priority,
        "Retention priority is available from the analytical pipeline.",
    )


# ---------------------------------------------------------------------------
# PAGE HEADER
# ---------------------------------------------------------------------------

st.title("👥 Customer Intelligence")

st.markdown(
    """
    Search for a customer and inspect their value, retention status,
    purchase history, and product recommendations.
    """
)

st.divider()


# ---------------------------------------------------------------------------
# CUSTOMER INPUT
# ---------------------------------------------------------------------------

st.subheader("Select Customer")

customer_id = st.text_input(
    "Customer Unique ID",
    value=st.session_state.get(
        "selected_customer_id",
        "",
    ) or "",
    placeholder="Enter customer_unique_id",
    help=(
        "Use the customer_unique_id from the processed customer dataset."
    ),
)

col1, col2 = st.columns(
    [1, 5]
)

with col1:
    load_customer = st.button(
        "Load Customer",
        type="primary",
        use_container_width=True,
    )

if load_customer:
    if not customer_id.strip():
        st.warning(
            "Please enter a customer ID."
        )
        st.stop()

    st.session_state.selected_customer_id = (
        customer_id.strip()
    )


selected_customer = st.session_state.get(
    "selected_customer_id"
)

if not selected_customer:
    st.info(
        "Enter a customer ID above to view customer intelligence."
    )
    st.stop()


# ---------------------------------------------------------------------------
# LOAD CUSTOMER DATA
# ---------------------------------------------------------------------------

try:
    with st.spinner("Loading customer intelligence..."):
        business = load_customer_business(
            selected_customer
        )

        history = load_history(
            selected_customer
        )

        recommendations = load_recommendations(
            selected_customer,
            k=10,
        )

except APIClientError as exc:
    st.error(
        "Unable to load this customer."
    )
    st.code(str(exc))
    st.stop()


# ---------------------------------------------------------------------------
# CUSTOMER HEADER
# ---------------------------------------------------------------------------

st.subheader(
    f"Customer: {selected_customer}"
)

priority = business.get(
    "retention_priority",
    "Unknown",
)

st.caption(
    priority_message(priority)
)


# ---------------------------------------------------------------------------
# KPI CARDS
# ---------------------------------------------------------------------------

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.metric(
        "Predicted Future Revenue",
        money(
            business.get(
                "predicted_future_revenue"
            )
        ),
    )

with kpi2:
    st.metric(
        "Recency",
        f"{business.get('recency_days', 0):,.0f} days",
    )

with kpi3:
    st.metric(
        "Orders",
        f"{business.get('order_count', 0):,.0f}",
    )

with kpi4:
    opportunity_score = business.get(
        "opportunity_score"
    )

    st.metric(
        "Opportunity Score",
        (
            f"{float(opportunity_score):.3f}"
            if opportunity_score is not None
            else "—"
        ),
    )


# ---------------------------------------------------------------------------
# RETENTION INTELLIGENCE
# ---------------------------------------------------------------------------

st.subheader("🎯 Retention Intelligence")

ret_col1, ret_col2 = st.columns(2)

with ret_col1:
    st.markdown("**Priority**")

    if priority == "Critical":
        st.error(priority)
    elif priority == "High":
        st.warning(priority)
    elif priority == "Medium":
        st.info(priority)
    else:
        st.success(priority)

    st.markdown("**Recommended Action**")
    st.write(
        business.get(
            "recommended_action",
            "No recommendation available.",
        )
    )

with ret_col2:
    st.markdown("**Why**")
    st.write(
        business.get(
            "recommendation_reason",
            "No recommendation reason available.",
        )
    )

    st.markdown("**Retention Strategy**")
    st.write(
        business.get(
            "retention_strategy",
            "No retention strategy available.",
        )
    )


# ---------------------------------------------------------------------------
# CUSTOMER ATTRIBUTES
# ---------------------------------------------------------------------------

optional_attributes = {
    "Customer Segment": business.get(
        "customer_segment"
    )
    or business.get("segment"),
    "Total Historical Revenue": business.get(
        "total_revenue"
    ),
    "Average Review Score": business.get(
        "average_review_score"
    ),
    "Cluster": business.get(
        "cluster_id"
    ),
}

available_attributes = {
    key: value
    for key, value in optional_attributes.items()
    if value is not None
}

if available_attributes:
    st.subheader("Customer Profile")

    profile_df = pd.DataFrame(
        [
            {
                "Attribute": key,
                "Value": (
                    money(value)
                    if "Revenue" in key
                    else value
                ),
            }
            for key, value
            in available_attributes.items()
        ]
    )

    st.dataframe(
        profile_df,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# PURCHASE HISTORY
# ---------------------------------------------------------------------------

st.subheader("🛒 Purchase History")

purchased_products = history.get(
    "purchased_products",
    [],
)

if not purchased_products:
    st.info(
        "No known purchase history is available for this customer."
    )
else:
    st.write(
        f"{len(purchased_products):,} unique products purchased."
    )

    history_df = pd.DataFrame(
        {
            "Product ID": purchased_products
        }
    )

    st.dataframe(
        history_df,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# RECOMMENDATIONS
# ---------------------------------------------------------------------------

st.subheader("🛍️ Personalized Recommendations")

recommendation_rows = recommendations.get(
    "recommendations",
    [],
)

if not recommendation_rows:
    st.info(
        "No personalized recommendations are available."
    )
else:
    recommendation_df = pd.DataFrame(
        recommendation_rows
    )

    display_columns = [
        "rank",
        "product_id",
        "score",
        "method",
        "category",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in recommendation_df.columns
    ]

    recommendation_df = recommendation_df[
        available_columns
    ].copy()

    if "score" in recommendation_df.columns:
        recommendation_df["score"] = (
            pd.to_numeric(
                recommendation_df["score"],
                errors="coerce",
            )
            .round(4)
        )

    st.dataframe(
        recommendation_df,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# RAW ANALYTICAL CONTEXT
# ---------------------------------------------------------------------------

with st.expander("View Analytical Customer Record"):
    st.json(business)
