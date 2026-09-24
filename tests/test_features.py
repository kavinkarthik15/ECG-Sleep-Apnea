import numpy as np
import pytest

from app.core.exceptions import SignalRejectedError
from app.ml.features import FEATURE_NAMES, extract_hrv_features


def test_feature_order_and_adjacency_preservation():
    rpeaks = np.array([0, 80, 160, 240, 320, 400, 480, 560, 640, 720, 800, 880, 960, 1040, 1120, 1200, 1280, 1360, 1440, 1520, 1600, 1680])
    values, quality = extract_hrv_features(rpeaks, 100)
    assert list(values) == FEATURE_NAMES
    assert quality["rr_valid_ratio"] == 1.0


def test_invalid_rr_is_rejected():
    with pytest.raises(SignalRejectedError, match="valid RR"):
        extract_hrv_features(np.arange(20) * 10, 100)