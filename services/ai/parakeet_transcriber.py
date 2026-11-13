"""Pinned sherpa-onnx Parakeet TDT v3 transcription adapter."""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

LOGGER = logging.getLogger(__name__)
SAMPLE_RATE = 16_000
SHERPA_ONNX_VERSION = "2.0.1"
DEFAULT_PRECISION = "fp32"
DEFAULT_NUM_THREADS = 4
PRECISIONS = ("fp32", "int8")


@dataclass(frozen=True)
class ParakeetArtifact:
    repo_id: str
    revision: str
    files: dict[str, str]


ARTIFACTS = {
    "fp32": ParakeetArtifact(
        repo_id="csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3",
        revision="5fcc0122fe87e8365e339e467af90c67b746218f",
        files={
            "encoder.onnx": "36b758364dfddce472b9a9f75bf6049bbd35c886d7927e3eda80d4ceb3348512",
            "encoder.weights": "3af3f51af5f2d01dbbf5af47d42c7962a2c205f11004254bb4f2b979862f39a8",
            "decoder.onnx": "caed31af1bb08edcc09a01a1c3cbb4d4eb5bfdb9c4e5f307012f84bbf5dbfdbc",
            "joiner.onnx": "0f294e5ba9021a3d80e492de94abe4c116f0afce78452c7debb5dd07690d0340",
            "tokens.txt": "d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d",
        },
    ),
    "int8": ParakeetArtifact(
        repo_id="csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8",
        revision="ed5d745623472f97cfc2e6c2916ee248798fc5a8",
        files={
            "encoder.int8.onnx": "1afbe69c1ffdabee94755f42e4daf1d93549131a3da11356bda84fcef0f2c479",
            "decoder.int8.onnx": "0222a86147299d4dee90edf95b6d13827edb42ad8b7c9cf0b2582f030937c0b5",
            "joiner.int8.onnx": "cbd02f3696e9944970111fb439d9c3fd365a80374565f13f2b9c7007d253fc98",
            "tokens.txt": "d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d",
        },
    ),
}


class ParakeetConfigurationError(ValueError):
    """Invalid or incomplete Parakeet selection; never eligible for fallback."""


class ParakeetRuntimeError(RuntimeError):
    """A valid pinned Parakeet installation failed while initializing or decoding."""


def parakeet_precision() -> str:
    precision = os.getenv("PARAKEET_PRECISION", DEFAULT_PRECISION).strip().lower()
    if precision not in PRECISIONS:
        raise ParakeetConfigurationError("PARAKEET_PRECISION must be fp32 or int8")
    return precision


def parakeet_model_dir() -> Path:
    raw = os.getenv("PARAKEET_MODEL_DIR", "").strip()
    if not raw:
        raise ParakeetConfigurationError(
            "PARAKEET_MODEL_DIR is required when ASR_PROVIDER=parakeet"
        )
    return Path(raw).expanduser()


def parakeet_num_threads() -> int:
    raw = os.getenv("PARAKEET_NUM_THREADS", str(DEFAULT_NUM_THREADS)).strip()
    try:
        value = int(raw)
    except ValueError:
        raise ParakeetConfigurationError(
            "PARAKEET_NUM_THREADS must be a positive integer"
        ) from None
    if value < 1:
        raise ParakeetConfigurationError("PARAKEET_NUM_THREADS must be a positive integer")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=4)
def validate_model_files(model_dir_value: str, precision: str) -> tuple[Path, ...]:
    """Check fixed file names and hashes once per worker process and model directory."""
    if precision not in PRECISIONS:
        raise ParakeetConfigurationError("PARAKEET_PRECISION must be fp32 or int8")
    model_dir = Path(model_dir_value).expanduser()
    if not model_dir.is_dir():
        raise ParakeetConfigurationError(f"Parakeet model directory does not exist: {model_dir}")
    artifact = ARTIFACTS[precision]
    checked: list[Path] = []
    for filename, expected_sha256 in artifact.files.items():
        path = model_dir / filename
        if not path.is_file():
            raise ParakeetConfigurationError(f"Missing Parakeet {precision} file: {path}")
        if _sha256(path) != expected_sha256:
            raise ParakeetConfigurationError(f"Parakeet SHA-256 mismatch: {filename}")
        checked.append(path)
    return tuple(checked)


def validate_parakeet_installation(model_dir: Path | str, precision: str, num_threads: int) -> None:
    """Validate static config without creating an ONNX Runtime session."""
    if importlib.util.find_spec("sherpa_onnx") is None:
        raise ParakeetConfigurationError(
            "ASR_PROVIDER=parakeet requires the optional extra 'asr-parakeet' "
            "(uv sync --extra asr-parakeet)"
        )
    if num_threads < 1:
        raise ParakeetConfigurationError("PARAKEET_NUM_THREADS must be a positive integer")
    validate_model_files(str(Path(model_dir).expanduser()), precision)


class ParakeetTranscriber:
    """Offline recognizer implementing the AI worker's transcriber contract."""

    def __init__(
        self,
        model_dir: Path | str,
        *,
        precision: str = DEFAULT_PRECISION,
        num_threads: int = DEFAULT_NUM_THREADS,
        recognizer: Any | None = None,
    ) -> None:
        if precision not in PRECISIONS:
            raise ParakeetConfigurationError("PARAKEET_PRECISION must be fp32 or int8")
        if num_threads < 1:
            raise ParakeetConfigurationError("PARAKEET_NUM_THREADS must be a positive integer")
        self.model_dir = Path(model_dir).expanduser()
        self.precision = precision
        self.num_threads = num_threads
        self.artifact = ARTIFACTS[precision]
        files = validate_model_files(str(self.model_dir), precision)
        if precision == "int8":
            message = (
                "Parakeet INT8 is experimental: P02 measured 58.44% overall WER, "
                "8/30 empty transcripts and 2/30 foreign-language heuristic matches; "
                "FP32 is the validated primary candidate."
            )
            warnings.warn(message, RuntimeWarning, stacklevel=2)
            LOGGER.warning(message)
        if recognizer is not None:
            self._recognizer = recognizer
        else:
            try:
                import sherpa_onnx  # type: ignore[import-untyped]

                suffix = ".int8.onnx" if precision == "int8" else ".onnx"
                self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                    encoder=str(self.model_dir / f"encoder{suffix}"),
                    decoder=str(self.model_dir / f"decoder{suffix}"),
                    joiner=str(self.model_dir / f"joiner{suffix}"),
                    tokens=str(self.model_dir / "tokens.txt"),
                    num_threads=num_threads,
                    decoding_method="greedy_search",
                    model_type="nemo_transducer",
                )
            except Exception as exc:  # noqa: BLE001 - native runtime exposes varied exceptions
                raise ParakeetRuntimeError(
                    f"sherpa-onnx could not initialize the verified {precision} model "
                    f"from {self.model_dir} ({type(exc).__name__})"
                ) from None
        self._checked_files = files

    @property
    def version(self) -> str:
        return (
            f"parakeet-tdt-0.6b-v3-{self.precision};sherpa-onnx={SHERPA_ONNX_VERSION};"
            f"revision={self.artifact.revision}"
        )

    def transcribe(
        self,
        audio: Path,
        reference: str | None = None,
        *,
        waveform: np.ndarray | None = None,
    ) -> dict[str, Any]:
        if waveform is None:
            from spikes.synthetic_voice import decode_audio

            try:
                waveform = decode_audio(Path(audio))
            except (OSError, ValueError):
                raise
        duration = len(waveform) / SAMPLE_RATE
        if duration <= 0:
            raise ValueError("Audio has no samples")
        started = perf_counter()
        try:
            stream = self._recognizer.create_stream()
            stream.accept_waveform(SAMPLE_RATE, waveform)
            self._recognizer.decode_stream(stream)
            result = stream.result
        except Exception as exc:  # noqa: BLE001 - native runtime exposes varied exceptions
            raise ParakeetRuntimeError(
                f"sherpa-onnx inference failed for verified {self.precision} model "
                f"({type(exc).__name__})"
            ) from None
        elapsed = perf_counter() - started
        transcript = str(result.text).strip()
        tokens = list(getattr(result, "tokens", []) or [])
        timestamps = list(getattr(result, "timestamps", []) or [])
        log_probs = [float(value) for value in (getattr(result, "ys_log_probs", []) or [])]
        mean_log_prob = sum(log_probs) / len(log_probs) if log_probs else None
        words_per_second = len(transcript.split()) / duration if transcript else 0.0
        segment = {
            "start": min(timestamps) if timestamps else 0.0,
            "end": max(timestamps) if timestamps else duration,
            "text": transcript,
            "tokens": tokens,
            "timestamps": timestamps,
            "mean_ys_log_prob": mean_log_prob,
        }
        output: dict[str, Any] = {
            "provider": "parakeet",
            "model": "parakeet-tdt-0.6b-v3",
            "version": self.version,
            "precision": self.precision,
            "transcript": transcript,
            "audio_seconds": duration,
            "inference_seconds": elapsed,
            "words_per_second": words_per_second,
            "tokens": tokens,
            "timestamps": timestamps,
            "mean_ys_log_prob": mean_log_prob,
            "segments": [segment] if transcript else [],
        }
        if reference is not None:
            from spikes.metrics import word_errors

            output["reference"] = reference
            output["metrics"] = word_errors(reference, transcript)
        return output


@lru_cache(maxsize=4)
def _cached_model(model_dir: str, precision: str, num_threads: int) -> ParakeetTranscriber:
    return ParakeetTranscriber(model_dir, precision=precision, num_threads=num_threads)
