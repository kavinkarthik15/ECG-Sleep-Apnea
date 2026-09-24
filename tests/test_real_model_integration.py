from pathlib import Path
import json

import neurokit2 as nk
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.ml.model_loader import load_model_package


def test_real_model_metadata_and_pipeline():
    package = load_model_package(Path("app/models/ecg_apnea_hrv_lr_v2.joblib"))
    assert package.model_version == "ecg_apnea_hrv_lr_v2"
    assert package.sampling_rate == 100
    assert package.window_seconds == 60
    assert package.threshold == 0.50
    assert package.feature_names == [
        "mean_rr", "median_rr", "mean_hr", "min_hr", "max_hr", "sdnn",
        "rmssd", "pnn50", "rr_range", "rr_cv", "mean_abs_rr_diff",
        "std_rr_diff", "hr_std",
    ]
    assert list(package.model.named_steps) == ["scaler", "classifier"]
    assert package.model.named_steps["scaler"].__class__.__name__ == "StandardScaler"
    assert package.model.named_steps["classifier"].__class__.__name__ == "LogisticRegression"


def test_real_model_prediction_endpoint_reaches_pipeline():
    package = load_model_package(Path("app/models/ecg_apnea_hrv_lr_v2.joblib"))
    signal = nk.ecg_simulate(duration=60, sampling_rate=100, heart_rate=70, random_state=42)
    application = create_app(package=package, settings=Settings(), load_artifact=False)
    with TestClient(application) as client:
        response = client.post("/api/v1/predict", json={"sampling_rate": 100, "ecg_samples": signal.tolist()})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert body["model_version"] == "ecg_apnea_hrv_lr_v2"
    assert 0.0 <= body["result"]["apnea_class_score"] <= 1.0


def test_real_model_startup_loads_once_and_routes_work(monkeypatch):
    original_loader = __import__("app.main", fromlist=["load_model_package"]).load_model_package
    calls = 0

    def counted_loader(path):
        nonlocal calls
        calls += 1
        return original_loader(path)

    monkeypatch.setattr("app.main.load_model_package", counted_loader)
    settings = Settings(model_path=Path("app/models/ecg_apnea_hrv_lr_v2.joblib"))
    signal = nk.ecg_simulate(duration=60, sampling_rate=100, heart_rate=70, random_state=43)
    application = create_app(settings=settings, load_artifact=True)
    with TestClient(application) as client:
        assert client.get("/").status_code == 200
        assert client.get("/health").json()["model_loaded"] is True
        assert client.get("/api/v1/model-info").json()["feature_count"] == 13
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200
        assert client.post("/api/v1/analyze-samples", json={"sampling_rate": 100, "ecg_samples": signal.tolist() + [0.0] * 7}).status_code == 200
        csv_content = "ecg\n" + "\n".join(str(value) for value in signal)
        file_response = client.post("/api/v1/analyze-file", files={"file": ("signal.csv", csv_content.encode("utf-8"))}, data={"sampling_rate": "100"})
        assert file_response.status_code == 200
        invalid_requests = [
            (None, {"sampling_rate": 50, "ecg_samples": signal.tolist()}),
            (None, {"sampling_rate": 100, "ecg_samples": signal.tolist()[:-1]}),
            (json.dumps({"sampling_rate": 100, "ecg_samples": [float("nan")] * 6000}), None),
            (json.dumps({"sampling_rate": 100, "ecg_samples": [float("inf")] * 6000}), None),
            (None, {"sampling_rate": 100, "ecg_samples": [1.0] * 6000}),
        ]
        for content, payload in invalid_requests:
            response = client.post("/api/v1/predict", content=content, json=payload) if content else client.post("/api/v1/predict", json=payload)
            assert response.status_code in {400, 422}
    assert calls == 1