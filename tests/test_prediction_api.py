from pathlib import Path

import neurokit2 as nk
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.database import Base
from app.main import create_app
from app.ml.model_loader import load_model_package
from app.schemas.requests import ECGPredictionRequest


@pytest.fixture
def real_package():
    return load_model_package(Path("app/models/ecg_apnea_hrv_lr_v2.joblib"))


@pytest.fixture
def real_signal():
    return nk.ecg_simulate(duration=60, sampling_rate=100, heart_rate=70, random_state=47)


@pytest.fixture
def real_client(real_package):
    application = create_app(
        package=real_package,
        settings=Settings(
            app_env="test",
            database_url="sqlite+pysqlite:///:memory:",
        ),
        load_artifact=False,
    )
    Base.metadata.create_all(application.state.database_engine)
    with TestClient(application, base_url="https://testserver") as client:
        yield client


def test_request_schema_rejects_removed_explanation_options():
    request_data = {"sampling_rate": 100, "ecg_samples": [0.1]}
    request = ECGPredictionRequest.model_validate(request_data)
    assert request.include_features is False

    for removed_option in ("include_explanation", "include_ai_explanation"):
        with pytest.raises(ValidationError):
            ECGPredictionRequest.model_validate({**request_data, removed_option: True})


def test_prediction_and_optional_hrv_features_remain_available(real_client, real_signal):
    payload = {"sampling_rate": 100, "ecg_samples": real_signal.tolist()}
    default_response = real_client.post("/api/v1/predict", json=payload)
    features_response = real_client.post(
        "/api/v1/predict",
        json={**payload, "include_features": True},
    )

    assert default_response.status_code == features_response.status_code == 200
    default_result = default_response.json()
    features_result = features_response.json()
    assert features_result["result"] == default_result["result"]
    assert features_result["signal_quality"] == default_result["signal_quality"]
    assert len(features_result["features"]) == 13
    assert "features" not in default_result
    assert not any("explanation" in key for key in default_result)
    assert not any("explanation" in key for key in features_result)


def test_recording_preserves_prediction_and_rejection_results(real_client, real_signal):
    response = real_client.post(
        "/api/v1/analyze-samples",
        json={
            "sampling_rate": 100,
            "ecg_samples": [1.0] * 6000 + real_signal.tolist(),
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["summary"]["total_windows"] == 2
    assert result["summary"]["rejected_windows"] == 1
    assert result["windows"][0]["status"] == "rejected"
    assert result["windows"][1]["status"] == "success"
    assert all("explanation" not in window for window in result["windows"])
    assert not any("explanation" in key for key in result)


def test_file_analysis_preserves_optional_hrv_features(real_client, real_signal):
    file_content = "ecg\n" + "\n".join(str(value) for value in real_signal)
    response = real_client.post(
        "/api/v1/analyze-file",
        files={"file": ("signal.csv", file_content.encode("utf-8"))},
        data={"sampling_rate": "100", "include_features": "true"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["windows"][0]["status"] == "success"
    assert len(result["windows"][0]["features"]) == 13
    assert not any("explanation" in key for key in result)
    assert all("explanation" not in window for window in result["windows"])
