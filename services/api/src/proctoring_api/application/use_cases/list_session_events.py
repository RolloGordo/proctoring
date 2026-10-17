"""Caso de uso: listar los eventos de una sesion."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from proctoring_api.application.ports.event_repository import EventRepository
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.session_access import ensure_teacher_owns_session
from proctoring_api.domain.event import ProctoringEvent
from proctoring_api.domain.user import AuthenticatedUser


class ListSessionEvents:
    """Devuelve los eventos de una sesion, opcionalmente de un solo estudiante.

    Es lo que alimenta la pantalla de revision del docente: la linea de tiempo de
    senales con su evidencia. Por eso el orden cronologico importa y lo garantiza
    el repositorio.
    """

    def __init__(
        self, events: EventRepository, sessions: ExamSessionRepository | None = None
    ) -> None:
        self._events = events
        self._sessions = sessions

    def execute(
        self,
        session_id: UUID,
        *,
        actor: AuthenticatedUser | None = None,
        student_id: UUID | None = None,
    ) -> Sequence[ProctoringEvent]:
        """Eventos de la sesion que el actor tiene derecho a ver.

        Un **estudiante** solo ve los suyos: se ignora el filtro que pida y se
        fuerza a su propio id. Que la API escriba con service role y omita RLS
        significa que este filtro es lo unico que impide que un estudiante lea la
        evidencia de sus companeros.

        Un **docente** ve toda la sesion, pero solo si es suya.

        `actor` es `None` solo con la autenticacion desactivada en desarrollo
        local (ver `Settings.auth_enabled`).
        """
        ensure_teacher_owns_session(self._sessions, session_id, actor)

        if actor is not None and actor.is_student:
            student_id = actor.id

        return self._events.list_by_session(session_id, student_id)
