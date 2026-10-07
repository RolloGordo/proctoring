"""Bancos de preguntas: crearlos, llenarlos y atarlos a un examen."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.ports.question_bank_repository import QuestionBankRepository
from proctoring_api.application.ports.question_repository import QuestionRepository
from proctoring_api.application.session_access import ensure_teacher_owns_session
from proctoring_api.application.use_cases.create_exam_session import DEFAULT_DEV_TEACHER_ID
from proctoring_api.application.use_cases.manage_questions import (
    MAX_QUESTIONS_PER_SESSION,
    NewQuestion,
)
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.question import InvalidQuestionError, Question
from proctoring_api.domain.question_bank import QuestionBank
from proctoring_api.domain.user import AuthenticatedUser

#: Tope por banco. Mas generoso que el de un examen porque un banco es
#: precisamente el sitio donde se acumulan preguntas de varios años.
MAX_QUESTIONS_PER_BANK = 1000


@dataclass(frozen=True, slots=True)
class BankSummary:
    """Un banco con cuántas preguntas tiene."""

    bank: QuestionBank
    question_count: int


def ensure_teacher_owns_bank(
    banks: QuestionBankRepository, bank_id: UUID, actor: AuthenticatedUser | None
) -> QuestionBank:
    """Devuelve el banco si quien pregunta es su docente.

    Raises:
        AuthorizationError: si el banco no es suyo **o no existe**. Se responde lo
            mismo en los dos casos: distinguirlos permitiría averiguar qué bancos
            existen.
    """
    bank = banks.find_by_id(bank_id)
    if bank is None:
        raise AuthorizationError("No tienes acceso a este banco de preguntas")

    if actor is not None and (not actor.is_teacher or bank.teacher_id != actor.id):
        raise AuthorizationError("No tienes acceso a este banco de preguntas")

    return bank


class CreateQuestionBank:
    """Crea un banco. Solo un docente."""

    def __init__(
        self,
        banks: QuestionBankRepository,
        clock: Clock,
        dev_teacher_id: UUID = DEFAULT_DEV_TEACHER_ID,
    ) -> None:
        self._banks = banks
        self._clock = clock
        self._dev_teacher_id = dev_teacher_id

    def execute(
        self,
        name: str,
        *,
        course_id: UUID | None = None,
        description: str | None = None,
        actor: AuthenticatedUser | None = None,
    ) -> QuestionBank:
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo un docente puede crear un banco de preguntas")

        bank = QuestionBank.create(
            teacher_id=actor.id if actor is not None else self._dev_teacher_id,
            name=name,
            course_id=course_id,
            description=description,
            created_at=self._clock.now(),
        )
        self._banks.save(bank)
        return bank


class ListQuestionBanks:
    """Los bancos del docente que pregunta, con cuántas preguntas tiene cada uno."""

    def __init__(
        self,
        banks: QuestionBankRepository,
        dev_teacher_id: UUID = DEFAULT_DEV_TEACHER_ID,
    ) -> None:
        self._banks = banks
        self._dev_teacher_id = dev_teacher_id

    def execute(self, *, actor: AuthenticatedUser | None = None) -> Sequence[BankSummary]:
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo un docente tiene bancos propios")

        teacher_id = actor.id if actor is not None else self._dev_teacher_id
        bancos = self._banks.list_by_teacher(teacher_id)
        # El conteo llega en una consulta para todos, no una por banco.
        conteo = self._banks.count_questions([b.id for b in bancos])
        return [BankSummary(bank=b, question_count=conteo.get(b.id, 0)) for b in bancos]


class ListBankQuestions:
    """Las preguntas de un banco, **con** sus respuestas correctas."""

    def __init__(self, banks: QuestionBankRepository, questions: QuestionRepository) -> None:
        self._banks = banks
        self._questions = questions

    def execute(
        self, bank_id: UUID, *, actor: AuthenticatedUser | None = None
    ) -> Sequence[Question]:
        ensure_teacher_owns_bank(self._banks, bank_id, actor)
        return self._questions.list_by_bank(bank_id)


class AddQuestionsToBank:
    """Añade preguntas al banco. Es también el destino de la importación QTI."""

    def __init__(self, banks: QuestionBankRepository, questions: QuestionRepository) -> None:
        self._banks = banks
        self._questions = questions

    def execute(
        self,
        bank_id: UUID,
        nuevas: Sequence[NewQuestion],
        *,
        actor: AuthenticatedUser | None = None,
    ) -> Sequence[Question]:
        """Raises:
        AuthorizationError: si el banco no es del docente.
        InvalidQuestionError: si no se envía ninguna, si alguna viola una regla
            o si se pasa del tope del banco.
        """
        ensure_teacher_owns_bank(self._banks, bank_id, actor)

        if not nuevas:
            raise InvalidQuestionError("No se envio ninguna pregunta")

        ya_hay = self._questions.count_by_bank(bank_id)
        if ya_hay + len(nuevas) > MAX_QUESTIONS_PER_BANK:
            raise InvalidQuestionError(
                f"Un banco admite como maximo {MAX_QUESTIONS_PER_BANK} preguntas (tiene {ya_hay})"
            )

        # Se construyen todas antes de guardar ninguna: importando 40 preguntas de
        # un QTI, que la trigésima sea inválida no puede dejar 29 a medias.
        construidas = [
            Question.create(
                bank_id=bank_id,
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


class AttachBankToSession:
    """Ata un banco a un examen: a partir de ahí, el examen extrae de él."""

    def __init__(
        self,
        banks: QuestionBankRepository,
        sessions: ExamSessionRepository,
    ) -> None:
        self._banks = banks
        self._sessions = sessions

    def execute(
        self, session_id: UUID, bank_id: UUID, *, actor: AuthenticatedUser | None = None
    ) -> bool:
        """Devuelve `False` si ya estaba atado. Idempotente.

        Raises:
            AuthorizationError: si el examen o el banco no son del docente. Hacen
                falta **los dos**: sin comprobar el banco, un docente podría atar
                el banco de otro a su propio examen y leerlo entero por la puerta
                de atrás.
        """
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo un docente arma sus examenes")
        ensure_teacher_owns_session(self._sessions, session_id, actor)
        ensure_teacher_owns_bank(self._banks, bank_id, actor)

        return self._banks.attach_to_session(session_id, bank_id)


class DetachBankFromSession:
    """Quita un banco de un examen. Las preguntas del banco no se tocan."""

    def __init__(
        self,
        banks: QuestionBankRepository,
        sessions: ExamSessionRepository,
    ) -> None:
        self._banks = banks
        self._sessions = sessions

    def execute(
        self, session_id: UUID, bank_id: UUID, *, actor: AuthenticatedUser | None = None
    ) -> None:
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo un docente arma sus examenes")
        ensure_teacher_owns_session(self._sessions, session_id, actor)
        ensure_teacher_owns_bank(self._banks, bank_id, actor)

        self._banks.detach_from_session(session_id, bank_id)


class ListSessionBanks:
    """De qué bancos extrae un examen, y cuántas preguntas suman."""

    def __init__(
        self,
        banks: QuestionBankRepository,
        sessions: ExamSessionRepository | None = None,
    ) -> None:
        self._banks = banks
        self._sessions = sessions

    def execute(
        self, session_id: UUID, *, actor: AuthenticatedUser | None = None
    ) -> Sequence[BankSummary]:
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo el docente ve como esta armado su examen")
        ensure_teacher_owns_session(self._sessions, session_id, actor)

        bancos = self._banks.list_session_banks(session_id)
        conteo = self._banks.count_questions([b.id for b in bancos])
        return [BankSummary(bank=b, question_count=conteo.get(b.id, 0)) for b in bancos]


__all__ = [
    "MAX_QUESTIONS_PER_BANK",
    "MAX_QUESTIONS_PER_SESSION",
    "AddQuestionsToBank",
    "AttachBankToSession",
    "BankSummary",
    "CreateQuestionBank",
    "DetachBankFromSession",
    "ListBankQuestions",
    "ListQuestionBanks",
    "ListSessionBanks",
    "ensure_teacher_owns_bank",
]
