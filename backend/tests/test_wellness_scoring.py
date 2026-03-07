import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.wellness_scoring import WellnessScoringEngine


@pytest.fixture()
def engine():
    return WellnessScoringEngine()


def test_all_scores_weighted_average(engine):
    score, weights = engine.calculate(skin_score=80, posture_score=70, eye_score=90)
    assert 0 <= score <= 100
    assert isinstance(weights, dict)


def test_some_scores_none_renormalized(engine):
    score, _ = engine.calculate(skin_score=80, posture_score=None, eye_score=90)
    assert 0 <= score <= 100


def test_no_scores_returns_zero(engine):
    score, _ = engine.calculate()
    assert score == 0.0


def test_score_clamping_high(engine):
    score, _ = engine.calculate(skin_score=200, posture_score=200, eye_score=200, thermal_score=200)
    assert score <= 100.0


def test_score_clamping_low(engine):
    score, _ = engine.calculate(skin_score=-50, posture_score=-50, eye_score=-50)
    assert score >= 0.0


def test_thermal_disabled_zero_weight(engine):
    """When thermal weight is 0, thermal_score should not affect the result."""
    score_with, _ = engine.calculate(skin_score=80, posture_score=70, eye_score=90, thermal_score=50)
    score_without, _ = engine.calculate(skin_score=80, posture_score=70, eye_score=90, thermal_score=None)
    assert score_with == score_without
