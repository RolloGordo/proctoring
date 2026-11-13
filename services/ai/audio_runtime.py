"""Audio adapters for the RQ task; no database writes or alert decisions."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import math
import os
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

logger = logging.getLogger(__name__)

SIM_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
MAX_AUDIO_BYTES = 8_000_000

DEFAULT_ASR_PROVIDER = "faster-whisper"
ASR_PROVIDERS = ("deepgram", "faster-whisper", "parakeet")
LOCAL_ASR_EXTRA = "asr-local"
PARAKEET_ASR_EXTRA = "asr-parakeet"
PARAKEET_QUALITY_CALIBRATION_SOURCE = (
    "results/quality-gate-parakeet.json (Parakeet INT8 outputs, speaker P01)"
)
PARAKEET_ENGLISH_MARKERS = frozenset(
    {
        "what",
        "is",
        "it",
        "why",
        "never",
        "looking",
        "okay",
        "my",
        "that",
        "now",
        "not",
        "going",
        "to",
        "be",
        "idea",
        "theyre",
        "they",
        "big",
        "side",
    }
)

DEFAULT_ASR_LOCAL_MODEL = "small"
ASR_LOCAL_MODELS = ("tiny", "base", "small")

DEFAULT_ASR_FALLBACK_PROVIDER = "none"
ASR_FALLBACK_PROVIDERS = ("deepgram", "faster-whisper", "none")

DEFAULT_SIMILARITY_BACKEND = "torch"
SIMILARITY_BACKENDS = ("torch", "onnx-int8", "onnx-fp32")

DEFAULT_SIMILARITY_ONNX_VOCAB = "es_en"
SIMILARITY_ONNX_VOCAB_MODES = ("es_en", "full")

DEFAULT_ENFORCE_MEMORY_BUDGET = False

DEFAULT_ASR_LOCAL_VAD_FILTER = True
DEFAULT_ASR_LOCAL_VAD_THRESHOLD = 0.3

# Quality gate thresholds calibrated on 28 in-sample audios (8 MediaSpeech + 20 from a
# single speaker P01 across 5 conditions) without independent held-out validation.
DEFAULT_MIN_WORDS_PER_SECOND = 0.50
DEFAULT_MAX_NO_SPEECH_PROB = 0.60
DEFAULT_MIN_AVG_LOGPROB = -0.60
DEFAULT_MAX_COMPRESSION_RATIO = 1.85
DEFAULT_HALLUCINATION_PHRASES: tuple[str, ...] = (
    "suscríbete",
    "suscribete",
    "más información en www",
    "mas informacion en www",
    "subtítulos realizados por",
    "subtitulos realizados por",
    "amara.org",
    "gracias por ver",
)

# Latency budget for fallback: min(4.5 s, 10.0 s - elapsed - 1.5 s).
DEFAULT_LATENCY_BUDGET_SECONDS = 10.0
DEFAULT_FALLBACK_MAX_TIMEOUT_SECONDS = 4.5
DEFAULT_POST_ASR_RESERVE_SECONDS = 1.5

# Pre-flight container memory thresholds (bytes) measured in Stage 0 and 2B Docker benchmarks:
# 1) SIMILARITY_BACKEND=torch (PyTorch MiniLM FP32):
# - Deepgram + SimilarityModel (torch) peaks at ~1,124 MiB RSS -> 1,280 MiB min.
# - faster-whisper tiny/base + SimilarityModel (torch) peaks at ~1,290-1,331 MiB -> 1,500 MiB min.
# - faster-whisper small + SimilarityModel (torch) peaks at ~1,698 MiB RSS -> 1,800 MiB min.
MIN_MEM_DEEPGRAM_WITH_SIM_BYTES = 1_280 * 1024 * 1024
MIN_MEM_WHISPER_TINY_BASE_WITH_SIM_BYTES = 1_500 * 1024 * 1024
MIN_MEM_WHISPER_SMALL_WITH_SIM_BYTES = 1_800 * 1024 * 1024

# 2) SIMILARITY_BACKEND=onnx-int8 (ONNX Runtime MiniLM INT8):
# - Deepgram + OnnxSimilarityModel (int8, es_en) peaks at ~225 MiB RSS -> 384 MiB min.
# - faster-whisper tiny + OnnxSimilarityModel (int8, es_en) peaks at ~435 MiB RSS -> 500 MiB min.
# - faster-whisper base + OnnxSimilarityModel (int8, es_en) peaks at ~545 MiB RSS -> 640 MiB min.
# - faster-whisper small + OnnxSimilarityModel (int8, es_en) peaks at ~980 MiB RSS -> 1,150 MiB min.
MIN_MEM_DEEPGRAM_WITH_ONNX_INT8_BYTES = 384 * 1024 * 1024
MIN_MEM_WHISPER_TINY_WITH_ONNX_INT8_BYTES = 500 * 1024 * 1024
MIN_MEM_WHISPER_BASE_WITH_ONNX_INT8_BYTES = 640 * 1024 * 1024
MIN_MEM_WHISPER_SMALL_WITH_ONNX_INT8_BYTES = 1_150 * 1024 * 1024

# 3) SIMILARITY_BACKEND=onnx-fp32 (ONNX Runtime MiniLM FP32):
# - Deepgram + OnnxSimilarityModel (fp32, es_en) peaks at ~485 MiB RSS -> 640 MiB min.
# - faster-whisper tiny/base + OnnxSimilarityModel (fp32) peaks at ~720-820 MiB -> 900 MiB min.
# - faster-whisper small + OnnxSimilarityModel (fp32) peaks at ~1,210 MiB RSS -> 1,400 MiB min.
MIN_MEM_DEEPGRAM_WITH_ONNX_FP32_BYTES = 640 * 1024 * 1024
MIN_MEM_WHISPER_TINY_BASE_WITH_ONNX_FP32_BYTES = 900 * 1024 * 1024
MIN_MEM_WHISPER_SMALL_WITH_ONNX_FP32_BYTES = 1_400 * 1024 * 1024

# Existing Docker evidence measured Parakeet FP32 + PyTorch similarity at a 3,171.4 MB
# cgroup peak, while FP32 OOMed under 2 GiB. Four GiB is the conservative minimum that
# keeps that observed peak below the 85% operating margin. The ONNX-int8 combination has
# not been measured separately, so it temporarily uses the same conservative bound.
MIN_MEM_PARAKEET_FP32_WITH_SIM_BYTES = 4 * 1024 * 1024 * 1024
MIN_MEM_PARAKEET_INT8_WITH_SIM_BYTES = 1_280 * 1024 * 1024

CGROUP_V2_MEMORY_MAX = Path("/sys/fs/cgroup/memory.max")
CGROUP_V1_MEMORY_LIMIT = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")


def _parse_bool_env(var_name: str, default: bool) -> bool:
    raw = os.getenv(var_name)
    if raw is None or not raw.strip():
        return default
    norm = raw.strip().lower()
    if norm in ("1", "true", "yes", "on"):
        return True
    if norm in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{var_name} must be a boolean (true or false)")


def _parse_float_env(
    var_name: str,
    default: float,
    *,
    min_val: float | None = None,
    max_val: float | None = None,
    strict_min: bool = False,
    strict_max: bool = False,
) -> float:
    raw = os.getenv(var_name)
    if raw is None or not raw.strip():
        return default
    try:
        val = float(raw.strip())
    except ValueError:
        raise ValueError(f"{var_name} must be a finite number") from None
    if not math.isfinite(val):
        raise ValueError(f"{var_name} must be a finite number")
    if min_val is not None and (val <= min_val if strict_min else val < min_val):
        op = ">" if strict_min else ">="
        raise ValueError(f"{var_name} must be {op} {min_val}")
    if max_val is not None and (val >= max_val if strict_max else val > max_val):
        op = "<" if strict_max else "<="
        raise ValueError(f"{var_name} must be {op} {max_val}")
    return val


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


def asr_local_model() -> str:
    """Local Whisper model size chosen by ``ASR_LOCAL_MODEL``; defaults to ``small``."""
    name = os.getenv("ASR_LOCAL_MODEL", "").strip().lower() or DEFAULT_ASR_LOCAL_MODEL
    if name not in ASR_LOCAL_MODELS:
        raise ValueError(f"Unknown ASR_LOCAL_MODEL; expected one of: {', '.join(ASR_LOCAL_MODELS)}")
    return name


def asr_fallback_provider() -> str:
    """Fallback provider chosen by ``ASR_FALLBACK_PROVIDER``; defaults to ``none``."""
    name = os.getenv("ASR_FALLBACK_PROVIDER", "").strip().lower() or DEFAULT_ASR_FALLBACK_PROVIDER
    if name not in ASR_FALLBACK_PROVIDERS:
        raise ValueError(
            f"Unknown ASR_FALLBACK_PROVIDER; expected one of: {', '.join(ASR_FALLBACK_PROVIDERS)}"
        )
    return name


def parakeet_settings() -> tuple[str, Path, int]:
    from parakeet_transcriber import (
        parakeet_model_dir,
        parakeet_num_threads,
        parakeet_precision,
    )

    return parakeet_precision(), parakeet_model_dir(), parakeet_num_threads()


def validate_asr_configuration() -> None:
    """Validate selected provider, local artifacts, and only the credentials it needs."""
    provider = asr_provider()
    fallback = asr_fallback_provider()
    if provider == "deepgram":
        if fallback == "faster-whisper":
            raise ValueError(
                "ASR_FALLBACK_PROVIDER=faster-whisper is supported only when ASR_PROVIDER=parakeet"
            )
        from deepgram_transcriber import _read_key

        _read_key()
        return
    if provider == "parakeet":
        if fallback == "deepgram":
            raise ValueError(
                "Parakeet supports only ASR_FALLBACK_PROVIDER=faster-whisper or none; "
                "select a local fallback explicitly"
            )
        from parakeet_transcriber import validate_parakeet_installation

        precision, model_dir, threads = parakeet_settings()
        validate_parakeet_installation(model_dir, precision, threads)
        if fallback == "faster-whisper":
            asr_local_model()
            if importlib.util.find_spec("faster_whisper") is None:
                raise ValueError(
                    "ASR_FALLBACK_PROVIDER=faster-whisper needs the optional extra "
                    f"'{LOCAL_ASR_EXTRA}' (uv sync --extra {LOCAL_ASR_EXTRA})"
                )
        return
    if provider == "faster-whisper":
        if fallback == "faster-whisper":
            raise ValueError("ASR_FALLBACK_PROVIDER=faster-whisper cannot fall back to itself")
        asr_local_model()
        if importlib.util.find_spec("faster_whisper") is None:
            raise ValueError(
                "ASR_PROVIDER=faster-whisper needs the optional extra "
                f"'{LOCAL_ASR_EXTRA}' (uv sync --extra {LOCAL_ASR_EXTRA})"
            )
        if fallback == "deepgram":
            from deepgram_transcriber import _read_key

            _read_key()
        return
    if fallback == "faster-whisper":
        raise ValueError(
            "ASR_FALLBACK_PROVIDER=faster-whisper is valid only when ASR_PROVIDER=parakeet"
        )
    if fallback == "deepgram":
        from deepgram_transcriber import _read_key

        _read_key()


def parakeet_runtime_status() -> dict[str, Any]:
    """Non-loading status for /health; never checks or returns credential values."""
    try:
        provider = asr_provider()
    except ValueError as exc:
        return {
            "asr_precision": None,
            "asr_model_dir": None,
            "asr_model_revision": None,
            "asr_model_loaded": False,
            "asr_model_files_verified": False,
            "asr_load_strategy": None,
            "asr_configuration_error": f"invalid-config:{exc}",
        }
    if provider != "parakeet":
        return {
            "asr_precision": None,
            "asr_model_dir": None,
            "asr_model_revision": None,
            "asr_model_loaded": False,
            "asr_model_files_verified": False,
            "asr_load_strategy": None,
        }
    from parakeet_transcriber import ARTIFACTS, _cached_model, validate_model_files

    try:
        precision, model_dir, threads = parakeet_settings()
        loaded = _cached_model.cache_info().currsize > 0
        validate_model_files(str(model_dir), precision)
        files_verified = True
        error = None
    except (ValueError, OSError) as exc:
        precision, model_dir, threads, loaded = None, None, None, False
        files_verified = False
        error = f"invalid-config:{exc}"
    return {
        "asr_precision": precision,
        "asr_model_dir": str(model_dir) if model_dir else None,
        "asr_model_revision": ARTIFACTS[precision].revision if precision else None,
        "asr_model_loaded": loaded,
        "asr_model_files_verified": files_verified,
        "asr_num_threads": threads,
        "asr_load_strategy": "preloaded-in-process" if loaded else "lazy-after-fork",
        "asr_configuration_error": error,
    }


def asr_fallback_on_empty() -> bool:
    """Whether an empty Whisper transcript triggers fallback when fallback is enabled."""
    return _parse_bool_env("ASR_FALLBACK_ON_EMPTY", True)


def similarity_backend() -> str:
    """Similarity backend chosen by ``SIMILARITY_BACKEND``; defaults to ``torch``."""
    name = os.getenv("SIMILARITY_BACKEND", "").strip().lower() or DEFAULT_SIMILARITY_BACKEND
    if name not in SIMILARITY_BACKENDS:
        raise ValueError(
            f"Unknown SIMILARITY_BACKEND; expected one of: {', '.join(SIMILARITY_BACKENDS)}"
        )
    return name


def similarity_onnx_vocab() -> str:
    """Vocabulary mode for ONNX similarity model (``es_en`` default or ``full``)."""
    name = os.getenv("SIMILARITY_ONNX_VOCAB", "").strip().lower() or DEFAULT_SIMILARITY_ONNX_VOCAB
    if name not in SIMILARITY_ONNX_VOCAB_MODES:
        raise ValueError(
            "Unknown SIMILARITY_ONNX_VOCAB; expected one of: "
            f"{', '.join(SIMILARITY_ONNX_VOCAB_MODES)}"
        )
    return name


def asr_enforce_memory_budget() -> bool:
    """Whether an insufficient container memory limit aborts startup (default False)."""
    return _parse_bool_env("ASR_ENFORCE_MEMORY_BUDGET", DEFAULT_ENFORCE_MEMORY_BUDGET)


def asr_local_vad_filter() -> bool:
    """Whether Faster-Whisper applies Silero VAD filtering (default True)."""
    return _parse_bool_env("ASR_LOCAL_VAD_FILTER", DEFAULT_ASR_LOCAL_VAD_FILTER)


def asr_local_vad_threshold() -> float:
    """Silero VAD speech probability threshold for Faster-Whisper (default 0.3)."""
    return _parse_float_env(
        "ASR_LOCAL_VAD_THRESHOLD",
        DEFAULT_ASR_LOCAL_VAD_THRESHOLD,
        min_val=0.0,
        max_val=1.0,
        strict_min=True,
        strict_max=True,
    )


def quality_gate_config() -> dict[str, Any]:
    """Read and validate quality gate thresholds from environment variables."""
    min_wps = _parse_float_env(
        "ASR_MIN_WORDS_PER_SECOND",
        DEFAULT_MIN_WORDS_PER_SECOND,
        min_val=0.0,
    )
    max_nsp = _parse_float_env(
        "ASR_MAX_NO_SPEECH_PROB",
        DEFAULT_MAX_NO_SPEECH_PROB,
        min_val=0.0,
        max_val=1.0,
    )
    min_lp = _parse_float_env(
        "ASR_MIN_AVG_LOGPROB",
        DEFAULT_MIN_AVG_LOGPROB,
        max_val=0.0,
        strict_max=True,
    )
    max_cr = _parse_float_env(
        "ASR_MAX_COMPRESSION_RATIO",
        DEFAULT_MAX_COMPRESSION_RATIO,
        min_val=0.0,
        strict_min=True,
    )
    raw_phrases = os.getenv("ASR_HALLUCINATION_PHRASES")
    if raw_phrases is None:
        phrases = DEFAULT_HALLUCINATION_PHRASES
    else:
        phrases = tuple(p.strip().lower() for p in raw_phrases.split(",") if p.strip())
    return {
        "fallback_on_empty": asr_fallback_on_empty(),
        "min_words_per_second": min_wps,
        "max_no_speech_prob": max_nsp,
        "min_avg_logprob": min_lp,
        "max_compression_ratio": max_cr,
        "hallucination_phrases": phrases,
    }


def parakeet_quality_gate_config() -> dict[str, Any]:
    min_wps = _parse_float_env(
        "PARAKEET_MIN_WORDS_PER_SECOND",
        DEFAULT_MIN_WORDS_PER_SECOND,
        min_val=0.0,
    )
    raw_markers = os.getenv("PARAKEET_MIN_ENGLISH_MARKERS", "2").strip()
    try:
        min_markers = int(raw_markers)
    except ValueError:
        raise ValueError("PARAKEET_MIN_ENGLISH_MARKERS must be a positive integer") from None
    if min_markers < 1:
        raise ValueError("PARAKEET_MIN_ENGLISH_MARKERS must be a positive integer")
    return {
        "min_words_per_second": min_wps,
        "min_english_markers": min_markers,
        "hallucination_phrases": DEFAULT_HALLUCINATION_PHRASES,
        "calibration_source": PARAKEET_QUALITY_CALIBRATION_SOURCE,
        "calibration_precision": "int8",
    }


def evaluate_parakeet_quality(result: dict[str, Any], config: dict[str, Any]) -> list[str]:
    """Return informational confidence reasons only; never selects another provider."""
    transcript = str(result.get("transcript") or "").strip()
    reasons: list[str] = []
    if not transcript:
        reasons.append("empty_transcript")
        return reasons
    words = transcript.split()
    duration = result.get("audio_seconds")
    if isinstance(duration, int | float) and not isinstance(duration, bool) and duration > 0:
        words_per_second = len(words) / float(duration)
        if words_per_second < float(config["min_words_per_second"]):
            reasons.append("low_words_per_second")
    from spikes.metrics import normalize

    normalized_words = set(normalize(transcript))
    if len(normalized_words.intersection(PARAKEET_ENGLISH_MARKERS)) >= int(
        config["min_english_markers"]
    ):
        reasons.append("foreign_language_heuristic")
    folded = transcript.casefold()
    if any(phrase.casefold() in folded for phrase in config["hallucination_phrases"]):
        reasons.append("known_hallucination_phrase")
    return reasons


def compute_fallback_timeout(elapsed_seconds: float) -> float:
    """Remaining time budget for Deepgram fallback: min(4.5s, 10s - elapsed - 1.5s)."""
    budget = _parse_float_env(
        "ASR_LATENCY_BUDGET_SECONDS",
        DEFAULT_LATENCY_BUDGET_SECONDS,
        min_val=0.0,
        strict_min=True,
    )
    max_timeout = _parse_float_env(
        "ASR_FALLBACK_MAX_TIMEOUT_SECONDS",
        DEFAULT_FALLBACK_MAX_TIMEOUT_SECONDS,
        min_val=0.0,
        strict_min=True,
    )
    reserve = _parse_float_env(
        "ASR_POST_ASR_RESERVE_SECONDS",
        DEFAULT_POST_ASR_RESERVE_SECONDS,
        min_val=0.0,
    )
    remaining = budget - max(0.0, float(elapsed_seconds)) - reserve
    return min(max_timeout, remaining)


def evaluate_asr_quality(
    result: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> tuple[bool, str | None]:
    """Decide whether a local Whisper transcription is acceptable or needs fallback.

    Returns ``(passed, reason)`` where ``reason`` is ``None`` when ``passed`` is True.
    """
    cfg = config if config is not None else quality_gate_config()
    transcript = str(result.get("transcript") or "").strip()
    if not transcript:
        if cfg["fallback_on_empty"]:
            return False, "empty_transcript"
        return True, None

    lower_text = transcript.lower()
    for phrase in cfg["hallucination_phrases"]:
        if phrase and phrase.lower() in lower_text:
            return False, "hallucination_phrase"

    wps: float | None = None
    raw_wps = result.get("words_per_second")
    if (
        isinstance(raw_wps, int | float)
        and not isinstance(raw_wps, bool)
        and math.isfinite(raw_wps)
    ):
        wps = float(raw_wps)
    else:
        raw_dur = result.get("audio_seconds")
        if (
            isinstance(raw_dur, int | float)
            and not isinstance(raw_dur, bool)
            and math.isfinite(raw_dur)
            and raw_dur > 0
        ):
            wps = len(transcript.split()) / float(raw_dur)
    if wps is not None and wps < float(cfg["min_words_per_second"]):
        return False, "low_words_per_second"

    segments = result.get("segments")
    if isinstance(segments, list) and segments:
        nsps = [
            float(s["no_speech_prob"])
            for s in segments
            if isinstance(s, dict) and s.get("no_speech_prob") is not None
        ]
        if nsps and max(nsps) > float(cfg["max_no_speech_prob"]):
            return False, "high_no_speech_prob"

        lps = [
            float(s["avg_logprob"])
            for s in segments
            if isinstance(s, dict) and s.get("avg_logprob") is not None
        ]
        if lps and min(lps) < float(cfg["min_avg_logprob"]):
            return False, "low_avg_logprob"

        crs = [
            float(s["compression_ratio"])
            for s in segments
            if isinstance(s, dict) and s.get("compression_ratio") is not None
        ]
        if crs and max(crs) > float(cfg["max_compression_ratio"]):
            return False, "high_compression_ratio"

    return True, None


@lru_cache(maxsize=1)
def _local_asr_model() -> Any:
    """Faster-Whisper is expensive to load, so only this one is cached.

    It is an optional extra, absent from the production image. Asking for it without the
    extra fails with an actionable message instead of a bare ``ModuleNotFoundError``.
    """
    model_name = asr_local_model()
    vad_filter = asr_local_vad_filter()
    vad_threshold = asr_local_vad_threshold()
    if importlib.util.find_spec("faster_whisper") is None:
        raise RuntimeError(
            "ASR_PROVIDER=faster-whisper needs the optional extra "
            f"'{LOCAL_ASR_EXTRA}' (uv sync --extra {LOCAL_ASR_EXTRA})"
        )
    from spikes.transcribe import Transcriber

    vad_params = {"threshold": vad_threshold} if vad_filter else None
    try:
        return Transcriber(
            model_name,
            offline=True,
            vad_filter=vad_filter,
            vad_parameters=vad_params,
        )
    except OSError as exc:
        raise RuntimeError(
            f"Faster-Whisper model '{model_name}' could not be loaded offline: {exc}"
        ) from None


# CTranslate2 (faster-whisper) spawns a C++ std::thread inside ReplicaPool on init.
# POSIX os.fork() does not clone background threads into the child process, so using a
# parent WhisperModel instance inside a forked child deadlocks waiting on the missing
# C++ worker thread, and destroying it in the child hangs on std::thread::join().
# If _local_asr_model was cached before fork(), detach the parent reference in the child
# so it is neither called nor destroyed, and let the child initialize its own pool.
_FORK_DETACHED_ASR_MODELS: list[Any] = []


def _detach_local_asr_after_fork() -> None:
    if (
        not hasattr(_local_asr_model, "_mock_name")
        and hasattr(_local_asr_model, "cache_info")
        and _local_asr_model.cache_info().currsize > 0
    ):
        _FORK_DETACHED_ASR_MODELS.append(_local_asr_model())
        _local_asr_model.cache_clear()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_detach_local_asr_after_fork)


def _get_local_asr() -> Any:
    """Validate local ASR settings and invalidate cache if model/VAD settings changed."""
    target_model = asr_local_model()
    target_vad = asr_local_vad_filter()
    target_threshold = asr_local_vad_threshold()
    if (
        not hasattr(_local_asr_model, "_mock_name")
        and hasattr(_local_asr_model, "cache_info")
        and _local_asr_model.cache_info().currsize > 0
    ):
        cached = _local_asr_model()
        cached_params = getattr(cached, "vad_parameters", None)
        expected_params = {"threshold": target_threshold} if target_vad else None
        if (
            getattr(cached, "model", target_model) != target_model
            or getattr(cached, "vad_filter", target_vad) != target_vad
            or cached_params != expected_params
        ):
            _local_asr_model.cache_clear()
    return _local_asr_model()


def asr_model() -> Any:
    """Return the configured transcriber (``.transcribe(path)`` and ``.version``).

    The provider is read on every call, so changing ``ASR_PROVIDER`` can never be masked
    by a cached instance. Deepgram is cheap to build and is deliberately not cached: its
    key and timeout are then always the current ones, and a missing key fails here,
    before any network request.

    There is no silent fallback on configuration errors: a missing key or uninstalled extra
    must surface immediately as a failed job, never masked by another engine.
    """
    validate_asr_configuration()
    provider = asr_provider()
    if provider == "deepgram":
        from deepgram_transcriber import DeepgramTranscriber

        return DeepgramTranscriber()
    if provider == "parakeet":
        return _get_parakeet_asr()
    return _get_local_asr()


def _get_parakeet_asr() -> Any:
    from parakeet_transcriber import _cached_model

    precision, model_dir, threads = parakeet_settings()
    from parakeet_transcriber import ParakeetConfigurationError, ParakeetRuntimeError

    try:
        return _cached_model(str(model_dir), precision, threads)
    except ParakeetConfigurationError:
        raise
    except ParakeetRuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalize native initialization failures
        raise ParakeetRuntimeError(
            f"Parakeet runtime initialization failed ({type(exc).__name__})"
        ) from None


def clear_parakeet_model_cache() -> None:
    from parakeet_transcriber import _cached_model

    _cached_model.cache_clear()


def _build_fallback_transcriber(timeout: float) -> Any:
    from deepgram_transcriber import DeepgramTranscriber

    return DeepgramTranscriber(timeout=timeout)


def _asr_version(asr: Any) -> str:
    version = getattr(asr, "version", None)
    # A transcriber without an identifier is recorded as unknown, never mislabelled.
    return version if isinstance(version, str) and version else "asr-unknown"


@lru_cache(maxsize=1)
def _cached_similarity_model(backend: str, vocab_mode: str) -> Any:
    if backend == "torch":
        from spikes.similarity import SimilarityModel

        try:
            return SimilarityModel(
                SIM_REVISION,
                offline=True,
                cache_dir=os.getenv("SIMILARITY_CACHE_DIR", "models"),
            )
        except OSError:
            raise RuntimeError(
                "Similarity model could not be loaded offline. Prepare the pinned model "
                "and mount its cache at SIMILARITY_CACHE_DIR (default: models). "
                "No model download was attempted."
            ) from None

    if (
        importlib.util.find_spec("onnxruntime") is None
        or importlib.util.find_spec("tokenizers") is None
    ):
        raise RuntimeError(
            f"SIMILARITY_BACKEND={backend} requires 'onnxruntime' and 'tokenizers' to be installed."
        )
    from spikes.similarity import OnnxSimilarityModel

    variant = "int8" if backend == "onnx-int8" else "fp32"
    try:
        return OnnxSimilarityModel(
            SIM_REVISION,
            variant=variant,
            vocab_mode=vocab_mode,
            offline=True,
            cache_dir=os.getenv("SIMILARITY_CACHE_DIR", "models"),
        )
    except OSError as exc:
        raise RuntimeError(
            f"ONNX similarity model ({backend}, vocab={vocab_mode}) could not be loaded "
            f"offline: {exc}"
        ) from None


def similarity_model() -> Any:
    return _cached_similarity_model(similarity_backend(), similarity_onnx_vocab())


similarity_model.cache_clear = _cached_similarity_model.cache_clear  # type: ignore[attr-defined]
similarity_model.cache_info = _cached_similarity_model.cache_info  # type: ignore[attr-defined]


def detect_memory_limit_bytes(
    cgroup_v2_path: Path = CGROUP_V2_MEMORY_MAX,
    cgroup_v1_path: Path = CGROUP_V1_MEMORY_LIMIT,
) -> int | None:
    """Read container memory limit from cgroup v2 (`memory.max`) or v1, or None if unlimited."""
    for candidate in (cgroup_v2_path, cgroup_v1_path):
        if candidate.is_file():
            try:
                raw = candidate.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if not raw or raw == "max":
                return None
            try:
                val = int(raw)
            except ValueError:
                continue
            # cgroup v1 reports ~2^63-1 when unlimited.
            if 0 < val < (1 << 50):
                return val
    return None


def _required_memory_for(
    sim_backend: str,
    provider: str,
    local_model: str | None,
) -> tuple[int, str]:
    """Return (required_bytes, reason) for the given similarity backend and ASR engine."""
    if provider == "parakeet":
        from parakeet_transcriber import parakeet_precision

        precision = parakeet_precision()
        required = (
            MIN_MEM_PARAKEET_FP32_WITH_SIM_BYTES
            if precision == "fp32"
            else MIN_MEM_PARAKEET_INT8_WITH_SIM_BYTES
        )
        evidence = (
            "P02 Docker evidence: Parakeet FP32 peak cgroup 3,171.4 MB with torch similarity; "
            "FP32 with ONNX similarity has not been measured and uses this conservative bound"
            if precision == "fp32"
            else "previous Docker evidence measured Parakeet INT8 near 1 GiB; "
            "the 85% margin sets the 1,280 MiB minimum"
        )
        return required, f"Parakeet {precision} + {sim_backend} ({evidence})"

    if sim_backend == "onnx-int8":
        if provider == "deepgram":
            return (
                MIN_MEM_DEEPGRAM_WITH_ONNX_INT8_BYTES,
                "ASR_PROVIDER=deepgram + OnnxSimilarityModel(onnx-int8) "
                "(measured peak ~225 MiB RSS with es_en vocab)",
            )
        if local_model == "tiny":
            return (
                MIN_MEM_WHISPER_TINY_WITH_ONNX_INT8_BYTES,
                "ASR_PROVIDER=faster-whisper (tiny) + OnnxSimilarityModel(onnx-int8) "
                "(measured peak ~435 MiB RSS with es_en vocab)",
            )
        if local_model == "base":
            return (
                MIN_MEM_WHISPER_BASE_WITH_ONNX_INT8_BYTES,
                "ASR_PROVIDER=faster-whisper (base) + OnnxSimilarityModel(onnx-int8) "
                "(measured peak ~545 MiB RSS)",
            )
        return (
            MIN_MEM_WHISPER_SMALL_WITH_ONNX_INT8_BYTES,
            "ASR_PROVIDER=faster-whisper (small) + OnnxSimilarityModel(onnx-int8) "
            "(measured peak ~980 MiB RSS)",
        )

    if sim_backend == "onnx-fp32":
        if provider == "deepgram":
            return (
                MIN_MEM_DEEPGRAM_WITH_ONNX_FP32_BYTES,
                "ASR_PROVIDER=deepgram + OnnxSimilarityModel(onnx-fp32) "
                "(measured peak ~485 MiB RSS with es_en vocab)",
            )
        if local_model == "small":
            return (
                MIN_MEM_WHISPER_SMALL_WITH_ONNX_FP32_BYTES,
                "ASR_PROVIDER=faster-whisper (small) + OnnxSimilarityModel(onnx-fp32) "
                "(measured peak ~1210 MiB RSS)",
            )
        return (
            MIN_MEM_WHISPER_TINY_BASE_WITH_ONNX_FP32_BYTES,
            f"ASR_PROVIDER=faster-whisper ({local_model}) + OnnxSimilarityModel(onnx-fp32) "
            "(measured peak ~720-820 MiB RSS)",
        )

    # Default: SIMILARITY_BACKEND=torch
    if provider == "deepgram":
        return (
            MIN_MEM_DEEPGRAM_WITH_SIM_BYTES,
            "ASR_PROVIDER=deepgram + SimilarityModel(torch) (measured peak ~1124 MiB RSS)",
        )
    if local_model == "small":
        return (
            MIN_MEM_WHISPER_SMALL_WITH_SIM_BYTES,
            "ASR_PROVIDER=faster-whisper (small) + SimilarityModel(torch) "
            "(measured peak ~1698 MiB RSS)",
        )
    return (
        MIN_MEM_WHISPER_TINY_BASE_WITH_SIM_BYTES,
        f"ASR_PROVIDER=faster-whisper ({local_model}) + SimilarityModel(torch) "
        "(measured peak ~1331 MiB RSS)",
    )


def check_memory_budget(limit_bytes: int | None = None) -> dict[str, Any]:
    """Compare container memory limit against measured RSS requirements per backend & engine."""
    detected = detect_memory_limit_bytes() if limit_bytes is None else limit_bytes
    provider = asr_provider()
    local_model = asr_local_model() if provider == "faster-whisper" else None
    fallback = asr_fallback_provider() if provider in {"faster-whisper", "parakeet"} else "none"
    parakeet_info = parakeet_runtime_status() if provider == "parakeet" else {}
    sim_backend = similarity_backend()
    enforce = asr_enforce_memory_budget()

    if provider == "deepgram":
        mode = "remote-deepgram"
    elif provider == "parakeet":
        mode = (
            "local-parakeet-with-local-fallback"
            if fallback == "faster-whisper"
            else "local-parakeet"
        )
    else:
        mode = "local-with-deepgram-fallback" if fallback == "deepgram" else "local-only"

    required, reason = _required_memory_for(sim_backend, provider, local_model)
    sufficient = detected is None or detected >= required
    det_mib = round(detected / (1024 * 1024), 2) if detected is not None else None
    req_mib = round(required / (1024 * 1024), 2)
    warning = (
        None
        if sufficient
        else (
            f"Insufficient container memory: detected cgroup limit {det_mib} MiB is below "
            f"the required {req_mib} MiB for {reason}."
        )
    )
    return {
        "asr_provider": provider,
        "asr_local_model": local_model,
        "asr_fallback_provider": fallback,
        "asr_mode": mode,
        "similarity_backend": sim_backend,
        "memory_enforce": enforce,
        "memory_limit_bytes": detected,
        "memory_limit_mib": det_mib,
        "required_memory_bytes": required,
        "required_memory_mib": req_mib,
        "memory_sufficient": sufficient,
        "warning": warning,
        "reason": reason,
        **parakeet_info,
    }


def enforce_memory_budget(limit_bytes: int | None = None) -> dict[str, Any]:
    """Warn on startup if container memory is below threshold; fail fast only if enforced."""
    status = check_memory_budget(limit_bytes)
    if not status["memory_sufficient"]:
        msg = str(status["warning"])
        if status["memory_enforce"]:
            raise RuntimeError(
                f"{msg} Failing fast because ASR_ENFORCE_MEMORY_BUDGET=true "
                "to prevent kernel OOM kill (exit 137)."
            )
        logger.warning(
            "%s Set ASR_ENFORCE_MEMORY_BUDGET=true to make this check fatal on startup.",
            msg,
        )
    return status


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

    started = perf_counter()
    path = Path(path)
    waveform = decode_audio(path)  # Bounds duration/decoded memory before ASR.
    provider = asr_provider()
    fallback = asr_fallback_provider() if provider in {"faster-whisper", "parakeet"} else "none"
    gate_cfg = quality_gate_config() if provider == "faster-whisper" else None
    parakeet_gate_cfg = parakeet_quality_gate_config() if provider == "parakeet" else None
    model = None
    sin_modelo: str | None = None
    if question is not None and question.strip():
        try:
            model = similarity_model()
        except RuntimeError as fallo:
            # **Que falte el modelo no puede tirar el analisis entero.**
            #
            # Esto no se capturaba, asi que la excepcion subia hasta RQ y el
            # trabajo moria completo: ni transcripcion, ni fragmento analizado,
            # ni nada en el expediente del docente. Se leia igual que si el
            # estudiante no hubiera hablado, que es el peor fallo posible aqui.
            #
            # Con el modelo caido no se puede medir la similitud, y entonces la
            # alerta de consulta a IA no se dispara: eso es la regla funcionando
            # —exige las dos condiciones—, no un fallo. Pero el habla si se
            # reporta por si sola desde el 19/10, y el docente tiene que recibir
            # su fragmento y su transcripcion igualmente.
            logger.warning("Similitud no disponible: %s", fallo)
            sin_modelo = str(fallo)
    detector = synthetic_model()

    asr_quality_status = "ok"
    asr_quality_reasons: list[str] = []
    asr_quality_details: dict[str, str] = {}
    skip_analysis = False

    if provider == "deepgram":
        asr = asr_model()
        transcript = str(asr.transcribe(path)["transcript"])
        asr_version_str = _asr_version(asr)
    elif provider == "parakeet":
        from parakeet_transcriber import ParakeetConfigurationError, ParakeetRuntimeError

        try:
            asr = asr_model()
            asr_res = asr.transcribe(path, waveform=waveform)
        except ParakeetConfigurationError:
            raise
        except ParakeetRuntimeError as exc:
            if fallback != "faster-whisper":
                raise
            primary_version = (
                f"parakeet-tdt-0.6b-v3-{parakeet_settings()[0]};"
                "runtime_initialization_or_inference_failed"
            )
            logger.exception(
                "Parakeet runtime failed; switching to configured local faster-whisper fallback"
            )
            clear_parakeet_model_cache()
            asr = _get_local_asr()
            asr_res = asr.transcribe(path)
            transcript = str(asr_res.get("transcript", ""))
            gate_passed, reason = evaluate_asr_quality(asr_res, gate_cfg)
            if not gate_passed and reason:
                asr_quality_status = "low_confidence"
                asr_quality_reasons.append(reason)
                logger.warning("ASR low confidence provider=faster-whisper reason=%s", reason)
            asr_version_str = (
                f"{_asr_version(asr)};fallback_from={primary_version};"
                f"reason=parakeet_runtime_error:{type(exc).__name__}"
            )
        else:
            transcript = str(asr_res.get("transcript", ""))
            asr_version_str = _asr_version(asr)
            asr_quality_reasons = evaluate_parakeet_quality(asr_res, parakeet_gate_cfg or {})
            if asr_quality_reasons:
                asr_quality_status = "low_confidence"
                logger.warning(
                    "ASR low confidence provider=parakeet reasons=%s calibration_precision=int8",
                    ",".join(asr_quality_reasons),
                )
            mean_log_prob = asr_res.get("mean_ys_log_prob")
            asr_quality_details = {
                "asr_quality_calibrated_on": "parakeet-int8",
                "asr_quality_words_per_second": f"{asr_res.get('words_per_second', 0.0):.6f}",
                "asr_quality_token_count": str(len(asr_res.get("tokens", []))),
                "asr_quality_timestamp_count": str(len(asr_res.get("timestamps", []))),
                "asr_quality_mean_ys_log_prob": (
                    f"{mean_log_prob:.6f}"
                    if isinstance(mean_log_prob, int | float)
                    else "unavailable"
                ),
            }
    else:
        asr = asr_model()
        primary_version = _asr_version(asr)
        try:
            asr_res = asr.transcribe(path)
            transcript = str(asr_res.get("transcript", ""))
        except (RuntimeError, ValueError, OSError) as exc:
            if fallback != "deepgram":
                raise
            logger.warning(
                "Local Faster-Whisper runtime failed (%s); triggering Deepgram fallback",
                type(exc).__name__,
            )
            elapsed = perf_counter() - started
            fb_timeout = compute_fallback_timeout(elapsed)
            if fb_timeout <= 0:
                raise RuntimeError(
                    "Local Faster-Whisper failed and Deepgram fallback budget is exhausted"
                ) from None
            fb_asr = _build_fallback_transcriber(timeout=fb_timeout)
            fb_res = fb_asr.transcribe(path)
            transcript = str(fb_res["transcript"])
            asr_version_str = (
                f"{_asr_version(fb_asr)};fallback_from={primary_version};"
                f"reason=runtime_error:{type(exc).__name__}"
            )
        else:
            asr_version_str = primary_version
            gate_passed, reason = evaluate_asr_quality(asr_res, gate_cfg)
            if not gate_passed and reason:
                asr_quality_status = "low_confidence"
                asr_quality_reasons.append(reason)
                logger.warning("ASR low confidence provider=faster-whisper reason=%s", reason)

    similarity = None
    versions: dict[str, str] = {"asr": asr_version_str, "sim": "not-applicable"}
    versions["asr_quality_status"] = asr_quality_status
    if asr_quality_reasons:
        versions["asr_quality_reasons"] = ",".join(asr_quality_reasons)
    versions.update(asr_quality_details)
    if sin_modelo is not None:
        versions["sim"] = "unavailable:model-not-loaded"
        versions["sim_error"] = sin_modelo[:200]
    if model is not None and not skip_analysis and transcript.strip():
        try:
            similarity = model.score(question, transcript)
            model_ver = getattr(model, "version", None)
            if isinstance(model_ver, str) and model_ver:
                versions["sim"] = model_ver
            else:
                sim_bg = similarity_backend()
                versions["sim"] = (
                    f"multilingual-MiniLM-L12-v2@{SIM_REVISION}"
                    if sim_bg == "torch"
                    else f"multilingual-MiniLM-L12-v2@{SIM_REVISION};backend={sim_bg}"
                )
        except ValueError:
            # Long texts must not be silently truncated to manufacture similarity.
            versions["sim"] = "unavailable:input-outside-model-context"
    score = detector.score(waveform) if (detector and not skip_analysis) else None
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
