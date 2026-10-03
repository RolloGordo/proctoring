"""Repositorio de sesiones en memoria, para pruebas.

En modo memoria la composicion de `main.py` no cablea ninguno: no hay sesiones
creadas porque no existe todavia el endpoint que las crea (SPEC-002).
"""

from __future__ import annotations

import threading
from uuid import UUID


class InMemorySessionRepository:
    """Implementacion de `SessionRepository` sobre un diccionario."""

    def __init__(self, sessions: dict[UUID, UUID] | None = None) -> None:
        #: session_id -> teacher_id
        self._sessions: dict[UUID, UUID] = dict(sessions or {})
        self._lock = threading.Lock()

    def find_teacher_id(self, session_id: UUID) -> UUID | None:
        with self._lock:
            return self._sessions.get(session_id)

    def add(self, session_id: UUID, teacher_id: UUID) -> None:
        with self._lock:
            self._sessions[session_id] = teacher_id
