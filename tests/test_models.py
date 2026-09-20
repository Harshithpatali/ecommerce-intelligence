import numpy as np
import pandas as pd
import pytest

from backend.services.prediction_service import PredictionService


def test_prepare_features_rejects_missing_features(monkeypatch):
    monkeypatch.setattr(PredictionService, "_features", ["feature_a", "feature_b"])
    monkeypatch.setattr(PredictionService, "_model", object())
    with pytest.raises(ValueError, match="Missing required prediction features"):
        PredictionService._prepare_features(pd.DataFrame({"feature_a": [1]}))


def test_prepare_features_converts_numeric_and_imputes(monkeypatch):
    monkeypatch.setattr(PredictionService, "_features", ["feature_a", "feature_b"])
    monkeypatch.setattr(PredictionService, "_model", object())
    data = pd.DataFrame({"feature_a": ["1.0", "2.0"], "feature_b": [np.nan, "4.0"]})
    prepared = PredictionService._prepare_features(data)
    assert prepared["feature_a"].dtype.kind in "fi"
    assert prepared["feature_b"].dtype.kind in "fi"
    assert np.isfinite(prepared.to_numpy()).all()
    assert prepared.loc[0, "feature_b"] == pytest.approx(4.0)


def test_prepare_features_rejects_all_null_column(monkeypatch):
    monkeypatch.setattr(PredictionService, "_features", ["feature_a"])
    monkeypatch.setattr(PredictionService, "_model", object())
    with pytest.raises(ValueError, match="Unable to prepare numeric values"):
        PredictionService._prepare_features(pd.DataFrame({"feature_a": [None, None]}))
