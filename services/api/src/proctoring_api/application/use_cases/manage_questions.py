"""Casos de uso de preguntas: crearlas, listarlas y servirlas al estudiante."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.ports.participant_repository import ParticipantRepository
from proctoring_api.application.ports.question_bank_repository import QuestionBankRepository
from proctoring_api.application.ports.question_repository import QuestionRepository
from proctoring_api.application.session_access import ensure_teacher_owns_session
from proctoring_api.application.use_cases.manage_enrollment import (
    DEFAULT_DEV_STUDENT_ID,
    ensure_can_take_exam,
)
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.question import (
    ExamQuestion,
    InvalidQuestionError,
    Question,
    QuestionType,
)
from proctoring_api.domain.question_bank import draw_questions
from proctoring_api.domain.user import AuthenticatedUser

#: Tope por sesion. No es arbitrario: cada pregunta y sus opciones viajan al
#: cliente, y un examen de miles de preguntas seria un error del docente o un
#: intento de agotar la memoria del servicio.
MAX_QUESTIONS_PER_SESSION = 200


@dataclass(frozen=True, slots=True)
class NewQuestion:
    """Una pregunta a crear, ya con los tipos correctos."""

    question_type: QuestionType
    statement: str
    points: Decimal = Decimal(1)
    options: list[tuple[str, bool]] = field(default_factory=list)
    correct_numeric_answer: Decimal | None = None
    numeric_tolerance: Decimal | None = None
    correct_text_answer: str | None = None
    source_format: str | None = None


class AddQuestions:
    """Anade preguntas al final del examen. Solo el docente dueno."""

    def __init__(
        self, questions: QuestionRepository, sessions: ExamSessionRepository | None = None
    ) -> None:
        self._questions = questions
        self._sessions = sessions

    def execute(
        self,
        session_id: UUID,
        nuevas: Sequence[NewQuestion],
        *,
        actor: AuthenticatedUser | None = None,
    ) -> Sequence[Question]:
        """Crea las preguntas y devuelve lo guardado.

        Raises:
            AuthorizationError: si quien pide no es el docente dueno.
            InvalidQuestionError: si alguna pregunta viola una regla, o si se
                pasa del tope por sesion.
        """
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo un docente puede anadir preguntas a un examen")
        ensure_teacher_owns_session(self._sessions, session_id, actor)

        if not nuevas:
            raise InvalidQuestionError("No se envio ninguna pregunta")

        ya_hay = self._questions.count_by_session(session_id)
        if ya_hay + len(nuevas) > MAX_QUESTIONS_PER_SESSION:
            raise InvalidQuestionError(
                f"Un examen admite como maximo {MAX_QUESTIONS_PER_SESSION} preguntas "
                f"(tiene {ya_hay})"
            )

        # Se construyen TODAS antes de guardar ninguna: si la tercera es
        # invalida, el docente no se queda con dos preguntas sueltas y un error.
        construidas = [
            Question.create(
                session_id=session_id,
                position=ya_hay + indice,
                question_type=nueva.question_type,
                statement=nueva.statement,
                points=nueva.points,
                options=nueva.options,
                correct_numeric_answer=nueva.correct_numeric_answer,
                numeric_tolerance=nueva.numeric_tolerance,
                correct_text_answer=nueva.correct_text_answer,
                source_format=nueva.source_format,
            )
            for indice, nueva in enumerate(nuevas, start=1)
        ]

        self._questions.save_many(construidas)
        return construidas


class ListSessionQuestions:
    """Preguntas **con** sus respuestas correctas. Solo para el docente dueno."""

    def __init__(
        self, questions: QuestionRepository, sessions: ExamSessionRepository | None = None
    ) -> None:
        self._questions = questions
        self._sessions = sessions

    def execute(
        self, session_id: UUID, *, actor: AuthenticatedUser | None = None
    ) -> Sequence[Question]:
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError(
                "Las respuestas correctas solo las ve el docente. Para rendir el "
                "examen usa el endpoint del examen."
            )
        ensure_teacher_owns_session(self._sessions, session_id, actor)

        return self._questions.list_by_session(session_id)


class GetExamQuestions:
    """Preguntas **sin** respuestas correctas, para rendir el examen.

    Tres cosas lo protegen: el tipo que devuelve no tiene dónde guardar la
    respuesta; la ventana del examen se comprueba antes, porque si no un
    estudiante podría descargarlo la noche anterior; y se exige estar
    **matriculado**, porque conocer el `session_id` de un examen ajeno no debería
    dar acceso a sus preguntas.

    Si el examen tiene bancos atados, las preguntas salen de ahí y se **sortean
    por estudiante**. El sorteo es determinista: el mismo estudiante recibe
    siempre las mismas, aunque recargue la página a mitad del examen. Si no lo
    fuera, al recargar vería preguntas nuevas y perdería lo respondido.
    """

    def __init__(
        self,
        questions: QuestionRepository,
        sessions: ExamSessionRepository,
        clock: Clock,
        participants: ParticipantRepository | None = None,
        dev_student_id: UUID = DEFAULT_DEV_STUDENT_ID,
        banks: QuestionBankRepository | None = None,
    ) -> None:
        self._questions = questions
        self._sessions = sessions
        self._clock = clock
        self._participants = participants
        self._dev_student_id = dev_student_id
        self._banks = banks

    def execute(
        self, session_id: UUID, *, actor: AuthenticatedUser | None = None
    ) -> Sequence[ExamQuestion]:
        """Devuelve el examen tal como lo ve el estudiante.

        Raises:
            AuthorizationError: si un docente lo pide por aqui (tiene su propio
                endpoint), si la sesion no existe, o si el examen todavia no
                empezo o ya termino.
        """
        if actor is not None and actor.is_teacher:
            raise AuthorizationError(
                "Un docente ve su examen con las respuestas desde su panel, no por aqui"
            )

        sesion = self._sessions.find_by_id(session_id)
        if sesion is None:
            raise AuthorizationError("No tienes acceso a este examen")

        ahora = self._clock.now()
        if not (sesion.starts_at <= ahora <= sesion.ends_at):
            raise AuthorizationError(
                "El examen no esta abierto en este momento. Revisa la hora de inicio."
            )

        # Conocer el session_id no basta: hay que estar matriculado, haber
        # consentido, tener la identidad resuelta y no haber entregado.
        ensure_can_take_exam(self._participants, session_id, actor, self._dev_student_id)

        return [pregunta.for_student() for pregunta in self._para(sesion, actor)]

    def _para(self, sesion: ExamSession, actor: AuthenticatedUser | None) -> Sequence[Question]:
        """Las preguntas que le tocan a este estudiante.

        Sin bancos atados, las del propio examen y en su orden: es como funcionaba
        antes y los exámenes ya creados siguen igual.
        """
        bancos = self._banks.list_session_banks(sesion.id) if self._banks is not None else []
        if not bancos:
            return self._questions.list_by_session(sesion.id)

        disponibles = self._questions.list_by_banks([b.id for b in bancos])

        # La semilla del sorteo es la **matrícula**, no el estudiante: así dos
        # intentos del mismo examen pueden traer preguntas distintas, que es lo
        # que se espera de un segundo intento.
        participante = (
            self._participants.find(
                sesion.id, actor.id if actor is not None else self._dev_student_id
            )
            if self._participants is not None
            else None
        )
        if participante is None:
            # Sin matrícula no se llega aquí (lo impide `ensure_can_take_exam`),
            # salvo en el modo sin autenticación sin repositorio. Se entrega todo
            # en orden en vez de fallar.
            return disponibles

        return draw_questions(
            disponibles,
            session_id=sesion.id,
            participant_id=participante.id,
            pool_size=sesion.question_pool_size,
            shuffle=sesion.shuffle_questions,
        )
