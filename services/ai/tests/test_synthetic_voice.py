import copy
import math

import pytest

from spikes.synthetic_voice import (
    choose_threshold,
    compare,
    detection_metrics,
    operating_point,
    validate_rows,
)


def test_perfect_inverted_and_tied_eer() -> None:
    assert detection_metrics([0, 1], [0.1, 0.9], 0.5)["eer"] == 0
    assert detection_metrics([0, 1], [0.9, 0.1], 0.5)["eer"] == 1
    assert detection_metrics([0, 1], [0.5, 0.5], 0.5)["eer"] == 0.5


def test_fpr_and_accuracy_at_selected_threshold() -> None:
    threshold = choose_threshold([0, 0, 1, 1], [0.1, 0.3, 0.7, 0.9])
    assert threshold == 0.7
    point = operating_point([0, 0, 1, 1], [0.1, 0.8, 0.6, 0.9], threshold)
    assert point["fpr"] == 0.5
    assert point["fnr"] == 0.5
    assert point["accuracy"] == 0.5


@pytest.mark.parametrize(
    "labels,scores",
    [([1], [0.5]), ([0, 1], [0.1]), ([0, 1], [math.nan, 0.2]), ([0, 1], [2, 0.3]), ([], [])],
)
def test_invalid_metrics_fail(labels: list[int], scores: list[float]) -> None:
    with pytest.raises(ValueError):
        detection_metrics(labels, scores, 0.5)


def valid_rows() -> list[dict[str, str]]:
    rows = []
    for split in ("train", "calibration", "test"):
        for engine in ("human", "piper", "edge"):
            identifier = f"{split}_{engine}"
            rows.append(
                {
                    "sample_id": identifier,
                    "audio_path": f"audio/{identifier}.wav",
                    "sha256": identifier,
                    "label": "real" if engine == "human" else "synthetic",
                    "engine": engine,
                    "split": split,
                    "speaker_id": identifier,
                    "source_id": identifier,
                    "text_id": split,
                    "condition": "speaker_mic",
                    "source": "unit_test_fixture",
                    "license": "test_only",
                    "consent_id": "not_a_real_recording",
                }
            )
    rows.append(
        rows[-1]
        | {
            "sample_id": "heldout",
            "sha256": "heldout",
            "source_id": "heldout",
            "speaker_id": "heldout",
            "engine": "xtts",
            "condition": "mixed",
        }
    )
    return rows


def test_predefined_partitions_and_three_engines() -> None:
    validate_rows(valid_rows(), "xtts")


def test_mixed_recording_tracks_all_speakers() -> None:
    rows = valid_rows()
    rows[-1]["speaker_id"] = "heldout|train_human"
    with pytest.raises(ValueError, match="speaker_id"):
        validate_rows(rows, "xtts")


def test_baseline_fits_train_and_calibrates_without_test() -> None:
    pytest.importorskip("sklearn")
    rows = valid_rows()
    features = [[float(row["label"] == "synthetic"), 0.0] for row in rows]
    scores = [0.9 if row["label"] == "synthetic" else 0.1 for row in rows]
    first = compare(rows, features, scores, "xtts")
    for i, row in enumerate(rows):
        if row["split"] == "test":
            features[i] = [1 - features[i][0], 5.0]
            scores[i] = 1 - scores[i]
    second = compare(rows, features, scores, "xtts")
    for model in ("xlsr_logistic", "aasist_frozen"):
        assert first[model]["threshold"] == second[model]["threshold"]
        assert first[model]["test"]["accuracy"] == 1
        assert second[model]["test"]["accuracy"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("split", "train"),
        ("engine", "edge"),
        ("condition", "clean"),
        ("source_id", "train_human"),
        ("speaker_id", "train_human"),
        ("text_id", "train"),
        ("sha256", "train_human"),
        ("consent_id", ""),
    ],
)
def test_leakage_missing_consent_or_holdout_rejected(field: str, value: str) -> None:
    rows = copy.deepcopy(valid_rows())
    rows[-1][field] = value
    with pytest.raises(ValueError):
        validate_rows(rows, "xtts")
