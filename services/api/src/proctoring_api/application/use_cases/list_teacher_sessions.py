"""Casos de uso de lectura de sesiones de examen."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.session_access import ensure_teacher_owns_session
from proctoring_api.application.use_cases.create_exam_session import DEFAULT_DEV_TEACHER_ID
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.user import AuthenticatedUser


class ListTeacherSessions:
    """Sesiones del docente que pregunta. Nunca las de otro."""

    def __init__(
        self,
        sessions: ExamSessionRepository,
        dev_teacher_id: UUID = DEFAULT_DEV_TEACHER_ID,
    ) -> None:
        self._sessions = sessions
        self._dev_teacher_id = dev_teacher_id

    def execute(self, *, actor: AuthenticatedUser | None = None) -> Sequence[ExamSession]:
        if actor is None:
            return self._sessions.list_by_teacher(self._dev_teacher_id)

        if not actor.is_teacher:
            raise AuthorizationError("Solo un docente tiene sesiones de examen propias")

        # El id sale del token, no de un parametro: asi no hay forma de pedir las
        # de otro.
        return self._sessions.list_by_teacher(actor.id)


class GetExamSession:
    """Detalle de una sesion, con sus modulos."""

    def __init__(self, sessions: ExamSessionRepository) -> None:
        self._sessions = sessions

    def execute(self, session_id: UUID, *, actor: AuthenticatedUser | None = None) -> ExamSession:
        """Devuelve la sesion si el actor puede verla.

        Raises:
            AuthorizationError: si no es suya, o si no existe. Se responde lo
                mismo en ambos casos para no revelar que sesiones existen.
        """
        ensure_teacher_owns_session(self._sessions, session_id, actor)

        session = self._sessions.find_by_id(session_id)
        if session is None:
            raise AuthorizationError("No tienes acceso a esta sesion de examen")

        return session
