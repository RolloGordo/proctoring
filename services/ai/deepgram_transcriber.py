"""SPEC-008: Spanish transcription through Deepgram Nova-3 (pre-recorded REST API).

Default provider of the audio worker since TA-070 (``ASR_PROVIDER`` unset). It keeps the
interface of the local ``spikes.transcribe.Transcriber`` (now an optional extra used only
for experiments): ``.transcribe(audio, reference=None)`` and a compatible result dictionary,
so the worker and the evaluation scripts can swap providers without changes. Like the local
provider it only **measures**: it never decides alerts and never writes to the database.

Security notes:
- The key is read only from ``DEEPGRAM_API_KEY`` and sent only in the ``Authorization``
  header. It is never part of the URL, a log line, an exception message, a result or a repr.
- Error messages are built from fixed texts plus the HTTP status and a sanitized
  ``request_id``. Response bodies and ``str(httpx_exception)`` are never copied.
- Redirects are not followed, so the key cannot be forwarded to another origin.

No automatic retries here: 429 and 5xx are flagged ``transient`` so the caller (the RQ job)
can decide, keeping the worker inside its time budget.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from spikes.metrics import word_errors

logger = logging.getLogger(__name__)

API_KEY_ENV = "DEEPGRAM_API_KEY"
TIMEOUT_ENV = "DEEPGRAM_TIMEOUT_SECONDS"
DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"
MODEL = "nova-3"
LANGUAGE = "es"
#: Same limit as ``audio_runtime.MAX_AUDIO_BYTES``; to be centralized during integration.
MAX_AUDIO_BYTES = 8_000_000
#: The whole alert must arrive in < 10 s, so a hung request cannot wait longer than this.
DEFAULT_TIMEOUT_SECONDS = 8.0

_REQUEST_ID = re.compile(r"[0-9A-Za-z-]{1,64}")


class DeepgramError(RuntimeError):
    """Any failure talking to Deepgram. The message is safe to log."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        request_id: str | None = None,
        transient: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id
        #: True for 429/5xx/timeouts/network: worth retrying later, not now.
        self.transient = transient


def _error(
    reason: str,
    *,
    status_code: int | None = None,
    request_id: str | None = None,
    transient: bool = False,
) -> DeepgramError:
    details = []
    if status_code is not None:
        details.append(f"HTTP {status_code}")
    if request_id:
        details.append(f"request_id={request_id}")
    suffix = f" ({', '.join(details)})" if details else ""
    return DeepgramError(
        f"Deepgram: {reason}{suffix}",
        status_code=status_code,
        request_id=request_id,
        transient=transient,
    )


def _clean_request_id(value: Any) -> str | None:
    """Keep only short identifier-like values so nothing else leaks into messages."""
    if isinstance(value, str) and _REQUEST_ID.fullmatch(value):
        return value
    return None


def _request_id(response: httpx.Response) -> str | None:
    header = _clean_request_id(response.headers.get("dg-request-id"))
    if header:
        return header
    try:
        body = response.json()
    except ValueError:
        return None
    if isinstance(body, dict):
        return _clean_request_id(body.get("request_id"))
    return None


def _timeout_from(value: float | None) -> float:
    if value is None:
        raw = os.environ.get(TIMEOUT_ENV)
        if raw is None or not raw.strip():
            return DEFAULT_TIMEOUT_SECONDS
        try:
            value = float(raw)
        except ValueError:
            raise ValueError(f"{TIMEOUT_ENV} must be a positive number") from None
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError("Deepgram timeout must be a positive, finite number of seconds")
    return float(value)


def _read_key() -> str:
    key = os.environ.get(API_KEY_ENV, "").strip()
    if not key:
        raise _error(f"{API_KEY_ENV} is required")
    # A malformed value must be rejected here: the HTTP library would otherwise
    # reject it later with a message that could echo the secret.
    if not key.isascii() or not key.isprintable() or any(c.isspace() for c in key):
        raise _error(f"{API_KEY_ENV} has an invalid format")
    return key


def _extract(payload: Any, request_id: str | None) -> tuple[str, float | None, str | None]:
    """Return ``(transcript, audio_seconds, request_id)`` or raise on a malformed body.

    An empty transcript is a valid answer (silence); a missing field is not.
    """
    try:
        text = payload["results"]["channels"][0]["alternatives"][0]["transcript"]
    except (KeyError, IndexError, TypeError):
        raise _error("response has an unexpected structure", request_id=request_id) from None
    if not isinstance(text, str):
        raise _error("response transcript is not text", request_id=request_id)
    metadata = payload.get("metadata")
    duration: float | None = None
    if isinstance(metadata, dict):
        raw = metadata.get("duration")
        if isinstance(raw, int | float) and not isinstance(raw, bool) and math.isfinite(raw):
            duration = float(raw) if raw >= 0 else None
        request_id = _clean_request_id(metadata.get("request_id")) or request_id
    return text.strip(), duration, request_id


class DeepgramTranscriber:
    """Deepgram Nova-3 provider with the interface of ``spikes.transcribe.Transcriber``."""

    def __init__(self, client: httpx.Client | None = None, timeout: float | None = None) -> None:
        self._api_key = _read_key()
        self._client = client  # An injected client belongs to the caller; never closed here.
        self.timeout = _timeout_from(timeout)
        self.model = MODEL
        self.language = LANGUAGE

    def __repr__(self) -> str:
        return f"DeepgramTranscriber(model={self.model!r}, language={self.language!r})"

    @property
    def version(self) -> str:
        """Value for ``model_versions['asr']``."""
        return f"deepgram-{self.model}-{self.language}"

    def _read_audio(self, audio: Path) -> bytes:
        if not audio.is_file():
            raise ValueError(f"No existe el audio: {audio}")
        if audio.stat().st_size == 0:
            raise ValueError("Audio vacío")
        if audio.stat().st_size > MAX_AUDIO_BYTES:
            raise ValueError("Audio exceeds size limit")
        data = audio.read_bytes()
        if not data or len(data) > MAX_AUDIO_BYTES:
            raise ValueError("Audio vacío o fuera del límite de tamaño")
        return data

    def _send(self, data: bytes) -> httpx.Response:
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "application/octet-stream",
        }
        params = {
            "model": self.model,
            "language": self.language,
            "smart_format": "false",
            "punctuate": "false",
        }
        # Clients created here are always closed; injected ones are left to their owner.
        client = self._client or httpx.Client(timeout=self.timeout, follow_redirects=False)
        try:
            return client.post(
                DEEPGRAM_URL,
                params=params,
                headers=headers,
                content=data,
                timeout=self.timeout,
            )
        except httpx.TimeoutException:
            raise _error("request timed out", transient=True) from None
        except httpx.TransportError:
            raise _error("network error", transient=True) from None
        except httpx.HTTPError:
            raise _error("request could not be sent") from None
        finally:
            if self._client is None:
                client.close()

    @staticmethod
    def _check_status(response: httpx.Response) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        rid = _request_id(response)
        if status in (401, 403):
            reason, transient = "credentials or permissions rejected", False
        elif status == 402:
            reason, transient = "insufficient credits", False
        elif status in (400, 422):
            reason, transient = "audio or request rejected", False
        elif status == 429:
            reason, transient = "rate limit exceeded", True
        elif status >= 500:
            reason, transient = "service error", True
        else:
            reason, transient = "unexpected response status", False
        raise _error(reason, status_code=status, request_id=rid, transient=transient)

    def transcribe(self, audio: Path, reference: str | None = None) -> dict[str, Any]:
        data = self._read_audio(audio)
        started = perf_counter()
        try:
            response = self._send(data)
            self._check_status(response)
            header_rid = _request_id(response)
            try:
                payload = response.json()
            except ValueError:
                raise _error("response is not valid JSON", request_id=header_rid) from None
            transcript, duration, request_id = _extract(payload, header_rid)
        except DeepgramError as exc:
            logger.warning(
                "Deepgram transcription failed status=%s request_id=%s transient=%s",
                exc.status_code,
                exc.request_id,
                exc.transient,
            )
            raise
        # Includes network latency, unlike the local provider (no model load either).
        elapsed = perf_counter() - started
        logger.info("Deepgram transcription ok request_id=%s ms=%d", request_id, elapsed * 1000)
        result: dict[str, Any] = {
            "schema_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "audio_file": audio.name,
            "audio_sha256": hashlib.sha256(data).hexdigest(),
            "provider": "deepgram",
            "model": self.model,
            "version": self.version,
            "language": self.language,
            "smart_format": False,
            "punctuate": False,
            "inference_seconds": elapsed,
            "audio_seconds": duration,
            "real_time_factor": elapsed / duration if duration else None,
            "transcript": transcript,
            "segments": [],
            "request_id": request_id,
            "environment": {"httpx": httpx.__version__},
            "scope": "transcription_only_no_fraud_detection",
        }
        if reference is not None:
            result["reference"] = reference
            result["metrics"] = word_errors(reference, transcript)
        return result
