"""Guardar y recuperar las respuestas del estudiante mientras rinde."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from proctoring_api.application.exam_questions import questions_for
from proctoring_api.application.ports.answer_repository import AnswerRepository
from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.ports.participant_repository import ParticipantRepository
from proctoring_api.application.ports.question_bank_repository import QuestionBankRepository
from proctoring_api.application.ports.question_repository import QuestionRepository
from proctoring_api.application.use_cases.manage_enrollment import (
    DEFAULT_DEV_STUDENT_ID,
    ensure_can_take_exam,
)
from proctoring_api.domain.answer import Answer, InvalidAnswerError
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.participant import SessionParticipant
from proctoring_api.domain.user import AuthenticatedUser

#: Tope de respuestas por peticion. La pantalla del examen guarda de a una,
#: asi que un lote grande solo aparece al retomar; mas que el maximo de
#: preguntas por examen no tiene sentido.
MAX_ANSWERS_PER_REQUEST = 200


@dataclass(frozen=True, slots=True)
class AnswerInput:
    """Una respuesta tal como llega del cliente, ya con los tipos correctos."""

    question_id: UUID
    selected_option_id: UUID | None = None
    text_answer: str | None = None
    numeric_answer: Decimal | None = None


class SaveAnswers:
    """Guarda lo que el estudiante respondió.

    Guardar es **continuo**, no solo al entregar: si la aplicación se cierra a
    mitad del examen —y en un examen supervisado se cierra: se cae la cámara, se
    reinicia el equipo— lo respondido tiene que seguir ahí. Por eso la misma
    pregunta se puede guardar muchas veces y la última gana.

    Las mismas cuatro condiciones que para leer las preguntas: matriculado, con
    consentimiento, con la identidad resuelta y sin haber entregado. Y además la
    ventana del examen abierta, porque responder después de que cierra sería
    responder fuera de tiempo.
    """

    def __init__(
        self,
        answers: AnswerRepository,
        questions: QuestionRepository,
        participants: ParticipantRepository,
        sessions: ExamSessionRepository,
        clock: Clock,
        dev_student_id: UUID = DEFAULT_DEV_STUDENT_ID,
        banks: QuestionBankRepository | None = None,
    ) -> None:
        self._answers = answers
        self._questions = questions
        self._participants = participants
        self._sessions = sessions
        self._clock = clock
        self._dev_student_id = dev_student_id
        self._banks = banks

    def execute(
        self,
        session_id: UUID,
        entradas: Sequence[AnswerInput],
        *,
        actor: AuthenticatedUser | None = None,
    ) -> Sequence[Answer]:
        """Guarda las respuestas y devuelve lo guardado.

        Raises:
            AuthorizationError: si lo pide un docente, si el examen no está
                abierto o si no puede rendirlo.
            InvalidAnswerError: si no se envía ninguna, si se pasa del tope, si
                una pregunta no es de este examen o si la forma no corresponde
                al tipo de pregunta.
        """
        if actor is not None and actor.is_teacher:
            raise AuthorizationError("Un docente no responde el examen de un estudiante")

        if not entradas:
            raise InvalidAnswerError("No se envio ninguna respuesta")
        if len(entradas) > MAX_ANSWERS_PER_REQUEST:
            raise InvalidAnswerError(
                f"Como maximo {MAX_ANSWERS_PER_REQUEST} respuestas por peticion"
            )

        ahora = self._clock.now()
        sesion, participante = self._require_participant(session_id, actor, ahora)

        # Las preguntas **de este estudiante**, indexadas: responder una pregunta
        # de otro examen tiene que fallar aunque se conozca su id.
        #
        # El mismo `questions_for` que las entrega y que las califica, y no las
        # del examen a secas. Las de un banco no son del examen —tienen
        # `session_id` nulo y cuelgan del banco—, asi que validar contra el
        # examen dejaba un examen con banco que se mostraba entero y no aceptaba
        # ni una respuesta. Y de paso, una pregunta del banco que a este
        # estudiante no le salio en el sorteo tampoco se le acepta.
        del_examen = {
            pregunta.id: pregunta.for_student()
            for pregunta in questions_for(sesion, participante.id, self._questions, self._banks)
        }

        # Se construyen todas antes de guardar ninguna: si la tercera viene mal,
        # el estudiante no se queda con dos guardadas y un error.
        construidas = []
        for entrada in entradas:
            pregunta = del_examen.get(entrada.question_id)
            if pregunta is None:
                raise InvalidAnswerError("Esa pregunta no es de este examen")
            construidas.append(
                Answer.create(
                    question=pregunta,
                    participant_id=participante.id,
                    answered_at=ahora,
                    selected_option_id=entrada.selected_option_id,
                    text_answer=entrada.text_answer,
                    numeric_answer=entrada.numeric_answer,
                )
            )

        self._answers.save_many(construidas)
        return construidas

    def _require_participant(
        self, session_id: UUID, actor: AuthenticatedUser | None, ahora: datetime
    ) -> tuple[ExamSession, SessionParticipant]:
        sesion = self._sessions.find_by_id(session_id)
        if sesion is None:
            raise AuthorizationError("No tienes acceso a este examen")

        if not (sesion.starts_at <= ahora <= sesion.ends_at):
            raise AuthorizationError("El examen no esta abierto en este momento")

        ensure_can_take_exam(self._participants, session_id, actor, self._dev_student_id)

        quien = actor.id if actor is not None else self._dev_student_id
        participante = self._participants.find(session_id, quien)
        if participante is None:
            raise AuthorizationError("No estas matriculado en este examen")
        return sesion, participante


class ListMyAnswers:
    """Lo que el estudiante ya respondió, para retomar el examen donde lo dejó."""

    def __init__(
        self,
        answers: AnswerRepository,
        participants: ParticipantRepository,
        dev_student_id: UUID = DEFAULT_DEV_STUDENT_ID,
    ) -> None:
        self._answers = answers
        self._participants = participants
        self._dev_student_id = dev_student_id

    def execute(
        self, session_id: UUID, *, actor: AuthenticatedUser | None = None
    ) -> Sequence[Answer]:
        """Devuelve solo las respuestas de quien pregunta.

        Un estudiante no ve las respuestas de otro: se busca por su propia
        matrícula, no por un `participant_id` que venga del cliente.

        Raises:
            AuthorizationError: si lo pide un docente o si no está matriculado.
        """
        if actor is not None and actor.is_teacher:
            raise AuthorizationError(
                "Las respuestas de un estudiante se revisan desde el panel del docente"
            )

        quien = actor.id if actor is not None else self._dev_student_id
        participante = self._participants.find(session_id, quien)
        if participante is None:
            raise AuthorizationError("No estas matriculado en este examen")

        return self._answers.list_by_participant(participante.id)


__all__ = [
    "MAX_ANSWERS_PER_REQUEST",
    "AnswerInput",
    "InvalidAnswerError",
    "ListMyAnswers",
    "SaveAnswers",
]
