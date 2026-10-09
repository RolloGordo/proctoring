"""Tareas que consume el worker de IA.

El audio y la verificación facial tienen implementación local.
El detector sintético es experimental y está desactivado por defecto hasta medir P2.

El reparto con la API es deliberado y conviene no romperlo:

| Quién | Qué hace |
|---|---|
| este worker | **mide**: transcribe, calcula similitud, puntúa la voz, compara caras |
| la API | **decide**: aplica los umbrales de la sesión y crea la alerta |

Por eso aquí no se escribe en la base ni se crean alertas. La regla que define el
proyecto —avisar **solo** si lo dicho se parece al enunciado **y** hay una segunda
voz sintética— vive en la API, con sus pruebas, y se puede calibrar sin tocar esto.
Si la implementas aquí, acabará habiendo dos reglas que se contradicen.

## Cómo funciona

1. La API encola el trabajo con el `event_id` (o el `participant_id`).
2. El worker pide a la API **qué** analizar: `GET /internal/audio-jobs/{event_id}`
   devuelve la ruta del audio en Storage y el **enunciado** con el que comparar.
3. El worker descarga el audio de Storage, mide, y manda los números a
   `POST /internal/audio-jobs/{event_id}/result`.
4. La respuesta trae `alerted`: qué decidió la API.

## Lo que hace falta configurar

| Variable | Para qué |
|---|---|
| `PROCTORING_API_URL` | Base de la API, por ejemplo `http://api:8000` |
| `INTERNAL_API_TOKEN` | El mismo secreto que tiene la API (`X-Internal-Token`) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Para descargar de Storage |

## Presupuesto de tiempo

La alerta de IA por voz tiene que llegar en **menos de 10 s**. Con `small`, la
transcripción de un fragmento de 10 s cuesta ~2,3 s, así que quedan ~7,7 s para la
similitud y la voz sintética. Mide de punta a punta (`processing_ms`), no por
partes: es el número que dice si la meta se cumple.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID

import httpx

from audio_runtime import download_audio, measure_audio

logger = logging.getLogger(__name__)

API_URL = os.environ.get("PROCTORING_API_URL", "http://localhost:8000").rstrip("/")
INTERNAL_TOKEN = os.environ.get("INTERNAL_API_TOKEN", "")
#: Lo que se espera de la API. Mas tiempo que esto es que algo esta mal.
HTTP_TIMEOUT_SECONDS = 15


def _headers() -> dict[str, str]:
    return {"X-Internal-Token": INTERNAL_TOKEN, "Content-Type": "application/json"}


def _get(path: str, **params: Any) -> dict[str, Any]:
    response = httpx.get(
        f"{API_URL}{path}", headers=_headers(), params=params, timeout=HTTP_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    return dict(response.json())


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(
        f"{API_URL}{path}", headers=_headers(), json=payload, timeout=HTTP_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    return dict(response.json())


def analyze_audio(event_id: str) -> dict[str, Any]:
    """Analiza el audio de un evento `speech_detected`.

    Args:
        event_id: identificador del evento. Es lo unico que viaja por la cola.

    Returns:
        Lo que respondio la API, incluido `alerted`: si decidio avisar al docente.
    """
    started = time.monotonic()
    event_id = str(UUID(event_id))
    if not INTERNAL_TOKEN:
        raise ValueError("INTERNAL_API_TOKEN is required")
    job = _get(f"/api/v1/internal/audio-jobs/{event_id}")

    with TemporaryDirectory(prefix="proctoring-audio-") as temporary:
        audio = Path(temporary) / "segment.audio"
        download_audio(job, audio)
        measurement = measure_audio(audio, job["question_statement"])
    # Includes job fetch, download, cold model setup, inference and cleanup.
    # The POST duration cannot be placed in its own body; log it separately.
    measurement["processing_ms"] = int((time.monotonic() - started) * 1000)
    measurement["model_versions"]["session_similarity_threshold"] = str(job["similarity_threshold"])
    measurement["model_versions"]["session_synthetic_threshold"] = str(job["synthetic_threshold"])
    result = _post(f"/api/v1/internal/audio-jobs/{event_id}/result", measurement)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "Audio job %s worker_total_ms=%s budget_met=%s", event_id, elapsed_ms, elapsed_ms < 10000
    )
    return result


def verify_face(participant_id: str, capture_path: str) -> dict[str, Any]:
    """Compara la captura del estudiante con su rostro de referencia.

    Hay alguien esperando en la sala de espera: el presupuesto es **P90 < 500 ms**,
    y por eso esta tarea va en la cola de prioridad alta.

    Args:
        participant_id: la matricula del estudiante en esa sesion.
        capture_path: ruta de la captura recien tomada, ya en Storage.

    Returns:
        Lo que respondio la API: que concluyo y como quedo el participante.
    """
    comenzado = time.monotonic()
    job = _get(f"/api/v1/internal/face-jobs/{participant_id}", capture_path=capture_path)

    from face_pipeline import FaceInconclusive, compare_job

    similarity: float | None = None
    inconclusive = False
    model_version = f"insightface/{os.getenv('FACE_MODEL_NAME', 'buffalo_sc')}-cpu"
    reference_embedding: list[float] | None = None
    try:
        similarity, reference_embedding = compare_job(job)
    except FaceInconclusive as exc:
        inconclusive = True
        logger.info("Verificación facial inconclusa: %s", exc)
    # Fallos de infraestructura (Storage, modelos no instalados) deben hacer
    # fallar el job para reintento; no se deben camuflar como falta de coincidencia.

    return _post(
        f"/api/v1/internal/sessions/{job['session_id']}"
        f"/students/{job['student_id']}/identity-result",
        {
            "similarity": similarity,
            "inconclusive": inconclusive,
            "latency_ms": int((time.monotonic() - comenzado) * 1000),
            "model_version": model_version,
            "reference_embedding": reference_embedding,
        },
    )
