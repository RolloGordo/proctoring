"""Tareas que consume el worker de IA.

**Esto es el esqueleto. Las partes marcadas con `TODO` son el trabajo real.**

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
from typing import Any

import httpx

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
    comenzado = time.monotonic()
    job = _get(f"/api/v1/internal/audio-jobs/{event_id}")

    # TODO(SP-007, Pierreluiggi): descargar `job["audio_path"]` del bucket
    #   `job["audio_bucket"]` en Supabase Storage.
    # TODO(SP-007): transcribir en espanol con faster-whisper (`small`: 16,0 % WER
    #   en MediaSpeech, 7,6 % en los audios propios; ver docs/SP-007-own-results.md).
    # TODO(SP-008): similitud entre la transcripcion y `job["question_statement"]`
    #   con sentence-transformers multilingue. Si el enunciado es `None` (la
    #   pregunta ya no existe) no hay con que comparar: deja `similarity` en None.
    # TODO(SP-008): puntuar si hay una segunda voz **sintetica**. Evaluar con un
    #   motor TTS que no se haya usado para entrenar: es lo que dice si generaliza.
    transcript: str | None = None
    similarity: float | None = None
    synthetic_voice_score: float | None = None
    model_versions: dict[str, str] = {}

    logger.info(
        "Analisis pendiente de implementar para el evento %s (umbral similitud %.2f, "
        "umbral voz sintetica %.2f)",
        event_id,
        job["similarity_threshold"],
        job["synthetic_threshold"],
    )

    # La API decide si esto es una consulta a una IA. El worker solo manda numeros.
    return _post(
        f"/api/v1/internal/audio-jobs/{event_id}/result",
        {
            "transcript": transcript,
            "similarity": similarity,
            "synthetic_voice_score": synthetic_voice_score,
            "processing_ms": int((time.monotonic() - comenzado) * 1000),
            "model_versions": model_versions,
        },
    )


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
