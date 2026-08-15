"""
Streamlit portfolio dashboard.

Displays:
- Portfolio KPIs
- Retention priority distribution
- Customer segment performance
- High-value inactive customers
- Backend/artifact health

Run:
    streamlit run frontend/app.py
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from api_client import (
    APIClientError,
    api_client,

)


# ---------------------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="E-Commerce Intelligence Dashboard",
    page_icon="📊",
    layout="wide",
)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_business_summary() -> dict:
    """Load portfolio KPIs from FastAPI."""
    return api_client.business_summary()


@st.cache_data(ttl=60)
def load_retention_priorities() -> list[dict]:
    """Load retention priority metrics."""
    return api_client.retention_priorities()


@st.cache_data(ttl=60)
def load_segment_summary() -> list[dict]:
    """Load segment metrics."""
    return api_client.segment_summary()


@st.cache_data(ttl=60)
def load_high_value_inactive(limit: int = 25) -> list[dict]:
    """Load high-value inactive customers."""
    return api_client.high_value_inactive(limit=limit)


@st.cache_data(ttl=30)
def load_health() -> dict:
    """Load backend health."""
    return api_client.health()


@st.cache_data(ttl=30)
def load_artifact_health() -> dict:
    """Load analytical artifact health."""
    return api_client.artifact_health()


def money(value: float | int | None) -> str:
    """Format monetary values for dashboard display."""
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


def clear_dashboard_cache() -> None:
    """Clear cached dashboard API responses."""
    load_business_summary.clear()
    load_retention_priorities.clear()
    load_segment_summary.clear()
    load_high_value_inactive.clear()
    load_health.clear()
    load_artifact_health.clear()


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------

st.title("📊 E-Commerce Intelligence Dashboard")

st.markdown(
    """
    <div style="color:#6b7280; font-size:1rem; margin-bottom:1rem;">
        Executive view of customer value, segmentation, retention risk,
        and revenue opportunity.
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("Dashboard Controls")

    if st.button(
        "↻ Refresh Data",
        use_container_width=True,
    ):
        clear_dashboard_cache()
        st.rerun()

    st.divider()

    st.caption("Data is served by the FastAPI backend.")
    st.caption(
        "Analytical metrics come from the project's processed artifacts."
    )


# ---------------------------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------------------------

try:
    summary = load_business_summary()
    priorities = load_retention_priorities()
    segments = load_segment_summary()
    inactive = load_high_value_inactive(25)
    health = load_health()
    artifacts = load_artifact_health()

except APIClientError as exc:
    st.error("Unable to load dashboard data.")
    st.code(str(exc))
    st.info(
        "Make sure FastAPI is running at the BACKEND_URL configured "
        "for the Streamlit application."
    )
    st.stop()


# ---------------------------------------------------------------------------
# KPI CARDS
# ---------------------------------------------------------------------------

st.subheader("Portfolio Overview")

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

with kpi1:
    st.metric(
        "Customers",
        f"{summary.get('customer_count', 0):,}",
    )

with kpi2:
    st.metric(
        "Predicted Future Revenue",
        money(
            summary.get(
                "predicted_future_revenue",
                0,
            )
        ),
    )

with kpi3:
    st.metric(
        "Average Customer Value",
        money(
            summary.get(
                "average_predicted_customer_value",
                0,
            )
        ),
    )

with kpi4:
    st.metric(
        "Critical Customers",
        f"{summary.get('critical_retention_customers', 0):,}",
    )

with kpi5:
    st.metric(
        "High Priority",
        f"{summary.get('high_retention_customers', 0):,}",
    )


# ---------------------------------------------------------------------------
# CHARTS
# ---------------------------------------------------------------------------

left, right = st.columns(2)

with left:
    st.subheader("Retention Priority")

    priority_df = pd.DataFrame(priorities)

    if priority_df.empty:
        st.info("No retention priority data available.")
    else:
        priority_order = [
            "Critical",
            "High",
            "Medium",
            "Low",
        ]

        priority_df["sort_order"] = (
            priority_df["retention_priority"]
            .map(
                {
                    name: index
                    for index, name in enumerate(
                        priority_order
                    )
                }
            )
            .fillna(99)
        )

        priority_df = (
            priority_df
            .sort_values("sort_order")
            .drop(columns="sort_order")
        )

        fig = px.bar(
            priority_df,
            x="retention_priority",
            y="customers",
            text="customers",
            labels={
                "retention_priority": "Priority",
                "customers": "Customers",
            },
        )

        fig.update_layout(
            height=380,
            margin=dict(
                l=20,
                r=20,
                t=30,
                b=20,
            ),
            showlegend=False,
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

with right:
    st.subheader("Customer Segments")

    segment_df = pd.DataFrame(segments)

    if segment_df.empty:
        st.info("No segment data available.")
    else:
        fig = px.bar(
            segment_df,
            x="segment",
            y="total_revenue",
            text="total_revenue",
            labels={
                "segment": "Segment",
                "total_revenue": "Revenue",
            },
        )

        fig.update_layout(
            height=380,
            margin=dict(
                l=20,
                r=20,
                t=30,
                b=20,
            ),
            showlegend=False,
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# ---------------------------------------------------------------------------
# REVENUE / SEGMENT TABLE
# ---------------------------------------------------------------------------

st.subheader("Segment Business Performance")

if segment_df.empty:
    st.info("No segment metrics are available.")
else:
    display_columns = [
        "segment",
        "customers",
        "total_revenue",
        "average_revenue",
        "average_recency_days",
        "average_order_count",
        "customer_share_pct",
        "revenue_share_pct",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in segment_df.columns
    ]

    display_df = segment_df[
        available_columns
    ].copy()

    if "total_revenue" in display_df.columns:
        display_df["total_revenue"] = (
            display_df["total_revenue"]
            .map(money)
        )

    if "average_revenue" in display_df.columns:
        display_df["average_revenue"] = (
            display_df["average_revenue"]
            .map(money)
        )

    if "average_recency_days" in display_df.columns:
        display_df["average_recency_days"] = (
            display_df["average_recency_days"]
            .round(1)
        )

    if "average_order_count" in display_df.columns:
        display_df["average_order_count"] = (
            display_df["average_order_count"]
            .round(2)
        )

    if "customer_share_pct" in display_df.columns:
        display_df["customer_share_pct"] = (
            display_df["customer_share_pct"]
            .round(1)
            .astype(str)
            + "%"
        )

    if "revenue_share_pct" in display_df.columns:
        display_df["revenue_share_pct"] = (
            display_df["revenue_share_pct"]
            .round(1)
            .astype(str)
            + "%"
        )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# HIGH-VALUE INACTIVE CUSTOMERS
# ---------------------------------------------------------------------------

st.subheader("🎯 High-Value Inactive Customers")

inactive_df = pd.DataFrame(inactive)

if inactive_df.empty:
    st.success(
        "No high-value inactive customers were identified."
    )
else:
    inactive_columns = [
        "customer_unique_id",
        "predicted_future_revenue",
        "recency_days",
        "order_count",
        "retention_priority",
        "recommended_action",
        "opportunity_score",
    ]

    available_columns = [
        column
        for column in inactive_columns
        if column in inactive_df.columns
    ]

    inactive_display = inactive_df[
        available_columns
    ].copy()

    if "predicted_future_revenue" in inactive_display.columns:
        inactive_display[
            "predicted_future_revenue"
        ] = (
            inactive_display[
                "predicted_future_revenue"
            ]
            .map(money)
        )

    if "recency_days" in inactive_display.columns:
        inactive_display["recency_days"] = (
            inactive_display["recency_days"]
            .round(0)
        )

    if "opportunity_score" in inactive_display.columns:
        inactive_display["opportunity_score"] = (
            inactive_display["opportunity_score"]
            .round(3)
        )

    st.dataframe(
        inactive_display,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# SYSTEM STATUS
# ---------------------------------------------------------------------------

with st.expander("System & Artifact Status"):
    status1, status2 = st.columns(2)

    with status1:
        st.markdown("**Backend**")

        backend_status = health.get(
            "status",
            "unknown",
        )

        if backend_status == "healthy":
            st.success("FastAPI backend is healthy.")
        else:
            st.warning(
                f"Backend status: {backend_status}"
            )

        st.json(health)

    with status2:
        st.markdown("**Analytical Artifacts**")

        artifact_status = artifacts.get(
            "status",
            "unknown",
        )

        if artifact_status == "ready":
            st.success(
                "All expected artifacts are available."
            )
        else:
            st.warning(
                "Some analytical artifacts are missing."
            )

        st.json(artifacts)
