from copy import deepcopy
from dataclasses import replace
from math import exp
from pathlib import Path

import neurokit2 as nk
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.core.exceptions import ModelUnavailableError
from app.ml.features import FEATURE_NAMES
from app.ml.inference import _calculate_explanation, predict_apnea_from_ecg
from app.ml.model_loader import load_model_package


@pytest.fixture
def real_package():
    return load_model_package(Path("app/models/ecg_apnea_hrv_lr_v2.joblib"))


@pytest.fixture
def real_signal():
    return nk.ecg_simulate(duration=60, sampling_rate=100, heart_rate=70, random_state=42)


def test_explanation_reconstructs_frozen_model_probability(real_package):
    features = {name: 100.0 + index / 10 for index, name in enumerate(FEATURE_NAMES)}

    explanation = _calculate_explanation(features, real_package)
    entries = explanation["features"]

    assert explanation["class_label"] == "A"
    assert explanation["method"] == "logistic_regression_feature_contributions"
    assert len(entries) == 13
    contributions = [entry["contribution"] for entry in entries]
    assert contributions == sorted(contributions, key=abs, reverse=True)
    assert {entry["feature_name"]: entry["feature_value"] for entry in entries} == features
    assert np.isclose(sum(contributions) + explanation["intercept"], explanation["logit"], rtol=1e-12, atol=1e-12)

    logit = explanation["logit"]
    expected_sigmoid = 1 / (1 + exp(-logit)) if logit >= 0 else exp(logit) / (1 + exp(logit))
    assert np.isclose(expected_sigmoid, explanation["reconstructed_probability"], rtol=1e-12, atol=1e-15)
    frame = pd.DataFrame([[features[name] for name in FEATURE_NAMES]], columns=FEATURE_NAMES)
    actual_probability = real_package.model.predict_proba(frame)[0, 1]
    assert np.isclose(explanation["reconstructed_probability"], actual_probability, rtol=1e-12, atol=1e-15)
    for entry in entries:
        expected_direction = (
            "toward_apnea" if entry["contribution"] > 0 else
            "away_from_apnea" if entry["contribution"] < 0 else
            "neutral"
        )
        assert entry["direction"] == expected_direction


def test_explanation_is_opt_in_and_does_not_change_prediction(real_package, real_signal):
    default_result = predict_apnea_from_ecg(real_signal, real_package)
    explained_result = predict_apnea_from_ecg(real_signal, real_package, include_explanation=True)

    assert "explanation" not in default_result
    assert "features" not in explained_result
    assert explained_result["explanation"]["class_label"] == "A"
    assert explained_result["result"]["class"] == default_result["result"]["class"]
    assert explained_result["result"]["apnea_class_score"] == default_result["result"]["apnea_class_score"]


def test_features_can_be_included_without_explanation(real_package, real_signal):
    result = predict_apnea_from_ecg(real_signal, real_package, include_features=True)

    assert "features" in result
    assert "explanation" not in result


def test_incompatible_model_structure_is_rejected(real_package):
    incompatible_package = replace(real_package, model=object())
    features = {name: 100.0 + index / 10 for index, name in enumerate(FEATURE_NAMES)}

    with pytest.raises(ModelUnavailableError, match="Cannot calculate a Logistic Regression explanation"):
        _calculate_explanation(features, incompatible_package)


def test_explanation_handles_reversed_binary_class_order(real_package):
    rng = np.random.default_rng(42)
    values = rng.normal(size=(240, len(FEATURE_NAMES)))
    scores = values[:, 0] - 0.6 * values[:, 1] + 0.3 * values[:, 2]
    target = np.where(scores > np.median(scores), 1, 0)
    encoded_target = 1 - target
    training_data = pd.DataFrame(values, columns=FEATURE_NAMES)
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(random_state=42, max_iter=500)),
    ])
    model.fit(training_data, encoded_target)

    classifier = model.named_steps["classifier"]
    # sklearn sorts binary classes on fit, so reverse the fitted parameterization
    # as well as classes_ to represent the equivalent [1, 0] class ordering.
    classifier.classes_ = classifier.classes_[::-1]
    classifier.coef_ = -classifier.coef_
    classifier.intercept_ = -classifier.intercept_
    package = replace(real_package, model=model)
    features = {name: 100.0 + index / 10 for index, name in enumerate(FEATURE_NAMES)}

    explanation = _calculate_explanation(features, package)
    feature_values = np.asarray([features[name] for name in FEATURE_NAMES])
    contributions_by_name = {
        entry["feature_name"]: entry["contribution"] for entry in explanation["features"]
    }
    frame = pd.DataFrame([feature_values], columns=FEATURE_NAMES)
    class_1_index = int(np.flatnonzero(classifier.classes_ == 1)[0])

    assert classifier.classes_.tolist() == [1, 0]
    assert len(explanation["features"]) == len(FEATURE_NAMES)
    assert set(contributions_by_name) == set(FEATURE_NAMES)
    class_1_coefficients = -classifier.coef_[0]
    expected_contributions = {
        name: (features[name] - model.named_steps["scaler"].mean_[index])
        * class_1_coefficients[index]
        / model.named_steps["scaler"].scale_[index]
        for index, name in enumerate(FEATURE_NAMES)
    }
    assert contributions_by_name == pytest.approx(expected_contributions, rel=1e-12, abs=1e-12)
    assert np.isclose(
        sum(contributions_by_name.values()) + explanation["intercept"],
        explanation["logit"],
        rtol=1e-12,
        atol=1e-12,
    )
    assert explanation["reconstructed_probability"] == pytest.approx(
        model.predict_proba(frame)[0, class_1_index], rel=1e-12, abs=1e-15
    )


def test_non_finite_classifier_parameters_are_rejected(real_package):
    model = deepcopy(real_package.model)
    model.named_steps["classifier"].coef_[0, 0] = np.nan
    package = replace(real_package, model=model)
    features = {name: 100.0 + index / 10 for index, name in enumerate(FEATURE_NAMES)}

    with pytest.raises(ModelUnavailableError, match="non-finite or invalid"):
        _calculate_explanation(features, package)
