"""
Streamlit Retention Intelligence page.

Features:
- Portfolio-level retention priorities.
- Recommended retention actions.
- High-value inactive customer list.
- Customer-specific retention intelligence.
- Revenue-at-risk style business context when supplied by FastAPI.

All analytical calculations remain in the backend.
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
    page_title="Retention | E-Commerce Intelligence",
    page_icon="🎯",
    layout="wide",
)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_priorities() -> list[dict]:
    """Load portfolio retention priorities."""
    return api_client.retention_priorities()


@st.cache_data(ttl=60)
def load_actions() -> list[dict]:
    """Load portfolio retention actions."""
    return api_client.retention_actions()


@st.cache_data(ttl=60)
def load_inactive(
    limit: int = 50,
) -> list[dict]:
    """Load high-value inactive customers."""
    return api_client.high_value_inactive(
        limit=limit
    )


@st.cache_data(ttl=60)
def load_customer(
    customer_id: str,
) -> dict:
    """Load customer-specific retention intelligence."""
    return api_client.customer_business_intelligence(
        customer_id
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


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------

st.title("🎯 Retention Intelligence")

st.markdown(
    """
    Identify customers who represent the strongest retention opportunities
    and translate analytical signals into actionable business priorities.
    """
)


# ---------------------------------------------------------------------------
# LOAD PORTFOLIO DATA
# ---------------------------------------------------------------------------

try:
    with st.spinner(
        "Loading retention intelligence..."
    ):
        priorities = load_priorities()
        actions = load_actions()
        inactive = load_inactive(50)

except APIClientError as exc:
    st.error(
        "Unable to load retention intelligence."
    )
    st.code(str(exc))
    st.stop()


priority_df = pd.DataFrame(
    priorities
)

action_df = pd.DataFrame(
    actions
)

inactive_df = pd.DataFrame(
    inactive
)


# ---------------------------------------------------------------------------
# PORTFOLIO RETENTION PRIORITIES
# ---------------------------------------------------------------------------

st.subheader("Portfolio Retention Priorities")

if priority_df.empty:
    st.info(
        "No retention-priority data is available."
    )
else:
    priority_count_col = None

    for candidate in [
        "customers",
        "customer_count",
        "count",
    ]:
        if candidate in priority_df.columns:
            priority_count_col = candidate
            break

    if (
        priority_count_col is not None
        and "retention_priority"
        in priority_df.columns
    ):
        chart_df = priority_df.copy()

        chart_df[priority_count_col] = pd.to_numeric(
            chart_df[priority_count_col],
            errors="coerce",
        )

        fig = px.bar(
            chart_df,
            x="retention_priority",
            y=priority_count_col,
            text=priority_count_col,
            labels={
                "retention_priority": "Priority",
                priority_count_col: "Customers",
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

    st.dataframe(
        priority_df,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# RETENTION ACTIONS
# ---------------------------------------------------------------------------

st.subheader("Recommended Retention Actions")

if action_df.empty:
    st.info(
        "No retention actions are available."
    )
else:
    st.dataframe(
        action_df,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# HIGH-VALUE INACTIVE CUSTOMERS
# ---------------------------------------------------------------------------

st.divider()

st.subheader(
    "🔥 High-Value Inactive Customers"
)

st.markdown(
    """
    These customers combine historical activity or predicted future value
    with inactivity signals and are therefore strong candidates for
    retention outreach.
    """
)

if inactive_df.empty:
    st.success(
        "No high-value inactive customers were returned."
    )
else:
    display_columns = [
        "customer_unique_id",
        "predicted_future_revenue",
        "historical_revenue",
        "recency_days",
        "order_count",
        "retention_priority",
        "recommended_action",
        "opportunity_score",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in inactive_df.columns
    ]

    display_df = inactive_df[
        available_columns
    ].copy()

    if "predicted_future_revenue" in display_df.columns:
        display_df[
            "predicted_future_revenue"
        ] = pd.to_numeric(
            display_df[
                "predicted_future_revenue"
            ],
            errors="coerce",
        )

        display_df[
            "predicted_future_revenue"
        ] = display_df[
            "predicted_future_revenue"
        ].map(
            money
        )

    if "historical_revenue" in display_df.columns:
        display_df[
            "historical_revenue"
        ] = pd.to_numeric(
            display_df[
                "historical_revenue"
            ],
            errors="coerce",
        ).map(
            money
        )

    if "recency_days" in display_df.columns:
        display_df["recency_days"] = pd.to_numeric(
            display_df["recency_days"],
            errors="coerce",
        ).round(0)

    if "order_count" in display_df.columns:
        display_df["order_count"] = pd.to_numeric(
            display_df["order_count"],
            errors="coerce",
        ).round(0)

    if "opportunity_score" in display_df.columns:
        display_df["opportunity_score"] = pd.to_numeric(
            display_df["opportunity_score"],
            errors="coerce",
        ).round(3)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# CUSTOMER-SPECIFIC RETENTION ANALYSIS
# ---------------------------------------------------------------------------

st.divider()

st.subheader("Customer Retention Analysis")

customer_id = st.text_input(
    "Customer Unique ID",
    value=st.session_state.get(
        "selected_customer_id",
        "",
    ) or "",
    placeholder="Enter customer_unique_id",
)

if st.button(
    "Analyze Customer",
    type="primary",
):
    if not customer_id.strip():
        st.warning(
            "Please enter a customer ID."
        )
    else:
        st.session_state.selected_customer_id = (
            customer_id.strip()
        )

        try:
            with st.spinner(
                "Analyzing customer retention opportunity..."
            ):
                customer = load_customer(
                    st.session_state.selected_customer_id
                )

        except APIClientError as exc:
            st.error(
                "Unable to analyze this customer."
            )
            st.code(str(exc))
            customer = None

        if customer:
            priority = customer.get(
                "retention_priority",
                "Unknown",
            )

            st.subheader(
                f"Retention Profile: "
                f"{st.session_state.selected_customer_id}"
            )

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.metric(
                    "Predicted Future Revenue",
                    money(
                        customer.get(
                            "predicted_future_revenue"
                        )
                    ),
                )

            with c2:
                st.metric(
                    "Recency",
                    (
                        f"{float(customer.get('recency_days', 0)):,.0f} days"
                        if customer.get(
                            "recency_days"
                        ) is not None
                        else "—"
                    ),
                )

            with c3:
                st.metric(
                    "Orders",
                    (
                        f"{float(customer.get('order_count', 0)):,.0f}"
                        if customer.get(
                            "order_count"
                        ) is not None
                        else "—"
                    ),
                )

            with c4:
                score = customer.get(
                    "opportunity_score"
                )

                st.metric(
                    "Opportunity Score",
                    (
                        f"{float(score):.3f}"
                        if score is not None
                        else "—"
                    ),
                )

            if priority == "Critical":
                st.error(
                    f"Retention Priority: {priority}"
                )
            elif priority == "High":
                st.warning(
                    f"Retention Priority: {priority}"
                )
            elif priority == "Medium":
                st.info(
                    f"Retention Priority: {priority}"
                )
            else:
                st.success(
                    f"Retention Priority: {priority}"
                )

            action = customer.get(
                "recommended_action"
            )

            reason = customer.get(
                "recommendation_reason"
            )

            strategy = customer.get(
                "retention_strategy"
            )

            action_col, reason_col = st.columns(2)

            with action_col:
                st.markdown(
                    "**Recommended Action**"
                )
                st.write(
                    action
                    or "No action provided."
                )

            with reason_col:
                st.markdown(
                    "**Reason**"
                )
                st.write(
                    reason
                    or "No reason provided."
                )

            if strategy:
                st.markdown(
                    "**Retention Strategy**"
                )
                st.write(strategy)

            with st.expander(
                "View Customer Retention Payload"
            ):
                st.json(customer)
