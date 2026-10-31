import json
from pathlib import Path
from types import SimpleNamespace

import neurokit2 as nk
import pytest
from google.genai import errors
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import routes
from app.core.config import Settings
from app.core.exceptions import (
    MathematicalExplanationError,
    ModelUnavailableError,
    SignalRejectedError,
)
from app.main import create_app
from app.ml.model_loader import load_model_package
from app.schemas.requests import ECGPredictionRequest, LongECGRequest
from app.schemas.responses import AI_EXPLANATION_DISCLAIMER, AIExplanation
from app.schemas.responses import PredictionExplanation, PredictionResponse
from app.services import ai_explanation_service
from app.services import ecg_service


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
        settings=Settings(gemini_api_key=None, gemini_model=None),
        load_artifact=False,
    )
    with TestClient(application) as client:
        yield client


def _without_explanations(value):
    if isinstance(value, dict):
        return {
            key: _without_explanations(nested)
            for key, nested in value.items()
            if key != "explanation"
        }
    if isinstance(value, list):
        return [_without_explanations(item) for item in value]
    return value


def _assert_explanation(explanation):
    parsed = PredictionExplanation.model_validate(explanation)
    assert parsed.class_label == "A"
    assert len(parsed.features) == 13


def _ai_payload(context):
    features = []
    if "mathematical_explanation" in context:
        features.extend(context["mathematical_explanation"]["features"])
    if "aggregate_features" in context:
        features.extend(context["aggregate_features"])
    else:
        for window in context.get("evidence_windows", []):
            features.extend(window["mathematical_explanation"]["features"])
    supporting = next(
        (item["feature_name"] for item in features if item["direction"] == "toward_apnea"),
        None,
    )
    opposing = next(
        (item["feature_name"] for item in features if item["direction"] == "away_from_apnea"),
        None,
    )
    return {
        "headline": "The model output favors the apnea-related class",
        "summary": "The supplied model evidence favors class A for this window.",
        "supporting_factors": [
            f"{supporting} contributes toward the apnea-related class."
        ] if supporting else [],
        "opposing_factors": [
            f"{opposing} contributes away from the apnea-related class."
        ] if opposing else [],
        "limitations": ["The model output is limited to this screening window."],
        "disclaimer": "This provider-supplied disclaimer is ignored.",
    }


class MockGeminiClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.models = self

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        context = json.loads(kwargs["contents"].rsplit("\n", 1)[1])
        response = self.response if self.response is not None else _ai_payload(context)
        return SimpleNamespace(text=json.dumps(response))

    def close(self):
        pass


def _mock_gemini(monkeypatch, response=None, error=None):
    client = MockGeminiClient(response, error)
    monkeypatch.setattr(ai_explanation_service, "_client", lambda settings: client)
    return client


def test_request_schemas_default_and_forbid_extra_fields():
    request_data = {"sampling_rate": 100, "ecg_samples": [0.1]}
    single_request = ECGPredictionRequest.model_validate(request_data)
    recording_request = LongECGRequest.model_validate(request_data)
    assert single_request.include_explanation is False
    assert single_request.include_ai_explanation is False
    assert recording_request.include_explanation is False
    assert recording_request.include_ai_explanation is False

    with pytest.raises(ValidationError):
        ECGPredictionRequest.model_validate({**request_data, "unexpected": True})


def test_predict_explanation_is_opt_in_and_features_remain_independent(real_client, real_signal):
    payload = {"sampling_rate": 100, "ecg_samples": real_signal.tolist()}
    default_response = real_client.post("/api/v1/predict", json=payload)
    features_response = real_client.post(
        "/api/v1/predict",
        json={**payload, "include_features": True},
    )
    explanation_response = real_client.post(
        "/api/v1/predict",
        json={**payload, "include_explanation": True},
    )

    assert default_response.status_code == features_response.status_code == explanation_response.status_code == 200
    default_result = default_response.json()
    features_result = features_response.json()
    explanation_result = explanation_response.json()
    assert "explanation" not in default_result
    assert "ai_explanation" not in default_result
    assert "ai_explanation_status" not in default_result
    assert "explanation" not in features_result
    assert PredictionResponse.model_validate(default_result).explanation is None
    assert len(features_result["features"]) == 13
    _assert_explanation(explanation_result["explanation"])
    assert PredictionResponse.model_validate(explanation_result).explanation is not None
    assert _without_explanations(explanation_result) == default_result


def test_predict_ai_explanation_is_opt_in_and_independent(real_client, real_signal, monkeypatch):
    client = _mock_gemini(monkeypatch)
    payload = {"sampling_rate": 100, "ecg_samples": real_signal.tolist()}
    default_response = real_client.post("/api/v1/predict", json=payload)
    math_response = real_client.post(
        "/api/v1/predict",
        json={**payload, "include_explanation": True},
    )
    assert len(client.calls) == 0
    ai_response = real_client.post(
        "/api/v1/predict",
        json={**payload, "include_ai_explanation": True},
    )

    assert default_response.status_code == math_response.status_code == ai_response.status_code == 200
    default = default_response.json()
    math_only = math_response.json()
    ai_only = ai_response.json()
    assert "ai_explanation" not in default
    assert "ai_explanation" not in math_only
    assert "explanation" in math_only and "ai_explanation" not in math_only
    assert "explanation" not in ai_only
    assert AIExplanation.model_validate(ai_only["ai_explanation"]).headline == _ai_payload({})["headline"]
    assert ai_only["ai_explanation"]["disclaimer"] == AI_EXPLANATION_DISCLAIMER
    assert ai_only["ai_explanation_status"] == {"status": "available", "code": None}
    assert ai_only["result"] == default["result"]
    assert len(client.calls) == 1
    sent_context = json.loads(client.calls[0]["contents"].rsplit("\n", 1)[1])
    assert len(sent_context["mathematical_explanation"]["features"]) == 13
    assert "ecg_samples" not in sent_context


def test_predict_gemini_failure_preserves_prediction(real_client, real_signal, monkeypatch):
    client = _mock_gemini(
        monkeypatch,
        error=errors.APIError(403, {"status": "PERMISSION_DENIED", "message": "secret provider detail"}),
    )
    payload = {"sampling_rate": 100, "ecg_samples": real_signal.tolist()}
    math_only = real_client.post(
        "/api/v1/predict",
        json={**payload, "include_explanation": True},
    ).json()
    requested = real_client.post(
        "/api/v1/predict",
        json={
            **payload,
            "include_explanation": True,
            "include_ai_explanation": True,
        },
    )

    assert requested.status_code == 200
    result = requested.json()
    assert result["result"] == math_only["result"]
    assert result["explanation"] == math_only["explanation"]
    assert result["ai_explanation"] is None
    assert result["ai_explanation_status"] == {
        "status": "unavailable",
        "code": "authentication_failed",
    }
    assert "secret provider detail" not in requested.text
    assert len(client.calls) == 1


def test_predict_ai_missing_credentials_is_reported_without_provider_call(real_client, real_signal):
    response = real_client.post(
        "/api/v1/predict",
        json={
            "sampling_rate": 100,
            "ecg_samples": real_signal.tolist(),
            "include_ai_explanation": True,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["ai_explanation"] is None
    assert result["ai_explanation_status"]["code"] == "missing_api_key"


def test_ai_explanation_is_unavailable_without_mathematical_xai(package, real_signal):
    application = create_app(
        package=package,
        settings=Settings(gemini_api_key="test-key", gemini_model="configured-test-model"),
        load_artifact=False,
    )
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/predict",
            json={
                "sampling_rate": 100,
                "ecg_samples": real_signal.tolist(),
                "include_ai_explanation": True,
            },
        )

    assert response.status_code == 200
    result = response.json()
    assert result["result"]["apnea_class_score"] == 0.5398
    assert "explanation" not in result
    assert result["ai_explanation"] is None
    assert result["ai_explanation_status"]["code"] == "mathematical_explanation_unavailable"


def test_xai_only_failure_preserves_prediction_when_ai_is_requested(
    real_client,
    real_signal,
    monkeypatch,
):
    baseline = real_client.post(
        "/api/v1/predict",
        json={"sampling_rate": 100, "ecg_samples": real_signal.tolist()},
    ).json()
    original_predict = routes.predict_apnea_from_ecg
    calls = []

    def fail_explanation_once(signal, package, **kwargs):
        calls.append(kwargs.get("include_explanation", False))
        if kwargs.get("include_explanation"):
            raise MathematicalExplanationError("explanation evidence is incompatible")
        return original_predict(signal, package, **kwargs)

    monkeypatch.setattr(routes, "predict_apnea_from_ecg", fail_explanation_once)
    response = real_client.post(
        "/api/v1/predict",
        json={
            "sampling_rate": 100,
            "ecg_samples": real_signal.tolist(),
            "include_ai_explanation": True,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["result"] == baseline["result"]
    assert result["ai_explanation"] is None
    assert result["ai_explanation_status"]["code"] == "mathematical_explanation_unavailable"
    assert calls == [True, False]


def test_model_unavailable_error_is_not_retried_as_xai_failure(
    real_client,
    real_signal,
    monkeypatch,
):
    calls = []

    def fail_prediction(*args, **kwargs):
        calls.append(kwargs.get("include_explanation", False))
        raise ModelUnavailableError("the prediction model is unavailable")

    monkeypatch.setattr(routes, "predict_apnea_from_ecg", fail_prediction)
    response = real_client.post(
        "/api/v1/predict",
        json={
            "sampling_rate": 100,
            "ecg_samples": real_signal.tolist(),
            "include_ai_explanation": True,
        },
    )

    assert response.status_code == 503
    assert response.json()["code"] == "MODEL_UNAVAILABLE"
    assert calls == [True]


def test_recording_xai_failure_preserves_successful_window_prediction(package, monkeypatch):
    calls = []

    def fail_explanation_once(signal, model_package, **kwargs):
        calls.append(kwargs.get("include_explanation", False))
        if kwargs.get("include_explanation"):
            raise MathematicalExplanationError("explanation evidence is incompatible")
        return {
            "status": "success",
            "result": {
                "class": "A",
                "label": "Apnea-related pattern detected",
                "apnea_class_score": 0.62,
                "threshold": 0.5,
            },
            "window": {"start_second": 0, "end_second": 60},
            "signal_quality": {"n_rpeaks": 60},
        }

    monkeypatch.setattr(ecg_service, "predict_apnea_from_ecg", fail_explanation_once)
    result = ecg_service.analyze_ecg_recording(
        [0.0] * 6000,
        100,
        package,
        include_ai_explanation=True,
        settings=Settings(gemini_api_key="test-key", gemini_model="configured-test-model"),
    )

    assert result["windows"][0]["result"]["apnea_class_score"] == 0.62
    assert result["ai_explanation_status"]["code"] == "mathematical_explanation_unavailable"
    assert calls == [True, False]


def test_recording_model_unavailable_error_is_propagated(package, monkeypatch):
    calls = []

    def fail_prediction(*args, **kwargs):
        calls.append(kwargs.get("include_explanation", False))
        raise ModelUnavailableError("the prediction model is unavailable")

    monkeypatch.setattr(ecg_service, "predict_apnea_from_ecg", fail_prediction)

    with pytest.raises(ModelUnavailableError, match="prediction model is unavailable"):
        ecg_service.analyze_ecg_recording(
            [0.0] * 6000,
            100,
            package,
            include_ai_explanation=True,
        )

    assert calls == [True]


def test_recording_model_prediction_failure_is_propagated(package, monkeypatch):
    calls = []

    def fail_prediction(*args, **kwargs):
        calls.append(kwargs.get("include_explanation", False))
        raise SignalRejectedError(
            "MODEL_PREDICTION_FAILED",
            "The model could not process this ECG window.",
        )

    monkeypatch.setattr(ecg_service, "predict_apnea_from_ecg", fail_prediction)

    with pytest.raises(SignalRejectedError, match="The model could not process"):
        ecg_service.analyze_ecg_recording(
            [0.0] * 6000,
            100,
            package,
            include_ai_explanation=True,
        )

    assert calls == [True]


def test_analyze_samples_explanations_preserve_results_and_summary(real_client, real_signal):
    payload = {
        "sampling_rate": 100,
        "ecg_samples": real_signal.tolist() * 2,
    }
    default_response = real_client.post("/api/v1/analyze-samples", json=payload)
    explanation_response = real_client.post(
        "/api/v1/analyze-samples",
        json={**payload, "include_explanation": True},
    )

    assert default_response.status_code == explanation_response.status_code == 200
    default_result = default_response.json()
    explanation_result = explanation_response.json()
    assert _without_explanations(explanation_result) == default_result
    assert explanation_result["summary"]["total_windows"] == 2
    assert explanation_result["summary"]["valid_windows"] == 2
    for window in explanation_result["windows"]:
        _assert_explanation(window["explanation"])


def test_recording_ai_uses_one_call_and_excludes_rejected_windows(real_client, real_signal, monkeypatch):
    client = _mock_gemini(monkeypatch)
    payload = {
        "sampling_rate": 100,
        "ecg_samples": [1.0] * 6000 + real_signal.tolist() * 4,
        "include_ai_explanation": True,
    }

    response = real_client.post("/api/v1/analyze-samples", json=payload)

    assert response.status_code == 200
    result = response.json()
    assert result["summary"]["valid_windows"] == 4
    assert result["summary"]["rejected_windows"] == 1
    assert result["ai_explanation"] is not None
    assert len(client.calls) == 1
    context = json.loads(client.calls[0]["contents"].rsplit("\n", 1)[1])
    assert context["successful_window_count"] == 4
    assert context["rejected_window_count"] == 1
    assert len(context["evidence_windows"]) == 3
    assert 0 not in [window["window_index"] for window in context["evidence_windows"]]
    assert all("signal_quality" in window for window in context["evidence_windows"])
    assert "ecg_samples" not in context
    assert "explanation" not in result["windows"][0]


def test_recording_does_not_call_gemini_without_ai_opt_in(real_client, real_signal, monkeypatch):
    client = _mock_gemini(monkeypatch)
    response = real_client.post(
        "/api/v1/analyze-samples",
        json={
            "sampling_rate": 100,
            "ecg_samples": real_signal.tolist(),
            "include_explanation": True,
            "include_ai_explanation": False,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert "explanation" in result["windows"][0]
    assert "ai_explanation" not in result
    assert client.calls == []


def test_recording_without_complete_successful_windows_skips_gemini(
    real_client,
    real_signal,
    monkeypatch,
):
    client = _mock_gemini(monkeypatch)
    response = real_client.post(
        "/api/v1/analyze-samples",
        json={
            "sampling_rate": 100,
            "ecg_samples": real_signal.tolist()[:-1],
            "include_ai_explanation": True,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["summary"]["total_windows"] == 0
    assert result["windows"] == []
    assert result["ai_explanation"] is None
    assert result["ai_explanation_status"]["code"] == "insufficient_successful_windows"
    assert client.calls == []


def test_recording_with_all_windows_rejected_skips_gemini(
    real_client,
    monkeypatch,
):
    client = _mock_gemini(monkeypatch)
    response = real_client.post(
        "/api/v1/analyze-samples",
        json={
            "sampling_rate": 100,
            "ecg_samples": [1.0] * 12000,
            "include_ai_explanation": True,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["summary"]["valid_windows"] == 0
    assert result["summary"]["rejected_windows"] == 2
    assert result["ai_explanation"] is None
    assert client.calls == []


def test_analyze_file_ai_explanation_is_recording_level(real_client, real_signal, monkeypatch):
    client = _mock_gemini(monkeypatch)
    file_content = "ecg\n" + "\n".join(str(value) for value in real_signal)

    response = real_client.post(
        "/api/v1/analyze-file",
        files={"file": ("signal.csv", file_content.encode("utf-8"))},
        data={"sampling_rate": "100", "include_ai_explanation": "true"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["ai_explanation"] is not None
    assert len(client.calls) == 1
    assert "ai_explanation" not in result["windows"][0]


def test_analyze_file_explanation_is_opt_in(real_client, real_signal):
    file_content = "ecg\n" + "\n".join(str(value) for value in real_signal)
    upload = {"file": ("signal.csv", file_content.encode("utf-8"))}
    default_response = real_client.post(
        "/api/v1/analyze-file",
        files=upload,
        data={"sampling_rate": "100"},
    )
    explanation_response = real_client.post(
        "/api/v1/analyze-file",
        files=upload,
        data={"sampling_rate": "100", "include_explanation": "true"},
    )

    assert default_response.status_code == explanation_response.status_code == 200
    default_result = default_response.json()
    explanation_result = explanation_response.json()
    assert _without_explanations(explanation_result) == default_result
    assert "explanation" not in default_result["windows"][0]
    _assert_explanation(explanation_result["windows"][0]["explanation"])


def test_analyze_samples_features_without_explanation(real_client, real_signal):
    response = real_client.post(
        "/api/v1/analyze-samples",
        json={
            "sampling_rate": 100,
            "ecg_samples": real_signal.tolist(),
            "include_features": True,
            "include_explanation": False,
        },
    )

    assert response.status_code == 200
    window = response.json()["windows"][0]
    assert window["status"] == "success"
    assert len(window["features"]) == 13
    assert "explanation" not in window


def test_analyze_file_features_without_explanation(real_client, real_signal):
    file_content = "ecg\n" + "\n".join(str(value) for value in real_signal)
    response = real_client.post(
        "/api/v1/analyze-file",
        files={"file": ("signal.csv", file_content.encode("utf-8"))},
        data={
            "sampling_rate": "100",
            "include_features": "true",
            "include_explanation": "false",
        },
    )

    assert response.status_code == 200
    window = response.json()["windows"][0]
    assert window["status"] == "success"
    assert len(window["features"]) == 13
    assert "explanation" not in window


def test_rejected_windows_never_contain_explanations(real_client, real_signal):
    payload = {
        "sampling_rate": 100,
        "ecg_samples": [1.0] * 6000 + real_signal.tolist(),
    }
    default_response = real_client.post("/api/v1/analyze-samples", json=payload)
    explanation_response = real_client.post(
        "/api/v1/analyze-samples",
        json={**payload, "include_explanation": True},
    )

    assert default_response.status_code == explanation_response.status_code == 200
    default_result = default_response.json()
    explanation_result = explanation_response.json()
    assert _without_explanations(explanation_result) == default_result
    rejected, successful = explanation_result["windows"]
    assert rejected["status"] == "rejected"
    assert "explanation" not in rejected
    assert successful["status"] == "success"
    _assert_explanation(successful["explanation"])
    assert explanation_result["summary"] == default_result["summary"]
