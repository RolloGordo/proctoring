from pathlib import Path
from unittest.mock import Mock

import pytest

import audio_runtime
import tasks

EVENT = "00000000-0000-4000-8000-000000000001"


def test_worker_downloads_measures_posts_and_cleans(monkeypatch):
    paths = []

    def download(job, path):
        paths.append(path)
        path.write_bytes(b"test fixture")

    measurement = {
        "transcript": "pregunta",
        "similarity": 0.99,
        "synthetic_voice_score": 0.01,
        "model_versions": {"asr": "fake-test"},
    }
    post = Mock(return_value={"alerted": False})
    monkeypatch.setattr(tasks, "INTERNAL_TOKEN", "test-only")
    monkeypatch.setattr(
        tasks,
        "_get",
        lambda _: {
            "question_statement": "pregunta",
            "similarity_threshold": 0.6,
            "synthetic_threshold": 0.5,
        },
    )
    monkeypatch.setattr(tasks, "download_audio", download)
    monkeypatch.setattr(tasks, "measure_audio", lambda p, q: measurement)
    monkeypatch.setattr(tasks, "_post", post)
    assert tasks.analyze_audio(EVENT) == {"alerted": False}
    assert not paths[0].exists()
    assert post.call_args.args[1]["processing_ms"] >= 0
    assert "alerted" not in post.call_args.args[1]


def test_download_failure_never_posts_empty_success(monkeypatch):
    monkeypatch.setattr(tasks, "INTERNAL_TOKEN", "test-only")
    monkeypatch.setattr(tasks, "_get", lambda _: {})
    monkeypatch.setattr(tasks, "download_audio", Mock(side_effect=OSError("unavailable")))
    post = Mock()
    monkeypatch.setattr(tasks, "_post", post)
    with pytest.raises(OSError):
        tasks.analyze_audio(EVENT)
    post.assert_not_called()


@pytest.mark.parametrize("question", [None, "", "  "])
def test_missing_question_and_disabled_synthetic_stay_null(monkeypatch, question):
    import spikes.synthetic_voice

    monkeypatch.setattr(spikes.synthetic_voice, "decode_audio", lambda _: [0.0] * 1600)
    monkeypatch.setattr(
        audio_runtime, "asr_model", lambda: Mock(transcribe=lambda _: {"transcript": "hola"})
    )
    similarity = Mock()
    monkeypatch.setattr(audio_runtime, "similarity_model", similarity)
    monkeypatch.setattr(audio_runtime, "synthetic_model", lambda: None)
    measured = audio_runtime.measure_audio(Path("unused"), question)
    assert measured["similarity"] is None
    assert measured["synthetic_voice_score"] is None
    similarity.assert_not_called()


@pytest.mark.parametrize("path", ["../secret", "/absolute", "a/../b", "a\\b", "a//b"])
def test_storage_path_validation(monkeypatch, tmp_path, path):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    with pytest.raises(ValueError, match="path"):
        audio_runtime.download_audio(
            {"audio_bucket": "audio-segments", "audio_path": path}, tmp_path / "audio"
        )


def test_invalid_event_rejected_before_network():
    with pytest.raises(ValueError):
        tasks.analyze_audio("../../bad")


def test_disabled_detector_is_not_zero(monkeypatch):
    audio_runtime.synthetic_model.cache_clear()
    monkeypatch.delenv("AUDIO_SYNTHETIC_MODE", raising=False)
    assert audio_runtime.synthetic_model() is None
    audio_runtime.synthetic_model.cache_clear()
