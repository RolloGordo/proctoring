"""Caso de uso: entrar a un examen con el código de acceso."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.use_cases.manage_enrollment import ExamCancelledError
from proctoring_api.domain.errors import AuthorizationError, DomainError
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.user import AuthenticatedUser


#: Normalización del código: el estudiante lo teclea leyéndolo de una pizarra o
#: de un chat, así que llega con espacios y en cualquier caja.
def normalise_access_code(code: str) -> str:
    return code.strip().upper().replace(" ", "").replace("-", "")


class ExamSessionNotFoundError(DomainError):
    """No hay ninguna sesión con ese código de acceso."""


class ExamNotOpenError(DomainError):
    """La sesión existe pero no admite ingresos en este momento."""


@dataclass(frozen=True, slots=True)
class JoinExamSessionOutput:
    """Lo que el estudiante necesita para prepararse."""

    session: ExamSession
    #: Si puede entrar ahora mismo, o solo está mirando la sala de espera.
    can_enter_now: bool
    opens_at: datetime
    closes_at: datetime


class JoinExamSession:
    """Resuelve un código de acceso a la sesión que le corresponde.

    **Todavía no matricula al estudiante**: crear la fila en
    `session_participants`, el consentimiento y la verificación de identidad son
    SPEC-004. Esto resuelve el código y dice si la ventana de ingreso está
    abierta, que es lo que la sala de espera necesita mostrar.
    """

    def __init__(self, sessions: ExamSessionRepository, clock: Clock) -> None:
        self._sessions = sessions
        self._clock = clock

    def execute(
        self, access_code: str, *, actor: AuthenticatedUser | None = None
    ) -> JoinExamSessionOutput:
        """Busca la sesión por su código.

        Raises:
            AuthorizationError: si quien pide es un docente. Un docente entra a
                sus exámenes por su panel, no por el código de estudiante.
            ExamSessionNotFoundError: si el código no corresponde a ninguna
                sesión. Se responde lo mismo para un código mal escrito que para
                uno de otro docente: un mensaje distinto permitiría tantear
                códigos hasta dar con uno válido.
        """
        if actor is not None and actor.is_teacher:
            raise AuthorizationError(
                "Un docente entra a sus exámenes desde su panel, no con un código de acceso"
            )

        session = self._sessions.find_by_access_code(normalise_access_code(access_code))
        if session is None:
            raise ExamSessionNotFoundError(
                "No hay ningún examen con ese código. Revísalo con tu docente."
            )

        # Un examen cancelado **sí** existió, así que decir "no hay ningún examen
        # con ese código" mandaría al estudiante a revisar un código que está
        # bien. Esto no filtra nada: ya tenía el código.
        if session.is_cancelled:
            raise ExamCancelledError(
                "Tu docente canceló este examen. No tienes que hacer nada; "
                "si no sabías nada, habla con él."
            )

        now = self._clock.now()
        return JoinExamSessionOutput(
            session=session,
            can_enter_now=session.accepts_entry_at(now),
            opens_at=session.starts_at,
            closes_at=session.ends_at,
        )
