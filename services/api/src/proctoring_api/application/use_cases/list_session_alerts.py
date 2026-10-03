"""Caso de uso: listar las alertas de una sesion."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from proctoring_api.application.ports.alert_repository import AlertRepository
from proctoring_api.application.ports.session_repository import SessionRepository
from proctoring_api.application.session_access import ensure_teacher_owns_session
from proctoring_api.domain.alert import Alert
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.user import AuthenticatedUser


class ListSessionAlerts:
    """Alertas de una sesion para la pantalla en vivo del docente.

    Realtime solo trae lo que ocurre a partir de que el docente se suscribe. Este
    caso de uso es el que llena la pantalla con lo que ya habia pasado cuando la
    abrio.
    """

    def __init__(self, alerts: AlertRepository, sessions: SessionRepository | None = None) -> None:
        self._alerts = alerts
        self._sessions = sessions

    def execute(
        self,
        session_id: UUID,
        *,
        actor: AuthenticatedUser | None = None,
        student_id: UUID | None = None,
    ) -> Sequence[Alert]:
        """Alertas de la sesion, de la mas reciente a la mas antigua.

        Solo para docentes. Un estudiante no ve las alertas que se generan sobre
        el: el sistema es un auditor y quien interpreta las senales es el docente.
        Mostrarselas en vivo ademas le ensenaria que detecciones esquivar.

        `actor` es `None` solo con la autenticacion desactivada en local.
        """
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo el docente puede ver las alertas de una sesion")

        ensure_teacher_owns_session(self._sessions, session_id, actor)

        return self._alerts.list_by_session(session_id, student_id)
