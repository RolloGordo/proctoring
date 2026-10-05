"""Repositorio de sesiones de examen en memoria."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from uuid import UUID

from proctoring_api.domain.exam_session import ExamSession


class InMemoryExamSessionRepository:
    """Implementacion de `ExamSessionRepository` sobre un diccionario."""

    def __init__(self, sessions: dict[UUID, ExamSession] | None = None) -> None:
        self._sessions: dict[UUID, ExamSession] = dict(sessions or {})
        self._lock = threading.Lock()

    def save(self, session: ExamSession) -> None:
        with self._lock:
            self._sessions[session.id] = session

    def find_by_id(self, session_id: UUID) -> ExamSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def find_teacher_id(self, session_id: UUID) -> UUID | None:
        with self._lock:
            session = self._sessions.get(session_id)
        return session.teacher_id if session else None

    def list_by_teacher(self, teacher_id: UUID) -> Sequence[ExamSession]:
        with self._lock:
            snapshot = list(self._sessions.values())

        mine = [session for session in snapshot if session.teacher_id == teacher_id]
        # De la mas proxima a la mas antigua: lo que el docente necesita primero
        # es el examen que viene.
        return sorted(mine, key=lambda session: session.starts_at, reverse=True)

    def list_by_courses(self, course_ids: Sequence[UUID]) -> Sequence[ExamSession]:
        wanted = set(course_ids)
        with self._lock:
            found = [s for s in self._sessions.values() if s.course_id in wanted]
        return sorted(found, key=lambda s: s.starts_at)

    def find_many(self, session_ids: Sequence[UUID]) -> Sequence[ExamSession]:
        with self._lock:
            return [self._sessions[i] for i in session_ids if i in self._sessions]

    def find_by_access_code(self, access_code: str) -> ExamSession | None:
        with self._lock:
            for sesion in self._sessions.values():
                if sesion.access_code == access_code:
                    return sesion
        return None

    def access_code_exists(self, access_code: str) -> bool:
        with self._lock:
            return any(session.access_code == access_code for session in self._sessions.values())

    def clear(self) -> None:
        """Vacia el repositorio. Solo para pruebas."""
        with self._lock:
            self._sessions.clear()
