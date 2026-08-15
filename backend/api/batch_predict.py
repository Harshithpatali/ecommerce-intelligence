"""
FastAPI CSV batch prediction endpoint.

Endpoint:
    POST /api/v1/predict/file

The endpoint accepts a CSV upload, validates the required CLV model
features, runs the existing PredictionService, and returns a CSV file
containing the original rows plus predicted_future_revenue.

The endpoint does not retrain or modify the model.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from backend.services.prediction_service import PredictionService


router = APIRouter()


MODEL_FEATURES = [
    "historical_recency_days",
    "historical_order_count",
    "historical_revenue",
    "historical_item_count",
    "historical_unique_products",
    "historical_average_order_value",
    "historical_average_items_per_order",
    "historical_orders_per_active_day",
]

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100_000


@router.post(
    "/file",
    summary="Predict CLV for an uploaded CSV",
)
async def predict_csv(
    file: UploadFile = File(...),
):
    """
    Upload a customer-feature CSV and return predictions as a CSV file.

    Required columns:
        historical_recency_days
        historical_order_count
        historical_revenue
        historical_item_count
        historical_unique_products
        historical_average_order_value
        historical_average_items_per_order
        historical_orders_per_active_day

    An optional customer_id column is preserved in the output.
    """
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="A CSV file is required.",
        )

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=415,
            detail="Only CSV files are supported.",
        )

    try:
        raw = await file.read()

        if len(raw) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    "File is too large. "
                    "Maximum supported size is 10 MB."
                ),
            )

        if not raw:
            raise HTTPException(
                status_code=400,
                detail="Uploaded CSV is empty.",
            )

        try:
            dataframe = pd.read_csv(
                io.BytesIO(raw)
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Unable to parse CSV: {exc}",
            ) from exc

        if dataframe.empty:
            raise HTTPException(
                status_code=400,
                detail="CSV contains no data rows.",
            )

        if len(dataframe) > MAX_ROWS:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"CSV contains {len(dataframe):,} rows. "
                    f"Maximum supported rows: {MAX_ROWS:,}."
                ),
            )

        missing_columns = [
            column
            for column in MODEL_FEATURES
            if column not in dataframe.columns
        ]

        if missing_columns:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "CSV is missing required model features.",
                    "missing_columns": missing_columns,
                },
            )

        # Validate model input columns explicitly before inference.
        for column in MODEL_FEATURES:
            dataframe[column] = pd.to_numeric(
                dataframe[column],
                errors="coerce",
            )

        invalid_counts = {
            column: int(
                dataframe[column].isna().sum()
            )
            for column in MODEL_FEATURES
            if dataframe[column].isna().any()
        }

        if invalid_counts:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "CSV contains missing or non-numeric "
                        "values in model features."
                    ),
                    "invalid_value_counts": invalid_counts,
                },
            )

        negative_columns = {}

        non_negative_features = [
            "historical_recency_days",
            "historical_order_count",
            "historical_revenue",
            "historical_item_count",
            "historical_unique_products",
            "historical_average_order_value",
            "historical_average_items_per_order",
            "historical_orders_per_active_day",
        ]

        for column in non_negative_features:
            count = int(
                (dataframe[column] < 0).sum()
            )

            if count:
                negative_columns[column] = count

        if negative_columns:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Model features cannot contain negative values."
                    ),
                    "negative_value_counts": negative_columns,
                },
            )

        try:
            result = PredictionService.predict_dataframe(
                dataframe
            )

        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=503,
                detail=str(exc),
            ) from exc

        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        output = io.StringIO()

        result.to_csv(
            output,
            index=False,
        )

        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": (
                    'attachment; filename="clv_predictions.csv"'
                ),
                "X-Rows-Processed": str(
                    len(result)
                ),
            },
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="CSV prediction service failed.",
        ) from exc
