from pathlib import Path

import pytest

from app.core.exceptions import ModelUnavailableError
from app.ml.model_loader import load_model_package


def test_missing_model_is_reported_without_internal_path():
    with pytest.raises(ModelUnavailableError, match="missing"):
        load_model_package(Path("missing-model.joblib"))