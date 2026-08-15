# E-Commerce Intelligence Streamlit Frontend

This directory contains the Streamlit presentation layer for the
E-Commerce Customer & Product Intelligence platform.

The frontend communicates with FastAPI through `api_client.py`.
It does not load the XGBoost model, execute SHAP calculations, call Groq
directly, or contain database credentials.

## Run from project root

```powershell
streamlit run frontend/app.py
```

## Backend requirement

Start FastAPI separately:

```powershell
uvicorn backend.main:app --reload
```

The default backend URL is:

```text
http://localhost:8000
```

For another backend URL, set:

```text
BACKEND_URL=https://your-render-api.onrender.com
```

## Pages

```text
pages/
├── 1_Dashboard.py
├── 2_Customers.py
├── 3_CLV_Prediction.py
├── 4_Explainability.py
├── 5_Recommendations.py
├── 6_Retention.py
└── 7_AI_Insights.py
```

### Dashboard

Executive portfolio view containing:

- customer count
- predicted future revenue
- average customer value
- retention priorities
- segment performance
- high-value inactive customers
- backend/artifact health

### Customers

Customer-level intelligence:

- CLV
- recency
- orders
- opportunity score
- retention recommendation
- purchase history
- personalized recommendations

### CLV Prediction

Interactive single-customer prediction using the eight CLV model features.

### Explainability

Local and global SHAP visualizations.

### Recommendations

Personalized and precomputed product recommendations.

### Retention

Portfolio retention priorities, actions, and high-value inactive customers.

### AI Insights

Groq-powered executive and customer-level natural-language insights.

## Architecture

```text
                    Streamlit
                        |
                  api_client.py
                        |
                        v
                     FastAPI
                        |
       +----------------+----------------+
       |                |                |
       v                v                v
   XGBoost            SHAP       Recommendation
       |                |                |
       +----------------+----------------+
                        |
                 Business Services
                        |
                        v
                    Groq AI
```

## Development rules

1. Keep ML logic in `backend/services/`.
2. Keep HTTP routes in `backend/api/`.
3. Keep Streamlit presentation logic in `frontend/`.
4. Do not put API keys in Streamlit source code.
5. Do not call Groq directly from Streamlit.
6. Do not duplicate model preprocessing in the frontend.
7. Use `api_client.py` for backend communication.

## Production

The Streamlit frontend can be deployed separately from the FastAPI backend.

Set the production environment variable:

```text
BACKEND_URL=https://<your-render-backend>.onrender.com
```

The frontend should never require the backend's `GROQ_API_KEY`.
