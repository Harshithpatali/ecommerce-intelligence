"""
Streamlit frontend entry point.

Run from the project root:

    streamlit run frontend/app.py

The page files intentionally use simple ASCII filenames so Streamlit page
discovery works reliably across Windows, Git, and deployment environments.
"""

from __future__ import annotations

import os

import streamlit as st


# ---------------------------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="E-Commerce Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------------------

if "selected_customer_id" not in st.session_state:
    st.session_state.selected_customer_id = None


# ---------------------------------------------------------------------------
# CUSTOM CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }

        [data-testid="stMetric"] {
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 12px;
            padding: 1rem;
        }

        .app-subtitle {
            color: #6b7280;
            font-size: 1rem;
            margin-top: -0.5rem;
            margin-bottom: 1.5rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("📊 E-Commerce")
    st.caption("Customer & Product Intelligence")

    st.divider()

    st.markdown("### Navigation")

    st.page_link(
        "app.py",
        label="Dashboard",
        icon="📊",
    )

    st.page_link(
        "pages/2_Customers.py",
        label="Customers",
        icon="👥",
    )

    st.page_link(
        "pages/3_CLV_Prediction.py",
        label="CLV Prediction",
        icon="🔮",
    )

    st.page_link(
        "pages/4_Explainability.py",
        label="Explainability",
        icon="🔍",
    )

    st.page_link(
        "pages/5_Recommendations.py",
        label="Recommendations",
        icon="🛍️",
    )

    st.page_link(
        "pages/6_Retention.py",
        label="Retention",
        icon="🎯",
    )

    st.page_link(
        "pages/7_AI_Insights.py",
        label="AI Insights",
        icon="🤖",
    )

    st.divider()

    backend_url = os.getenv(
        "BACKEND_URL",
        "http://localhost:8000",
    )

    st.caption("Backend")
    st.code(
        backend_url,
        language=None,
    )


# ---------------------------------------------------------------------------
# DASHBOARD LANDING PAGE
# ---------------------------------------------------------------------------

st.title("E-Commerce Customer & Product Intelligence")

st.markdown(
    '<div class="app-subtitle">'
    "A production-style analytics dashboard powered by FastAPI, "
    "XGBoost, SHAP, recommendation systems, and Groq AI."
    "</div>",
    unsafe_allow_html=True,
)

st.info(
    "Select a module from the sidebar to explore the intelligence platform."
)


# ---------------------------------------------------------------------------
# ARCHITECTURE OVERVIEW
# ---------------------------------------------------------------------------

st.subheader("Application Architecture")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📈 Analytics")
    st.write(
        "Customer segmentation, CLV prediction, retention analytics, "
        "and business KPIs."
    )

with col2:
    st.markdown("### 🧠 Explainable AI")
    st.write(
        "SHAP-based customer explanations and transparent model drivers."
    )

with col3:
    st.markdown("### 🤖 AI Insights")
    st.write(
        "Groq-powered natural-language interpretation of trusted "
        "analytical outputs."
    )


# ---------------------------------------------------------------------------
# SYSTEM STATUS
# ---------------------------------------------------------------------------

st.subheader("System")

status_col1, status_col2 = st.columns(2)

with status_col1:
    st.metric(
        "Frontend",
        "Online",
    )

with status_col2:
    st.metric(
        "Backend",
        "FastAPI",
    )

st.caption(
    "Analytical and ML logic remains in the FastAPI backend."
)
