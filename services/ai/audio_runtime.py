"""Audio adapters for the RQ task; no database writes or alert decisions."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

SIM_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
MAX_AUDIO_BYTES = 8_000_000

DEFAULT_ASR_PROVIDER = "deepgram"
ASR_PROVIDERS = ("deepgram", "faster-whisper")
LOCAL_ASR_EXTRA = "asr-local"


def download_audio(job: dict[str, Any], destination: Path) -> None:
    """Download a bounded private object from the configured Storage origin only.

    The job carries a short-lived signed URL, so the worker does not need the
    service role key -- that key bypasses RLS and opens every table and every
    bucket, and handing it out just to read a wav is giving away the master key.

    The old path stays as a fallback for the in-memory mode, where there is no
    storage to sign against.
    """
    signed = job.get("audio_url")
    if isinstance(signed, str) and signed:
        _download(signed, destination, headers={})
        return

    base = os.environ["SUPABASE_URL"].rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    ):
        raise ValueError("Storage requires HTTPS (except local development)")
    bucket = job["audio_bucket"]
    path = job["audio_path"]
    if not isinstance(bucket, str) or bucket != os.getenv("AUDIO_BUCKET", "audio-segments"):
        raise ValueError("Unexpected audio bucket")
    if (
        not isinstance(path, str)
        or path.startswith("/")
        or "\\" in path
        or any(p in {"", ".", ".."} for p in path.split("/"))
    ):
        raise ValueError("Invalid audio object path")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    if not key:
        raise ValueError("Missing Storage server credential")
    url = f"{base}/storage/v1/object/authenticated/{quote(bucket, safe='')}/{quote(path, safe='/')}"
    # Never forward server credentials through a redirect.
    _download(url, destination, headers={"Authorization": f"Bearer {key}", "apikey": key})


def _download(url: str, destination: Path, headers: dict[str, str]) -> None:
    """Fetch a bounded object. Both paths share the same limits on purpose.

    Never follows a redirect: on the service-role path that would forward the
    credential somewhere we did not choose.
    """
    with httpx.stream(
        "GET",
        url,
        headers=headers,
        timeout=10,
        follow_redirects=False,
    ) as response:
        response.raise_for_status()
        if int(response.headers.get("content-length", "0")) > MAX_AUDIO_BYTES:
            raise ValueError("Audio exceeds size limit")
        size = 0
        with destination.open("wb") as output:
            for block in response.iter_bytes():
                size += len(block)
                if size > MAX_AUDIO_BYTES:
                    raise ValueError("Audio exceeds size limit")
                output.write(block)
        if not size:
            raise ValueError("Empty audio")


def asr_provider() -> str:
    """Provider chosen by ``ASR_PROVIDER``; unset or blank means Deepgram."""
    name = os.getenv("ASR_PROVIDER", "").strip().lower() or DEFAULT_ASR_PROVIDER
    if name not in ASR_PROVIDERS:
        # The value is not echoed: someone may have pasted a secret in the wrong variable.
        raise ValueError(f"Unknown ASR_PROVIDER; expected one of: {', '.join(ASR_PROVIDERS)}")
    return name


@lru_cache(maxsize=1)
def _local_asr_model() -> Any:
    """Faster-Whisper is expensive to load, so only this one is cached.

    It is an optional extra, absent from the production image. Asking for it without the
    extra fails with an actionable message instead of a bare ``ModuleNotFoundError``.
    """
    if importlib.util.find_spec("faster_whisper") is None:
        raise RuntimeError(
            "ASR_PROVIDER=faster-whisper needs the optional extra "
            f"'{LOCAL_ASR_EXTRA}' (uv sync --extra {LOCAL_ASR_EXTRA})"
        )
    from spikes.transcribe import Transcriber

    return Transcriber("small", offline=True)


def asr_model() -> Any:
    """Return the configured transcriber (``.transcribe(path)`` and ``.version``).

    The provider is read on every call, so changing ``ASR_PROVIDER`` can never be masked
    by a cached instance. Deepgram is cheap to build and is deliberately not cached: its
    key and timeout are then always the current ones, and a missing key fails here,
    before any network request.

    There is no fallback between providers: a Deepgram misconfiguration must surface as
    a failed job, never as a transcript silently produced by another engine.
    """
    if asr_provider() == "deepgram":
        from deepgram_transcriber import DeepgramTranscriber

        return DeepgramTranscriber()
    return _local_asr_model()


def _asr_version(asr: Any) -> str:
    version = getattr(asr, "version", None)
    # A transcriber without an identifier is recorded as unknown, never mislabelled.
    return version if isinstance(version, str) and version else "asr-unknown"


@lru_cache(maxsize=1)
def similarity_model() -> Any:
    from spikes.similarity import SimilarityModel

    try:
        return SimilarityModel(SIM_REVISION, offline=True)
    except OSError:
        raise RuntimeError(
            "Similarity model could not be loaded offline. Prepare the pinned model "
            "and mount its cache at SIMILARITY_CACHE_DIR (default: models). "
            "No model download was attempted."
        ) from None


class AasistScorer:
    """Experimental spoof score, NOT evidence of a second speaker.

    Explicit local configuration is required. No model downloads in the job.
    Source is executable Python: use only the reviewed official source.
    """

    def __init__(self) -> None:
        import torch

        source = Path(os.environ["AASIST_SOURCE"])
        config = Path(os.environ["AASIST_CONFIG"])
        weights = Path(os.environ["AASIST_WEIGHTS"])
        spec = importlib.util.spec_from_file_location("worker_aasist", source)
        if spec is None or spec.loader is None:
            raise ValueError("Invalid AASIST source")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.model = module.Model(json.loads(config.read_text())["model_config"]).cpu().eval()
        self.model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
        self.version = (
            "aasist-experimental-sha256:" + hashlib.sha256(weights.read_bytes()).hexdigest()
        )

    def score(self, audio: Any) -> float:
        import numpy as np
        import torch

        scores = []
        with torch.inference_mode():
            for offset in range(0, len(audio), 64600):
                window = audio[offset : offset + 64600]
                window = np.tile(window, math.ceil(64600 / len(window)))[:64600]
                _, logits = self.model(torch.from_numpy(window).float().unsqueeze(0))
                scores.append(float(torch.softmax(logits, dim=1)[0, 0]))
        return sum(scores) / len(scores)


@lru_cache(maxsize=1)
def synthetic_model() -> AasistScorer | None:
    mode = os.getenv("AUDIO_SYNTHETIC_MODE", "disabled")
    if mode == "disabled":
        return None
    if mode != "aasist-experimental":
        raise ValueError("Unknown AUDIO_SYNTHETIC_MODE")
    return AasistScorer()


def measure_audio(path: Path, question: str | None) -> dict[str, Any]:
    from spikes.synthetic_voice import decode_audio

    waveform = decode_audio(path)  # Bounds duration/decoded memory before ASR.
    asr = asr_model()
    # Validate local prerequisites before a billable external transcription request.
    model = similarity_model() if question is not None and question.strip() else None
    detector = synthetic_model()
    transcript = str(asr.transcribe(path)["transcript"])
    similarity = None
    versions: dict[str, str] = {"asr": _asr_version(asr), "sim": "not-applicable"}
    if model is not None:
        try:
            similarity = model.score(question, transcript)
            versions["sim"] = f"multilingual-MiniLM-L12-v2@{SIM_REVISION}"
        except ValueError:
            # Long texts must not be silently truncated to manufacture similarity.
            versions["sim"] = "unavailable:input-outside-model-context"
    score = detector.score(waveform) if detector else None
    versions["tts_det"] = detector.version if detector else "disabled:awaiting-dataset-validation"
    for number in (similarity, score):
        if number is not None and (not math.isfinite(number) or not 0 <= number <= 1):
            raise ValueError("Model returned invalid score")
    return {
        "transcript": transcript,
        "similarity": similarity,
        "synthetic_voice_score": score,
        "model_versions": versions,
    }
