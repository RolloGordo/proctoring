"""Corregir y borrar una pregunta.

La regla que sostiene todo esto: una pregunta ya respondida no se toca. Cambiarle
la alternativa correcta reescribiría en silencio la nota de quien la respondió
bien, y nadie se enteraría.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from proctoring_api.adapters.outbound.memory.answer_repository import InMemoryAnswerRepository
from proctoring_api.adapters.outbound.memory.exam_session_repository import (
    InMemoryExamSessionRepository,
)
from proctoring_api.adapters.outbound.memory.question_bank_repository import (
    InMemoryQuestionBankRepository,
)
from proctoring_api.adapters.outbound.memory.question_repository import InMemoryQuestionRepository
from proctoring_api.application.use_cases.edit_questions import (
    DeleteQuestion,
    QuestionAlreadyAnsweredError,
    QuestionChanges,
    UpdateQuestion,
)
from proctoring_api.domain.answer import Answer
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.question import InvalidQuestionError, Question, QuestionType
from proctoring_api.domain.question_bank import QuestionBank
from proctoring_api.domain.user import AuthenticatedUser, UserRole

from tests.conftest import NOW

DOCENTE = AuthenticatedUser(id=uuid4(), role=UserRole.TEACHER)
OTRO_DOCENTE = AuthenticatedUser(id=uuid4(), role=UserRole.TEACHER)
ANA = AuthenticatedUser(id=uuid4(), role=UserRole.STUDENT)


@pytest.fixture
def sessions() -> InMemoryExamSessionRepository:
    return InMemoryExamSessionRepository()


@pytest.fixture
def questions() -> InMemoryQuestionRepository:
    return InMemoryQuestionRepository()


@pytest.fixture
def answers() -> InMemoryAnswerRepository:
    return InMemoryAnswerRepository()


@pytest.fixture
def banks(questions: InMemoryQuestionRepository) -> InMemoryQuestionBankRepository:
    return InMemoryQuestionBankRepository(questions)


@pytest.fixture
def sesion(sessions: InMemoryExamSessionRepository) -> ExamSession:
    creada = ExamSession.create(
        teacher_id=DOCENTE.id,
        title="Parcial",
        starts_at=NOW,
        duration_minutes=60,
    )
    sessions.save(creada)
    return creada


@pytest.fixture
def pregunta(questions: InMemoryQuestionRepository, sesion: ExamSession) -> Question:
    creada = Question.create(
        session_id=sesion.id,
        position=1,
        question_type=QuestionType.MULTIPLE_CHOICE,
        statement="¿Qué hace RLS?",
        points=Decimal(2),
        options=[("Filtra filas", True), ("Comprime", False)],
    )
    questions.save_many([creada])
    return creada


def respondida(answers: InMemoryAnswerRepository, pregunta: Question) -> None:
    answers.save_many(
        [
            Answer.create(
                question=pregunta.for_student(),
                participant_id=uuid4(),
                answered_at=NOW,
                selected_option_id=pregunta.options[0].id,
            )
        ]
    )


class TestCorregir:
    def test_se_cambian_los_puntos(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        pregunta: Question,
    ) -> None:
        corregida = UpdateQuestion(questions, sessions).execute(
            pregunta.id, QuestionChanges(points=Decimal(5)), actor=DOCENTE
        )

        assert corregida.points == Decimal(5)
        guardada = questions.find_by_id(pregunta.id)
        assert guardada is not None
        assert guardada.points == Decimal(5)

    def test_se_corrige_una_errata_del_enunciado(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        pregunta: Question,
    ) -> None:
        corregida = UpdateQuestion(questions, sessions).execute(
            pregunta.id,
            QuestionChanges(statement="¿Qué garantiza Row Level Security?"),
            actor=DOCENTE,
        )

        assert corregida.statement == "¿Qué garantiza Row Level Security?"
        # Y no se lleva por delante las alternativas.
        assert len(corregida.options) == 2

    def test_lo_que_no_se_envia_no_se_toca(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        pregunta: Question,
    ) -> None:
        corregida = UpdateQuestion(questions, sessions).execute(
            pregunta.id, QuestionChanges(points=Decimal(3)), actor=DOCENTE
        )

        assert corregida.statement == pregunta.statement
        assert [o.option_text for o in corregida.options] == [
            o.option_text for o in pregunta.options
        ]
        assert corregida.position == pregunta.position

    def test_el_id_y_la_posicion_no_cambian(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        pregunta: Question,
    ) -> None:
        """Un id nuevo dejaría huérfanas las respuestas ya guardadas."""
        corregida = UpdateQuestion(questions, sessions).execute(
            pregunta.id, QuestionChanges(statement="Otra cosa"), actor=DOCENTE
        )

        assert corregida.id == pregunta.id
        assert corregida.position == pregunta.position
        assert corregida.session_id == pregunta.session_id

    def test_se_reemplazan_las_alternativas(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        pregunta: Question,
    ) -> None:
        corregida = UpdateQuestion(questions, sessions).execute(
            pregunta.id,
            QuestionChanges(options=[("A", False), ("B", True), ("C", False)]),
            actor=DOCENTE,
        )

        assert [o.option_text for o in corregida.options] == ["A", "B", "C"]
        assert [o.is_correct for o in corregida.options] == [False, True, False]

    def test_editar_revalida(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        pregunta: Question,
    ) -> None:
        """Sin esto se colaría por la edición una pregunta sin ninguna correcta,
        que `create` nunca habría aceptado."""
        with pytest.raises(InvalidQuestionError):
            UpdateQuestion(questions, sessions).execute(
                pregunta.id,
                QuestionChanges(options=[("A", False), ("B", False)]),
                actor=DOCENTE,
            )

    def test_un_enunciado_vacio_se_rechaza(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        pregunta: Question,
    ) -> None:
        with pytest.raises(InvalidQuestionError):
            UpdateQuestion(questions, sessions).execute(
                pregunta.id, QuestionChanges(statement="   "), actor=DOCENTE
            )

    def test_una_pregunta_ajena_no_se_edita(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        pregunta: Question,
    ) -> None:
        with pytest.raises(AuthorizationError):
            UpdateQuestion(questions, sessions).execute(
                pregunta.id, QuestionChanges(points=Decimal(99)), actor=OTRO_DOCENTE
            )

    def test_una_inexistente_responde_igual_que_una_ajena(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        pregunta: Question,
    ) -> None:
        with pytest.raises(AuthorizationError) as ajena:
            UpdateQuestion(questions, sessions).execute(
                pregunta.id, QuestionChanges(points=Decimal(1)), actor=OTRO_DOCENTE
            )
        with pytest.raises(AuthorizationError) as no_existe:
            UpdateQuestion(questions, sessions).execute(
                uuid4(), QuestionChanges(points=Decimal(1)), actor=OTRO_DOCENTE
            )

        assert str(ajena.value) == str(no_existe.value)

    def test_un_estudiante_no_edita_preguntas(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        pregunta: Question,
    ) -> None:
        with pytest.raises(AuthorizationError, match="Solo un docente"):
            UpdateQuestion(questions, sessions).execute(
                pregunta.id, QuestionChanges(points=Decimal(20)), actor=ANA
            )


class TestYaRespondida:
    def test_no_se_corrige(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        answers: InMemoryAnswerRepository,
        pregunta: Question,
    ) -> None:
        respondida(answers, pregunta)

        with pytest.raises(QuestionAlreadyAnsweredError, match="reescribiria su nota"):
            UpdateQuestion(questions, sessions, None, answers).execute(
                pregunta.id,
                QuestionChanges(options=[("Filtra filas", False), ("Comprime", True)]),
                actor=DOCENTE,
            )

    def test_tampoco_se_borra(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        answers: InMemoryAnswerRepository,
        pregunta: Question,
    ) -> None:
        respondida(answers, pregunta)

        with pytest.raises(QuestionAlreadyAnsweredError):
            DeleteQuestion(questions, sessions, None, answers).execute(pregunta.id, actor=DOCENTE)

        assert questions.find_by_id(pregunta.id) is not None

    def test_otra_pregunta_del_mismo_examen_si_se_corrige(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        answers: InMemoryAnswerRepository,
        sesion: ExamSession,
        pregunta: Question,
    ) -> None:
        """El bloqueo es por pregunta, no por examen: si fuera por examen, una
        sola respuesta congelaría las cien preguntas restantes."""
        respondida(answers, pregunta)
        otra = Question.create(
            session_id=sesion.id,
            position=2,
            question_type=QuestionType.ESSAY,
            statement="Explica RLS",
            points=Decimal(5),
        )
        questions.save_many([otra])

        corregida = UpdateQuestion(questions, sessions, None, answers).execute(
            otra.id, QuestionChanges(points=Decimal(8)), actor=DOCENTE
        )

        assert corregida.points == Decimal(8)


class TestBorrar:
    def test_se_borra_una_pregunta_sin_responder(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        pregunta: Question,
    ) -> None:
        DeleteQuestion(questions, sessions).execute(pregunta.id, actor=DOCENTE)

        assert questions.find_by_id(pregunta.id) is None

    def test_las_demas_no_se_renumeran(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        sesion: ExamSession,
        pregunta: Question,
    ) -> None:
        """Las posiciones dejan huecos (1, 3) y está bien: el orden se conserva,
        que es lo único que `position` promete."""
        tercera = Question.create(
            session_id=sesion.id,
            position=3,
            question_type=QuestionType.ESSAY,
            statement="Tercera",
            points=Decimal(1),
        )
        segunda = Question.create(
            session_id=sesion.id,
            position=2,
            question_type=QuestionType.ESSAY,
            statement="Segunda",
            points=Decimal(1),
        )
        questions.save_many([segunda, tercera])

        DeleteQuestion(questions, sessions).execute(segunda.id, actor=DOCENTE)

        quedan = questions.list_by_session(sesion.id)
        assert [q.position for q in quedan] == [1, 3]
        assert [q.statement for q in quedan] == [pregunta.statement, "Tercera"]

    def test_no_se_borra_una_pregunta_ajena(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        pregunta: Question,
    ) -> None:
        with pytest.raises(AuthorizationError):
            DeleteQuestion(questions, sessions).execute(pregunta.id, actor=OTRO_DOCENTE)

        assert questions.find_by_id(pregunta.id) is not None


class TestPreguntasDeBanco:
    def test_el_dueno_del_banco_corrige_sus_preguntas(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        banks: InMemoryQuestionBankRepository,
    ) -> None:
        banco = QuestionBank.create(teacher_id=DOCENTE.id, name="Banco", created_at=NOW)
        banks.save(banco)
        suya = Question.create(
            bank_id=banco.id,
            position=1,
            question_type=QuestionType.ESSAY,
            statement="Del banco",
            points=Decimal(1),
        )
        questions.save_many([suya])

        corregida = UpdateQuestion(questions, sessions, banks).execute(
            suya.id, QuestionChanges(points=Decimal(4)), actor=DOCENTE
        )

        assert corregida.points == Decimal(4)
        assert corregida.bank_id == banco.id
        assert corregida.session_id is None

    def test_otro_docente_no_toca_el_banco_ajeno(
        self,
        questions: InMemoryQuestionRepository,
        sessions: InMemoryExamSessionRepository,
        banks: InMemoryQuestionBankRepository,
    ) -> None:
        banco = QuestionBank.create(teacher_id=DOCENTE.id, name="Banco", created_at=NOW)
        banks.save(banco)
        suya = Question.create(
            bank_id=banco.id,
            position=1,
            question_type=QuestionType.ESSAY,
            statement="Del banco",
            points=Decimal(1),
        )
        questions.save_many([suya])

        with pytest.raises(AuthorizationError):
            UpdateQuestion(questions, sessions, banks).execute(
                suya.id, QuestionChanges(points=Decimal(99)), actor=OTRO_DOCENTE
            )
