import math
from typing import Any

import pytest

from spikes.similarity import evaluate_scores, rates, roc


def test_perfect_and_inverted_roc() -> None:
    assert rates([0, 1], [0.1, 0.9], 0.5)["accuracy"] == 1
    assert rates([0, 1], [0.9, 0.1], 0.5)["accuracy"] == 0
    curve = roc([0, 1], [0.1, 0.9])
    assert [(p["fpr"], p["tpr"]) for p in curve] == [(0, 0), (0, 1), (1, 1)]


def test_ties_are_one_roc_step_and_threshold_is_inclusive() -> None:
    curve = roc([0, 1], [0.5, 0.5])
    assert len(curve) == 2
    assert rates([0, 1], [0.5, 0.5], 0.5)["fpr"] == 1
    rows = [
        {"split": split, "label": label, "score": 0.0}
        for split in ("calibration", "test")
        for label in ("reading", "unrelated")
    ]
    assert evaluate_scores(rows, 0.6)["chosen_threshold"] == 1.0


@pytest.mark.parametrize(
    "labels,scores",
    [([1], [0.5]), ([0, 1], [0.1]), ([0, 1], [math.nan, 0.2]), ([0, 1], [-0.1, 0.3]), ([], [])],
)
def test_invalid_metrics_fail(labels: list[int], scores: list[float]) -> None:
    with pytest.raises(ValueError):
        rates(labels, scores, 0.5)


def test_test_set_cannot_choose_threshold_and_reading_is_not_fraud() -> None:
    calibration: list[dict[str, Any]] = [
        {"split": "calibration", "label": "reading", "score": 0.9},
        {"split": "calibration", "label": "dictation", "score": 0.8},
        {"split": "calibration", "label": "unrelated", "score": 0.2},
    ]
    test: list[dict[str, Any]] = [
        {"split": "test", "label": "reading", "score": 0.7},
        {"split": "test", "label": "dictation", "score": 0.6},
        {"split": "test", "label": "unrelated", "score": 0.1},
    ]
    result = evaluate_scores(calibration + test, 0.6)
    assert result["chosen_threshold"] == 0.8
    assert result["test"]["tpr"] == 0
    assert result["test_auc"] == 1
    for row in test:
        row["score"] = 1 - float(row["score"])
    assert evaluate_scores(calibration + test, 0.6)["chosen_threshold"] == 0.8
