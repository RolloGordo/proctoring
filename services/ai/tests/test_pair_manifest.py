import csv
import hashlib
import json
from pathlib import Path

import pytest

from spikes.prepare_pairs import prepare
from spikes.similarity import load_pairs


def make_manifest(tmp_path: Path) -> Path:
    rows = []
    for index in range(60):
        audio = tmp_path / f"{index}.wav"
        audio.write_bytes(f"unit test only {index}".encode())
        rows.append(
            {
                "sample_id": str(index),
                "question_id": str(index // 3),
                "question": f"Pregunta {index // 3}",
                "label": ("reading", "dictation", "unrelated")[index % 3],
                "split": "calibration" if index < 42 else "test",
                "speaker_id": "P01",
                "consent_id": "TEST",
                "reference": "Texto de fixture",
                "audio_path": audio.name,
                "sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
            }
        )
    path = tmp_path / "manifest.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_manifest_requires_real_files_and_matching_hashes(tmp_path: Path) -> None:
    path = make_manifest(tmp_path)
    assert len(load_pairs(path)) == 60
    (tmp_path / "0.wav").write_bytes(b"modified")
    with pytest.raises(ValueError, match="hash"):
        load_pairs(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("question_id", "0"),
        ("question", "Pregunta 0"),
        ("audio_path", "../outside.wav"),
        ("consent_id", ""),
        ("sample_id", "0"),
        ("label", "fraud"),
    ],
)
def test_manifest_rejects_invalid_rows(tmp_path: Path, field: str, value: str) -> None:
    path = make_manifest(tmp_path)
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[-1][field] = value
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError):
        load_pairs(path)


def test_prepare_does_not_write_an_incomplete_manifest(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"samples": [{"sample_id": "missing_audio"}]}))
    with pytest.raises(ValueError):
        prepare(plan, tmp_path)
    assert not (tmp_path / "manifest.csv").exists()
