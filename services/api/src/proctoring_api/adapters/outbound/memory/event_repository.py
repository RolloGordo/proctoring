"""Repositorio de eventos en memoria.

Es el adaptador por defecto (`EVENT_REPOSITORY=memory`). Sirve para dos cosas:
levantar la API sin Supabase ni credenciales, y correr las pruebas en
milisegundos. Los datos se pierden al reiniciar: no usar en produccion.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from uuid import UUID

from proctoring_api.domain.event import ProctoringEvent


class InMemoryEventRepository:
    """Implementacion de `EventRepository` sobre una lista, protegida con lock.

    El lock hace falta porque uvicorn atiende varias peticiones a la vez y
    `list.append` mas la lectura no son atomicos entre si.
    """

    def __init__(self) -> None:
        self._events: list[ProctoringEvent] = []
        self._lock = threading.Lock()

    def save(self, event: ProctoringEvent) -> None:
        with self._lock:
            self._events.append(event)

    def list_by_session(
        self, session_id: UUID, student_id: UUID | None = None
    ) -> Sequence[ProctoringEvent]:
        with self._lock:
            # Se copia dentro del lock para no iterar una lista que otro hilo muta.
            snapshot = list(self._events)

        matches = [
            event
            for event in snapshot
            if event.session_id == session_id
            and (student_id is None or event.student_id == student_id)
        ]
        return sorted(matches, key=lambda event: event.started_at)

    def clear(self) -> None:
        """Vacia el repositorio. Solo para pruebas."""
        with self._lock:
            self._events.clear()
