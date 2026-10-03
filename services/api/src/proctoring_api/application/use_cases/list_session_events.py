"""Caso de uso: listar los eventos de una sesion."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from proctoring_api.application.ports.event_repository import EventRepository
from proctoring_api.domain.event import ProctoringEvent


class ListSessionEvents:
    """Devuelve los eventos de una sesion, opcionalmente de un solo estudiante.

    Es lo que alimenta la pantalla de revision del docente: la linea de tiempo de
    senales con su evidencia. Por eso el orden cronologico importa y lo garantiza
    el repositorio.
    """

    def __init__(self, events: EventRepository) -> None:
        self._events = events

    def execute(
        self, session_id: UUID, student_id: UUID | None = None
    ) -> Sequence[ProctoringEvent]:
        return self._events.list_by_session(session_id, student_id)
