"""El panel del estudiante: a que examenes entro y en que estado esta cada uno."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.ports.participant_repository import ParticipantRepository
from proctoring_api.application.ports.question_repository import QuestionRepository
from proctoring_api.application.use_cases.manage_enrollment import DEFAULT_DEV_STUDENT_ID
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.participant import SessionParticipant
from proctoring_api.domain.user import AuthenticatedUser


@dataclass(frozen=True, slots=True)
class MyExam:
    """Un examen al que el estudiante entro, con su estado."""

    session: ExamSession
    participant: SessionParticipant
    #: Si hoy puede entrar o seguir dentro. Se calcula aqui, con el reloj del
    #: servidor, y no en el cliente: la hora de un equipo de estudiante no es
    #: fiable.
    can_enter_now: bool
    #: Sobre cuanto se califica el examen, para mostrar "13.5 de 20". Es la
    #: escala que fijo el docente (20 en Peru), no la suma de los puntos de las
    #: preguntas: el estudiante lee su nota, no el reparto interno.
    max_score: float | None = None
    #: Si hay desarrollos que el docente aun no califica: la nota es parcial.
    pending_manual_review: bool = False
    #: Si el docente lo retiro. Sin esto el panel diria "empieza en 3 horas" de
    #: un examen que no va a ocurrir.
    cancelled: bool = False


class ListMyExams:
    """Los examenes del estudiante que pregunta. Nunca los de otro.

    El id sale del token, no de un parametro: no hay forma de pedir los de otro.
    """

    def __init__(
        self,
        participants: ParticipantRepository,
        sessions: ExamSessionRepository,
        clock: Clock,
        dev_student_id: UUID = DEFAULT_DEV_STUDENT_ID,
        questions: QuestionRepository | None = None,
    ) -> None:
        self._participants = participants
        self._sessions = sessions
        self._clock = clock
        self._dev_student_id = dev_student_id
        self._questions = questions

    def execute(self, *, actor: AuthenticatedUser | None = None) -> Sequence[MyExam]:
        """Devuelve los examenes del estudiante, del mas reciente al mas antiguo.

        Raises:
            AuthorizationError: si lo pide un docente. Su panel es otro.
        """
        if actor is not None and actor.is_teacher:
            raise AuthorizationError("Un docente ve sus examenes desde su propio panel")

        quien = actor.id if actor is not None else self._dev_student_id
        participaciones = self._participants.list_by_student(quien)
        if not participaciones:
            return []

        # Una consulta para todas las sesiones, no una por fila.
        sesiones = {
            sesion.id: sesion
            for sesion in self._sessions.find_many([p.session_id for p in participaciones])
        }
        ahora = self._clock.now()

        # El maximo solo hace falta para lo ya entregado, y se pide de una vez
        # para todos: una consulta, no una por fila.
        resumen = (
            self._questions.summarize_sessions(
                [p.session_id for p in participaciones if p.submitted_at is not None]
            )
            if self._questions is not None
            else {}
        )

        resultado = [
            MyExam(
                session=sesiones[p.session_id],
                participant=p,
                can_enter_now=_can_continue(sesiones[p.session_id], p, ahora),
                max_score=float(sesiones[p.session_id].max_score),
                pending_manual_review=(
                    resumen[p.session_id].has_manual_questions if p.session_id in resumen else False
                ),
                cancelled=sesiones[p.session_id].is_cancelled,
            )
            # Una matricula cuya sesion ya no existe se omite en vez de romper el panel.
            for p in participaciones
            if p.session_id in sesiones
        ]
        return sorted(resultado, key=lambda e: e.session.starts_at, reverse=True)


def _can_continue(session: ExamSession, participant: SessionParticipant, now: datetime) -> bool:
    """Si el estudiante puede abrir el examen ahora.

    La tolerancia de ingreso es para **entrar por primera vez**. Quien ya esta
    matriculado puede seguir mientras dure el examen: si se le reinicia el equipo
    a los quince minutos, no puede quedarse fuera por haber pasado la tolerancia.
    Es la misma regla que aplica la API al pedir las preguntas.
    """
    if participant.submitted_at is not None:
        return False
    return session.starts_at <= now <= session.ends_at
