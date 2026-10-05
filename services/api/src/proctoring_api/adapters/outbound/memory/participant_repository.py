"""Repositorio de matrículas en memoria."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from uuid import UUID

from proctoring_api.domain.participant import SessionParticipant


class InMemoryParticipantRepository:
    """Implementacion de `ParticipantRepository` sobre un diccionario."""

    def __init__(self, participants: Sequence[SessionParticipant] = ()) -> None:
        #: (session_id, student_id) -> matricula. Un estudiante tiene una sola
        #: matricula activa por sesion; los reintentos se modelan con `attempt`.
        self._participants: dict[tuple[UUID, UUID], SessionParticipant] = {
            (p.session_id, p.student_id): p for p in participants
        }
        self._lock = threading.Lock()

    def save(self, participant: SessionParticipant) -> None:
        with self._lock:
            self._participants[(participant.session_id, participant.student_id)] = participant

    def find(self, session_id: UUID, student_id: UUID) -> SessionParticipant | None:
        with self._lock:
            return self._participants.get((session_id, student_id))

    def list_by_student(self, student_id: UUID) -> Sequence[SessionParticipant]:
        with self._lock:
            snapshot = list(self._participants.values())

        return [p for p in snapshot if p.student_id == student_id]

    def list_by_session(self, session_id: UUID) -> Sequence[SessionParticipant]:
        with self._lock:
            snapshot = list(self._participants.values())

        de_la_sesion = [p for p in snapshot if p.session_id == session_id]
        # Por hora de consentimiento: el docente ve llegar a la gente en orden.
        return sorted(de_la_sesion, key=lambda p: (p.consent_at is None, p.consent_at))

    def clear(self) -> None:
        """Vacia el repositorio. Solo para pruebas."""
        with self._lock:
            self._participants.clear()
