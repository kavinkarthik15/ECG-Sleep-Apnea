import json
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors
from pydantic import SecretStr

from app.core.config import Settings
from app.ml.features import FEATURE_NAMES
from app.schemas.responses import (
    AI_EXPLANATION_DISCLAIMER,
    AIExplanation,
    GeneratedAIExplanation,
)
from app.services import ecg_service
from app.services import ai_explanation_service as ai_service


VALID_EXPLANATION = {
    "headline": "The model output favors the apnea-related class",
    "summary": "The supplied model evidence favors class A for this window.",
    "supporting_factors": ["mean_rr contributes toward the apnea-related class."],
    "opposing_factors": ["sdnn contributes away from the apnea-related class."],
    "limitations": ["This is one experimental model window."],
    "disclaimer": "Provider text must not replace the application disclaimer.",
}

SINGLE_WINDOW_CONTEXT = {
    "mathematical_explanation": {
        "features": [
            {"feature_name": "mean_rr", "contribution": 0.8, "direction": "toward_apnea"},
            {"feature_name": "sdnn", "contribution": -0.5, "direction": "away_from_apnea"},
            {"feature_name": "pnn50", "contribution": 0.4, "direction": "toward_apnea"},
            {"feature_name": "rmssd", "contribution": 0.3, "direction": "toward_apnea"},
            {"feature_name": "weak_feature", "contribution": 0.01, "direction": "toward_apnea"},
            {"feature_name": "neutral_feature", "contribution": 0.0, "direction": "neutral"},
        ]
    }
}


class MockModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(text=outcome)


class MockClient:
    def __init__(self, outcomes):
        self.models = MockModels(outcomes)
        self.closed = False

    def close(self):
        self.closed = True


def _settings(**kwargs):
    return Settings(
        gemini_api_key=SecretStr("test-key"),
        gemini_model="configured-test-model",
        gemini_max_retries=kwargs.pop("gemini_max_retries", 2),
        **kwargs,
    )


def _api_error(code):
    return errors.APIError(
        code,
        {"status": "RESOURCE_EXHAUSTED", "message": "provider detail must remain private"},
    )


def test_gemini_returns_validated_structured_output(monkeypatch):
    client = MockClient([json.dumps(VALID_EXPLANATION)])
    monkeypatch.setattr(ai_service, "_client", lambda settings: client)

    explanation = ai_service.generate_ai_explanation(SINGLE_WINDOW_CONTEXT, _settings())

    assert isinstance(explanation, AIExplanation)
    assert explanation.disclaimer == AI_EXPLANATION_DISCLAIMER
    assert explanation.headline == VALID_EXPLANATION["headline"]
    call = client.models.calls[0]
    assert call["model"] == "configured-test-model"
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].response_schema is GeneratedAIExplanation
    assert client.closed


@pytest.mark.parametrize(
    "field,value",
    [
        ("supporting_factors", ["unknown_feature contributes toward the apnea-related class."]),
        ("supporting_factors", ["sdnn contributes toward the apnea-related class."]),
        ("opposing_factors", ["mean_rr contributes away from the apnea-related class."]),
        ("supporting_factors", ["weak_feature contributes toward the apnea-related class."]),
        ("supporting_factors", ["neutral_feature contributes toward the apnea-related class."]),
        ("supporting_factors", ["mean_rr causes oxygen changes."]),
        ("summary", "The model causes respiratory changes."),
    ],
)
def test_gemini_rejects_claims_not_supported_by_math_evidence(monkeypatch, field, value):
    invalid_output = {**VALID_EXPLANATION, field: value}
    client = MockClient([json.dumps(invalid_output)])
    monkeypatch.setattr(ai_service, "_client", lambda settings: client)

    explanation, status = ai_service.safe_generate_ai_explanation(
        SINGLE_WINDOW_CONTEXT,
        _settings(),
    )

    assert explanation is None
    assert status.code == "invalid_response"


def test_gemini_validates_recording_claims_only_against_successful_evidence(monkeypatch):
    context = {
        "evidence_windows": [
            {
                "mathematical_explanation": {
                    "features": [
                        {"feature_name": "mean_rr", "contribution": 0.8, "direction": "toward_apnea"},
                        {"feature_name": "sdnn", "contribution": -0.5, "direction": "away_from_apnea"},
                    ]
                }
            }
        ],
        "rejected_window_feature": "hr_std",
    }
    valid_client = MockClient([json.dumps(VALID_EXPLANATION)])
    monkeypatch.setattr(ai_service, "_client", lambda settings: valid_client)
    explanation, status = ai_service.safe_generate_ai_explanation(context, _settings())
    assert explanation is not None
    assert status.status == "available"

    invalid_output = {
        **VALID_EXPLANATION,
        "supporting_factors": ["hr_std contributes toward the apnea-related class."],
    }
    invalid_client = MockClient([json.dumps(invalid_output)])
    monkeypatch.setattr(ai_service, "_client", lambda settings: invalid_client)
    explanation, status = ai_service.safe_generate_ai_explanation(context, _settings())
    assert explanation is None
    assert status.code == "invalid_response"


def _recording_window(index, class_label, status="success"):
    window = {"status": status, "window_index": index}
    if status == "success":
        window.update({
            "start_second": index * 60,
            "end_second": (index + 1) * 60,
            "result": {
                "class": class_label,
                "label": "Apnea-related pattern detected" if class_label == "A" else "No apnea-related pattern detected",
                "apnea_class_score": 0.6 if class_label == "A" else 0.4,
            },
            "explanation": {
                "intercept": 0.0,
                "logit": 0.4,
                "features": [
                    {
                        "feature_name": name,
                        "feature_value": 1.0,
                        "contribution": _window_feature_contribution(name, class_label),
                        "direction": _direction(_window_feature_contribution(name, class_label)),
                    }
                    for name in FEATURE_NAMES
                ],
            },
            "signal_quality": {"n_rpeaks": 60},
        })
    return window


def _window_feature_contribution(feature_name, class_label):
    if feature_name == "mean_rr":
        return 0.4
    if feature_name == "sdnn":
        return -0.2 if class_label == "A" else 0.2
    return 0.0


def _direction(contribution):
    return "toward_apnea" if contribution > 0 else "away_from_apnea" if contribution < 0 else "neutral"


@pytest.mark.parametrize("classes", [[], ["A"], ["A", "N"], ["A", "N", "A"]])
def test_representative_windows_handle_zero_to_three_successes(classes):
    windows = [
        _recording_window(index, label)
        for index, label in enumerate(classes)
    ]

    selected = ai_service.representative_windows(windows)

    assert [window["window_index"] for window in selected] == list(range(len(classes)))


def test_representative_windows_select_both_classes_and_preserve_order():
    windows = [
        _recording_window(index, label)
        for index, label in enumerate(["A", "A", "A", "N", "A", "A", "A"])
    ]

    selected = ai_service.representative_windows(windows)

    assert len(selected) == 3
    assert {window["prediction"]["class"] for window in selected} == {"A", "N"}
    assert [window["window_index"] for window in selected] == sorted(
        window["window_index"] for window in selected
    )


def test_representative_windows_distribute_one_class_across_time():
    windows = [
        _recording_window(index, "A")
        for index in range(7)
    ]

    selected = ai_service.representative_windows(windows)

    assert [window["window_index"] for window in selected] == [0, 3, 6]


def test_representative_windows_never_select_rejected_windows():
    windows = [
        _recording_window(0, "A"),
        _recording_window(1, "N", status="rejected"),
        _recording_window(2, "A"),
        _recording_window(3, "N"),
        _recording_window(4, "A"),
    ]

    selected = ai_service.representative_windows(windows)

    assert all(window["window_index"] != 1 for window in selected)
    assert {window["prediction"]["class"] for window in selected} == {"A", "N"}


def test_representative_windows_cap_selection_for_more_than_three_classes():
    windows = [
        _recording_window(index, label)
        for index, label in enumerate(["A", "B", "C", "D", "E", "F", "G"])
    ]

    selected = ai_service.representative_windows(windows)

    assert 0 <= len(selected) <= 3
    assert [window["window_index"] for window in selected] == sorted(
        window["window_index"] for window in selected
    )


def test_recording_aggregate_excludes_rejected_windows_and_averages_directions():
    windows = [
        _recording_window(0, "A"),
        _recording_window(1, "N"),
        _recording_window(2, "A"),
        _recording_window(3, "N", status="rejected"),
    ]
    windows[0]["explanation"]["features"][0]["contribution"] = 0.6
    windows[0]["explanation"]["features"][0]["direction"] = "toward_apnea"
    windows[1]["explanation"]["features"][0]["contribution"] = -0.3
    windows[1]["explanation"]["features"][0]["direction"] = "away_from_apnea"
    windows[2]["explanation"]["features"][0]["contribution"] = -0.3
    windows[2]["explanation"]["features"][0]["direction"] = "away_from_apnea"
    windows[3]["explanation"] = {
        "features": [
            {
                "feature_name": "rejected_only",
                "contribution": 100.0,
                "direction": "toward_apnea",
            },
            {
                "feature_name": "mean_rr",
                "contribution": 100.0,
                "direction": "toward_apnea",
            },
        ]
    }

    context = ai_service.build_recording_context("model-v1", {"valid_windows": 3}, windows)
    aggregate = {
        feature["feature_name"]: feature
        for feature in context["aggregate_features"]
    }

    assert len(context["evidence_windows"]) == 3
    assert [window["mathematical_explanation"]["features"][0]["contribution"] for window in context["evidence_windows"]] == [0.6, -0.3, -0.3]
    assert aggregate["mean_rr"]["aggregate_contribution"] == pytest.approx(0.0)
    assert aggregate["mean_rr"]["direction"] == "neutral"
    assert aggregate["sdnn"]["aggregate_contribution"] == pytest.approx((-0.2 + 0.2 - 0.2) / 3)
    assert aggregate["sdnn"]["direction"] == "away_from_apnea"
    assert "rejected_only" not in aggregate


def test_recording_aggregate_uses_all_successes_not_only_representatives():
    windows = [_recording_window(index, "A") for index in range(7)]
    representative_indices = {0, 3, 6}
    for window in windows:
        index = window["window_index"]
        features = window["explanation"]["features"]
        for feature in features:
            if feature["feature_name"] == "mean_rr":
                feature["contribution"] = 1.0 if index in representative_indices else -4.0
                feature["direction"] = _direction(feature["contribution"])
            elif feature["feature_name"] == "median_rr":
                feature["contribution"] = 2.0
                feature["direction"] = "toward_apnea"
            elif feature["feature_name"] == "pnn50":
                feature["contribution"] = 1.5
                feature["direction"] = "toward_apnea"
            elif feature["feature_name"] == "rmssd":
                feature["contribution"] = 1.0
                feature["direction"] = "toward_apnea"
            elif feature["feature_name"] == "mean_hr":
                feature["contribution"] = -1.0
                feature["direction"] = "away_from_apnea"

    context = ai_service.build_recording_context("model-v1", {}, windows)
    representatives = context["evidence_windows"]
    aggregate = {
        feature["feature_name"]: feature["aggregate_contribution"]
        for feature in context["aggregate_features"]
    }

    assert [window["window_index"] for window in representatives] == [0, 3, 6]
    assert all(
        next(
            feature["contribution"]
            for feature in window["mathematical_explanation"]["features"]
            if feature["feature_name"] == "mean_rr"
        ) > 0
        for window in representatives
    )
    assert aggregate["mean_rr"] == pytest.approx((3.0 - 16.0) / 7)
    assert aggregate["mean_rr"] < 0

    candidates = ai_service._eligible_feature_candidates(context)
    supporting = [name for name, _ in candidates["supporting_factors"][1]]
    opposing = [name for name, _ in candidates["opposing_factors"][1]]
    assert supporting == ["median_rr", "pnn50", "rmssd"]
    assert opposing == ["mean_rr", "mean_hr", "sdnn"]


def test_recording_claims_follow_aggregate_direction(monkeypatch):
    context = {
        "aggregate_features": [
            {"feature_name": "mean_rr", "aggregate_contribution": 0.0, "direction": "neutral"},
            {"feature_name": "sdnn", "aggregate_contribution": -0.2, "direction": "away_from_apnea"},
        ],
    }
    output = {
        **VALID_EXPLANATION,
        "supporting_factors": ["mean_rr contributes toward the apnea-related class."],
    }
    client = MockClient([json.dumps(output)])
    monkeypatch.setattr(ai_service, "_client", lambda settings: client)

    explanation, status = ai_service.safe_generate_ai_explanation(context, _settings())

    assert explanation is None
    assert status.code == "invalid_response"


def test_inconsistent_successful_feature_sets_return_safe_unavailable(package, monkeypatch):
    base_features = [
        {
            "feature_name": name,
            "feature_value": 1.0,
            "contribution": 0.1,
            "direction": "toward_apnea",
        }
        for name in FEATURE_NAMES
    ]
    calls = 0

    def fake_prediction(window, model_package, **kwargs):
        nonlocal calls
        calls += 1
        features = base_features if calls == 1 else base_features[:-1]
        return {
            "status": "success",
            "result": {
                "class": "A",
                "label": "Apnea-related pattern detected",
                "apnea_class_score": 0.6,
                "threshold": 0.5,
            },
            "signal_quality": {"n_rpeaks": 60},
            "explanation": {
                "intercept": 0.0,
                "logit": 0.4,
                "features": features,
            },
        }

    def unexpected_gemini_call(*args, **kwargs):
        raise AssertionError("Gemini must not be called for inconsistent evidence.")

    monkeypatch.setattr(ecg_service, "predict_apnea_from_ecg", fake_prediction)
    monkeypatch.setattr(ecg_service, "safe_generate_ai_explanation", unexpected_gemini_call)

    result = ecg_service.analyze_ecg_recording(
        [1.0] * 12000,
        100,
        package,
        include_ai_explanation=True,
        settings=_settings(),
    )

    assert result["summary"]["valid_windows"] == 2
    assert result["ai_explanation"] is None
    assert result["ai_explanation_status"]["code"] == "inconsistent_mathematical_evidence"


def test_gemini_missing_api_key_returns_safe_unavailable_status():
    explanation, status = ai_service.safe_generate_ai_explanation(
        {"evidence": "verified"},
        Settings(gemini_model="configured-test-model"),
    )

    assert explanation is None
    assert status.model_dump() == {"status": "unavailable", "code": "missing_api_key"}


def test_gemini_missing_model_is_reported_without_api_request():
    settings = Settings(gemini_api_key=SecretStr("test-key"))

    explanation, status = ai_service.safe_generate_ai_explanation({"evidence": 1}, settings)

    assert explanation is None
    assert status.code == "model_not_configured"


def test_gemini_authentication_failure_is_not_exposed(monkeypatch):
    client = MockClient([_api_error(403)])
    monkeypatch.setattr(ai_service, "_client", lambda settings: client)

    explanation, status = ai_service.safe_generate_ai_explanation({"evidence": 1}, _settings())

    assert explanation is None
    assert status.code == "authentication_failed"
    assert client.closed


def test_gemini_rate_limit_retries_are_bounded(monkeypatch):
    client = MockClient([_api_error(429), _api_error(429), _api_error(429), json.dumps(VALID_EXPLANATION)])
    monkeypatch.setattr(ai_service, "_client", lambda settings: client)
    monkeypatch.setattr(ai_service.time, "sleep", lambda delay: None)

    explanation, status = ai_service.safe_generate_ai_explanation(
        {"evidence": 1},
        _settings(gemini_max_retries=2),
    )

    assert explanation is None
    assert status.code == "quota_or_rate_limited"
    assert len(client.models.calls) == 3


def test_gemini_timeout_and_network_failures_are_reported(monkeypatch):
    timeout_client = MockClient([httpx.ReadTimeout("private timeout detail")] * 3)
    monkeypatch.setattr(ai_service, "_client", lambda settings: timeout_client)
    monkeypatch.setattr(ai_service.time, "sleep", lambda delay: None)
    explanation, timeout_status = ai_service.safe_generate_ai_explanation({"evidence": 1}, _settings())
    assert explanation is None
    assert timeout_status.code == "timeout"
    assert len(timeout_client.models.calls) == 3

    network_client = MockClient([httpx.ConnectError("private network detail")] * 3)
    monkeypatch.setattr(ai_service, "_client", lambda settings: network_client)
    explanation, network_status = ai_service.safe_generate_ai_explanation({"evidence": 1}, _settings())
    assert explanation is None
    assert network_status.code == "network_error"
    assert len(network_client.models.calls) == 3


@pytest.mark.parametrize(
    "response",
    [
        "not JSON",
        json.dumps({**VALID_EXPLANATION, "headline": ""}),
        json.dumps({key: value for key, value in VALID_EXPLANATION.items() if key != "limitations"}),
    ],
)
def test_gemini_malformed_or_invalid_content_is_rejected(monkeypatch, response):
    client = MockClient([response])
    monkeypatch.setattr(ai_service, "_client", lambda settings: client)

    explanation, status = ai_service.safe_generate_ai_explanation({"evidence": 1}, _settings())

    assert explanation is None
    assert status.code == "invalid_response"
    assert client.closed
