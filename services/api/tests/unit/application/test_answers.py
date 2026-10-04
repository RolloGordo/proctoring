"""Guardar respuestas: quién puede, cuándo y de qué examen."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from proctoring_api.adapters.outbound.memory.answer_repository import InMemoryAnswerRepository
from proctoring_api.adapters.outbound.memory.exam_session_repository import (
    InMemoryExamSessionRepository,
)
from proctoring_api.adapters.outbound.memory.participant_repository import (
    InMemoryParticipantRepository,
)
from proctoring_api.adapters.outbound.memory.question_repository import InMemoryQuestionRepository
from proctoring_api.application.use_cases.manage_answers import (
    AnswerInput,
    ListMyAnswers,
    SaveAnswers,
)
from proctoring_api.application.use_cases.manage_enrollment import DEFAULT_DEV_STUDENT_ID
from proctoring_api.domain.answer import InvalidAnswerError
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.participant import SessionParticipant
from proctoring_api.domain.question import Question, QuestionType
from proctoring_api.domain.user import AuthenticatedUser, UserRole

NOW = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)
ESTUDIANTE = UUID("7b2e4d10-5c6f-4a8b-9d0e-2f3a4b5c6d71")
DOCENTE = UUID("0f9e8d7c-6b5a-4938-8271-6a5b4c3d2e1f")


class FixedClock:
    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment


class Escenario:
    """Un examen abierto, con una pregunta, y un estudiante que puede rendirlo."""

    def __init__(self, *, verificado: bool = True, entregado: bool = False) -> None:
        self.sesiones = InMemoryExamSessionRepository()
        self.preguntas = InMemoryQuestionRepository()
        self.participantes = InMemoryParticipantRepository()
        self.respuestas = InMemoryAnswerRepository()
        self.clock = FixedClock(NOW)

        self.sesion = ExamSession.create(
            teacher_id=DOCENTE,
            title="Parcial",
            starts_at=NOW - timedelta(minutes=10),
            duration_minutes=90,
        )
        self.sesiones.save(self.sesion)

        self.pregunta = Question.create(
            session_id=self.sesion.id,
            position=1,
            question_type=QuestionType.MULTIPLE_CHOICE,
            statement="¿Que hace RLS?",
            options=[("Filtra filas", True), ("Comprime", False)],
        )
        self.preguntas.save_many([self.pregunta])

        participante = SessionParticipant.enroll(
            session_id=self.sesion.id, student_id=ESTUDIANTE, consented_at=NOW
        )
        if verificado:
            participante = participante.verified(NOW)
        if entregado:
            participante = participante.submitted(NOW)
        self.participante = participante
        self.participantes.save(participante)

        self.guardar = SaveAnswers(
            self.respuestas,
            self.preguntas,
            self.participantes,
            self.sesiones,
            self.clock,
        )
        self.listar = ListMyAnswers(self.respuestas, self.participantes)

    @property
    def actor(self) -> AuthenticatedUser:
        return AuthenticatedUser(id=ESTUDIANTE, role=UserRole.STUDENT)

    def eleccion(self, indice: int = 0) -> AnswerInput:
        return AnswerInput(
            question_id=self.pregunta.id,
            selected_option_id=self.pregunta.options[indice].id,
        )


class TestGuardar:
    def test_guarda_la_respuesta_del_estudiante(self) -> None:
        e = Escenario()

        guardadas = e.guardar.execute(e.sesion.id, [e.eleccion()], actor=e.actor)

        assert len(guardadas) == 1
        assert guardadas[0].participant_id == e.participante.id
        assert e.respuestas.list_by_participant(e.participante.id) == list(guardadas)

    def test_responder_otra_vez_reemplaza(self) -> None:
        # El estudiante cambia de opinión: no se guardan dos respuestas a la
        # misma pregunta, se queda la última.
        e = Escenario()

        e.guardar.execute(e.sesion.id, [e.eleccion(0)], actor=e.actor)
        e.guardar.execute(e.sesion.id, [e.eleccion(1)], actor=e.actor)

        guardadas = e.respuestas.list_by_participant(e.participante.id)
        assert len(guardadas) == 1
        assert guardadas[0].selected_option_id == e.pregunta.options[1].id

    def test_rechaza_una_pregunta_de_otro_examen(self) -> None:
        e = Escenario()
        ajena = AnswerInput(question_id=uuid4(), selected_option_id=uuid4())

        with pytest.raises(InvalidAnswerError, match="no es de este examen"):
            e.guardar.execute(e.sesion.id, [ajena], actor=e.actor)

    def test_no_guarda_nada_si_una_del_lote_es_invalida(self) -> None:
        e = Escenario()
        mala = AnswerInput(question_id=e.pregunta.id, numeric_answer=Decimal(5))

        with pytest.raises(InvalidAnswerError):
            e.guardar.execute(e.sesion.id, [e.eleccion(), mala], actor=e.actor)

        assert e.respuestas.list_by_participant(e.participante.id) == []

    def test_rechaza_un_lote_vacio(self) -> None:
        e = Escenario()

        with pytest.raises(InvalidAnswerError, match="ninguna"):
            e.guardar.execute(e.sesion.id, [], actor=e.actor)


class TestQuienPuede:
    def test_un_docente_no_responde_el_examen(self) -> None:
        e = Escenario()
        docente = AuthenticatedUser(id=DOCENTE, role=UserRole.TEACHER)

        with pytest.raises(AuthorizationError):
            e.guardar.execute(e.sesion.id, [e.eleccion()], actor=docente)

    def test_sin_matricula_no_se_responde(self) -> None:
        e = Escenario()
        otro = AuthenticatedUser(id=uuid4(), role=UserRole.STUDENT)

        with pytest.raises(AuthorizationError, match="matriculado"):
            e.guardar.execute(e.sesion.id, [e.eleccion()], actor=otro)

    def test_sin_identidad_resuelta_no_se_responde(self) -> None:
        e = Escenario(verificado=False)

        with pytest.raises(AuthorizationError, match="identidad"):
            e.guardar.execute(e.sesion.id, [e.eleccion()], actor=e.actor)

    def test_despues_de_entregar_no_se_responde(self) -> None:
        e = Escenario(entregado=True)

        with pytest.raises(AuthorizationError, match="entregaste"):
            e.guardar.execute(e.sesion.id, [e.eleccion()], actor=e.actor)

    def test_fuera_de_la_ventana_del_examen_no_se_responde(self) -> None:
        e = Escenario()
        e.guardar = SaveAnswers(
            e.respuestas,
            e.preguntas,
            e.participantes,
            e.sesiones,
            FixedClock(NOW + timedelta(days=1)),
        )

        with pytest.raises(AuthorizationError, match="no esta abierto"):
            e.guardar.execute(e.sesion.id, [e.eleccion()], actor=e.actor)

    def test_sin_autenticacion_usa_el_estudiante_de_desarrollo(self) -> None:
        # En local se recorre el flujo entero sin crear usuarios, pero con las
        # mismas comprobaciones: hace falta la matrícula del estudiante de
        # desarrollo.
        e = Escenario()
        e.participantes.save(
            SessionParticipant.enroll(
                session_id=e.sesion.id,
                student_id=DEFAULT_DEV_STUDENT_ID,
                consented_at=NOW,
            ).verified(NOW)
        )

        guardadas = e.guardar.execute(e.sesion.id, [e.eleccion()])

        assert len(guardadas) == 1


class TestListar:
    def test_devuelve_solo_lo_propio(self) -> None:
        e = Escenario()
        e.guardar.execute(e.sesion.id, [e.eleccion()], actor=e.actor)

        mias = e.listar.execute(e.sesion.id, actor=e.actor)

        assert len(mias) == 1
        assert mias[0].participant_id == e.participante.id

    def test_un_docente_no_las_lee_por_aqui(self) -> None:
        e = Escenario()
        docente = AuthenticatedUser(id=DOCENTE, role=UserRole.TEACHER)

        with pytest.raises(AuthorizationError):
            e.listar.execute(e.sesion.id, actor=docente)

    def test_sin_matricula_no_hay_nada_que_leer(self) -> None:
        e = Escenario()
        otro = AuthenticatedUser(id=uuid4(), role=UserRole.STUDENT)

        with pytest.raises(AuthorizationError, match="matriculado"):
            e.listar.execute(e.sesion.id, actor=otro)
