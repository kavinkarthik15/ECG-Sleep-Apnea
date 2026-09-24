import numpy as np
import pytest

from app.core.config import Settings
from app.main import create_app
from app.ml.model_loader import ModelPackage


class FakeModel:
    def __init__(self):
        self.columns = None

    def predict_proba(self, frame):
        self.columns = list(frame.columns)
        return np.array([[0.4602, 0.5398]])


@pytest.fixture
def package():
    return ModelPackage(FakeModel(), ["mean_rr", "median_rr", "mean_hr", "min_hr", "max_hr", "sdnn", "rmssd", "pnn50", "rr_range", "rr_cv", "mean_abs_rr_diff", "std_rr_diff", "hr_std"], 0.5, 100, 60, 0.5, 40.0, 4, 300, 2000, 0.8, 20, "neurokit", {0: "N", 1: "A"}, "ecg_apnea_hrv_lr_v2")


@pytest.fixture
def app(package):
    return create_app(package=package, settings=Settings(), load_artifact=False)