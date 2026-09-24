from fastapi.testclient import TestClient


def test_health_and_model_info(app):
    with TestClient(app) as client:
        assert client.get("/health").json()["model_loaded"] is True
        assert client.get("/api/v1/model-info").json()["feature_count"] == 13


def test_wrong_rate_and_count(app):
    with TestClient(app) as client:
        wrong_rate = client.post("/api/v1/predict", json={"sampling_rate": 50, "ecg_samples": [1]})
        assert wrong_rate.status_code == 422
        wrong_count = client.post("/api/v1/predict", json={"sampling_rate": 100, "ecg_samples": [1]})
        assert wrong_count.status_code == 422


def test_unsupported_upload(app):
    with TestClient(app) as client:
        response = client.post("/api/v1/analyze-file", files={"file": ("signal.json", b"[]")}, data={"sampling_rate": "100"})
        assert response.status_code == 415