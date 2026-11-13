from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import parakeet_transcriber as parakeet


class FakeRecognizer:
    def __init__(self, text: str = "hola mundo") -> None:
        self.text = text

    def create_stream(self) -> SimpleNamespace:
        return SimpleNamespace(accept_waveform=lambda *_: None)

    def decode_stream(self, stream: SimpleNamespace) -> None:
        stream.result = SimpleNamespace(
            text=self.text,
            tokens=["hola", "mundo"],
            timestamps=[0.1, 0.5],
            ys_log_probs=[-0.1, -0.3],
        )


def make_model_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    artifact = parakeet.ARTIFACTS["fp32"]
    for filename, checksum in artifact.files.items():
        path = model_dir / filename
        path.write_bytes(filename.encode())
        monkeypatch.setitem(artifact.files, filename, parakeet._sha256(path))
    parakeet.validate_model_files.cache_clear()
    return model_dir


def test_transcriber_uses_simulated_recognizer_and_returns_quality_signals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = make_model_dir(tmp_path, monkeypatch)
    model = parakeet.ParakeetTranscriber(model_dir, precision="fp32", recognizer=FakeRecognizer())
    result = model.transcribe(Path("unused.wav"), waveform=np.zeros(16_000, dtype=np.float32))
    assert result["transcript"] == "hola mundo"
    assert result["words_per_second"] == 2.0
    assert result["mean_ys_log_prob"] == pytest.approx(-0.2)
    assert result["timestamps"] == [0.1, 0.5]


def test_missing_model_directory_is_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(parakeet.ParakeetConfigurationError, match="does not exist"):
        parakeet.validate_model_files(str(tmp_path / "absent"), "fp32")


def test_configuration_failure_never_uses_local_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import audio_runtime
    import spikes.synthetic_voice

    monkeypatch.setattr(spikes.synthetic_voice, "decode_audio", lambda _: np.zeros(1600))
    monkeypatch.setattr(audio_runtime, "synthetic_model", lambda: None)
    monkeypatch.setenv("ASR_PROVIDER", "parakeet")
    monkeypatch.setenv("ASR_FALLBACK_PROVIDER", "faster-whisper")
    monkeypatch.setenv("PARAKEET_MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(
        audio_runtime,
        "asr_model",
        lambda: (_ for _ in ()).throw(parakeet.ParakeetConfigurationError("bad model dir")),
    )

    def fallback():
        pytest.fail("configuration errors must not trigger fallback")

    monkeypatch.setattr(audio_runtime, "_get_local_asr", fallback)
    with pytest.raises(parakeet.ParakeetConfigurationError):
        audio_runtime.measure_audio(Path("unused"), None)


def test_runtime_failure_uses_local_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import audio_runtime
    import spikes.synthetic_voice

    monkeypatch.setattr(spikes.synthetic_voice, "decode_audio", lambda _: np.zeros(1600))
    monkeypatch.setattr(audio_runtime, "synthetic_model", lambda: None)
    monkeypatch.setenv("ASR_PROVIDER", "parakeet")
    monkeypatch.setenv("ASR_FALLBACK_PROVIDER", "faster-whisper")
    monkeypatch.setenv("PARAKEET_MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(
        audio_runtime,
        "asr_model",
        lambda: (_ for _ in ()).throw(parakeet.ParakeetRuntimeError("decode failed")),
    )
    local = SimpleNamespace(
        version="faster-whisper-small-cpu-int8",
        transcribe=lambda _path: {"transcript": "respuesta local"},
    )
    monkeypatch.setattr(audio_runtime, "_get_local_asr", lambda: local)
    measured = audio_runtime.measure_audio(Path("unused"), None)
    assert measured["transcript"] == "respuesta local"
    assert "fallback_from=parakeet-tdt-0.6b-v3-fp32" in measured["model_versions"]["asr"]


def test_local_parakeet_configuration_does_not_require_deepgram_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import audio_runtime

    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.setenv("ASR_PROVIDER", "parakeet")
    monkeypatch.setenv("ASR_FALLBACK_PROVIDER", "none")
    monkeypatch.setenv("PARAKEET_MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(parakeet, "validate_parakeet_installation", lambda *_args: None)
    audio_runtime.validate_asr_configuration()
