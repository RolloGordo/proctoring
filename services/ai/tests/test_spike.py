import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

from spikes.evaluate import load_manifest, summarize
from spikes.metrics import normalize, word_errors
from spikes.transcribe import Transcriber


def test_spanish_normalization():
    assert normalize("¡NIÑO, acción! ¿Sí?") == ["niño", "acción", "sí"]
    assert normalize("accio\u0301n") == ["acción"]


@pytest.mark.parametrize(
    ("reference", "hypothesis", "edits", "wer"),
    [
        ("hola mundo", "hola mundo", 0, 0),
        ("hola mundo", "hola", 1, 0.5),
        ("hola mundo", "hola amigo", 1, 0.5),
        ("hola", "hola gran mundo", 2, 2),
        ("", "hola", 1, None),
        ("hola", "", 1, 1),
        ("", "", 0, None),
    ],
)
def test_word_errors(reference, hypothesis, edits, wer):
    result = word_errors(reference, hypothesis)
    assert result["word_edits"] == edits
    assert result["wer"] == wer


def test_micro_wer_is_weighted_and_silence_separate():
    results = [
        {
            "metrics": word_errors("uno dos tres", "uno dos tres"),
            "audio_seconds": 3,
            "inference_seconds": 1,
        },
        {"metrics": word_errors("cuatro", "otro"), "audio_seconds": 1, "inference_seconds": 1},
        {"metrics": word_errors("", "ruido"), "audio_seconds": 2, "inference_seconds": 1},
    ]
    report = summarize(results)
    assert report["micro_wer"] == 0.25
    assert report["empty_reference_inserted_words"] == 1
    assert report["aggregate_real_time_factor"] == 0.5


def test_manifest_rejects_path_escape(tmp_path):
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("sample_id,audio_path,reference\na,../outside.wav,hola\n")
    with pytest.raises(ValueError, match="fuera"):
        load_manifest(manifest)


def test_manifest_checks_hash_and_duplicate_ids(tmp_path):
    (tmp_path / "sample.wav").write_bytes(b"example")
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["sample_id", "audio_path", "reference", "sha256"])
        writer.writerow(["a", "sample.wav", "hola", "wrong"])
    with pytest.raises(ValueError, match="cambió"):
        load_manifest(manifest)
    manifest.write_text("sample_id,audio_path,reference\na,sample.wav,hola\na,sample.wav,hola\n")
    with pytest.raises(ValueError, match="duplicado"):
        load_manifest(manifest)


def test_transcription_consumes_lazy_segments(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake for unit test only")
    consumed = []

    def segments():
        consumed.append(True)
        yield SimpleNamespace(start=0.0, end=1.0, text=" Hola mundo ")

    class FakeEngine:
        def transcribe(self, path, **kwargs):
            assert kwargs["language"] == "es"
            assert kwargs["vad_filter"] is True
            return segments(), SimpleNamespace(duration=2.0)

    transcriber = Transcriber.__new__(Transcriber)
    transcriber.engine = FakeEngine()
    transcriber.model, transcriber.threads, transcriber.load_seconds = "fake", 4, 0.0
    monkeypatch.setattr("spikes.transcribe.version", lambda name: "test")
    result = transcriber.transcribe(audio, "hola mundo")
    assert consumed == [True]
    assert result["metrics"]["wer"] == 0
    assert result["transcript"] == "Hola mundo"
    assert result["scope"] == "transcription_only_no_fraud_detection"


def test_missing_audio_fails_before_inference():
    transcriber = Transcriber.__new__(Transcriber)
    with pytest.raises(ValueError, match="No existe"):
        transcriber.transcribe(Path("missing-unique-audio.wav"))
