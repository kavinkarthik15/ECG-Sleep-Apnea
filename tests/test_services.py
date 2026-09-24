import numpy as np

from app.services.ecg_service import analyze_ecg_recording
from app.services.file_service import parse_ecg_file


def test_recording_ignores_incomplete_tail(package, monkeypatch):
    monkeypatch.setattr("app.services.ecg_service.predict_apnea_from_ecg", lambda *args, **kwargs: {"status": "success", "result": {"class": "A", "apnea_class_score": 0.54}})
    result = analyze_ecg_recording(np.ones(6000 * 2 + 7), 100, package)
    assert result["summary"]["total_windows"] == 2
    assert result["ignored_samples"] == 7


def test_named_csv_column():
    result = parse_ecg_file("sample.csv", b"ECG,other\n1,2\n3,4\n", 1000)
    assert result.tolist() == [1.0, 3.0]