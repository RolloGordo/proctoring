"""Cola de trabajos en memoria.

Adaptador por defecto (`JOB_QUEUE=memory`). No ejecuta nada: solo anota que el
trabajo se pidio. Permite levantar la API sin Redis y, en las pruebas, comprobar
que `speech_detected` encola y que los demas eventos no.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from uuid import UUID


class InMemoryJobQueue:
    """Implementacion de `JobQueue` que solo registra lo encolado."""

    def __init__(self) -> None:
        self._audio_analysis_jobs: list[UUID] = []
        self._face_verification_jobs: list[tuple[UUID, str]] = []
        self._lock = threading.Lock()

    def enqueue_audio_analysis(self, event_id: UUID) -> None:
        with self._lock:
            self._audio_analysis_jobs.append(event_id)

    def enqueue_face_verification(self, participant_id: UUID, capture_path: str) -> None:
        with self._lock:
            self._face_verification_jobs.append((participant_id, capture_path))

    @property
    def face_verification_jobs(self) -> Sequence[tuple[UUID, str]]:
        """Verificaciones pedidas, en orden."""
        with self._lock:
            return tuple(self._face_verification_jobs)

    @property
    def audio_analysis_jobs(self) -> Sequence[UUID]:
        """Eventos para los que se pidio analisis de audio, en orden."""
        with self._lock:
            return tuple(self._audio_analysis_jobs)

    def clear(self) -> None:
        """Vacia la cola. Solo para pruebas."""
        with self._lock:
            self._audio_analysis_jobs.clear()
            self._face_verification_jobs.clear()
