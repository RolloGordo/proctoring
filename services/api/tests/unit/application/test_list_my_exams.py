"""El panel del estudiante: sus examenes, y solo los suyos."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from proctoring_api.adapters.outbound.memory.exam_session_repository import (
    InMemoryExamSessionRepository,
)
from proctoring_api.adapters.outbound.memory.participant_repository import (
    InMemoryParticipantRepository,
)
from proctoring_api.application.use_cases.list_my_exams import ListMyExams
from proctoring_api.application.use_cases.manage_enrollment import DEFAULT_DEV_STUDENT_ID
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.participant import SessionParticipant
from proctoring_api.domain.user import AuthenticatedUser, UserRole

NOW = datetime(2026, 10, 5, 15, 0, tzinfo=UTC)
ESTUDIANTE = UUID("7b2e4d10-5c6f-4a8b-9d0e-2f3a4b5c6d71")
OTRO = UUID("1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d")
DOCENTE = UUID("0f9e8d7c-6b5a-4938-8271-6a5b4c3d2e1f")


class FixedClock:
    def now(self) -> datetime:
        return NOW


class Escenario:
    def __init__(self) -> None:
        self.sesiones = InMemoryExamSessionRepository()
        self.participantes = InMemoryParticipantRepository()
        self.caso = ListMyExams(self.participantes, self.sesiones, FixedClock())

    def sesion(self, titulo: str, empieza: timedelta) -> ExamSession:
        sesion = ExamSession.create(
            teacher_id=DOCENTE,
            title=titulo,
            starts_at=NOW + empieza,
            duration_minutes=60,
        )
        self.sesiones.save(sesion)
        return sesion

    def matricular(
        self, sesion: ExamSession, quien: UUID = ESTUDIANTE, *, entregado: bool = False
    ) -> SessionParticipant:
        participante = SessionParticipant.enroll(
            session_id=sesion.id, student_id=quien, consented_at=NOW
        ).verified(NOW)
        if entregado:
            participante = participante.submitted(NOW)
        self.participantes.save(participante)
        return participante

    @property
    def actor(self) -> AuthenticatedUser:
        return AuthenticatedUser(id=ESTUDIANTE, role=UserRole.STUDENT)


def test_sin_matriculas_devuelve_una_lista_vacia() -> None:
    e = Escenario()

    assert e.caso.execute(actor=e.actor) == []


def test_devuelve_solo_los_examenes_del_estudiante() -> None:
    # La matricula de otro estudiante en otro examen no puede aparecer aqui.
    e = Escenario()
    mio = e.sesion("Mio", timedelta(minutes=-5))
    ajeno = e.sesion("Ajeno", timedelta(minutes=-5))
    e.matricular(mio)
    e.matricular(ajeno, OTRO)

    resultado = e.caso.execute(actor=e.actor)

    assert [x.session.title for x in resultado] == ["Mio"]


def test_del_mas_reciente_al_mas_antiguo() -> None:
    e = Escenario()
    for titulo, desfase in [("Viejo", timedelta(days=-10)), ("Nuevo", timedelta(days=3))]:
        e.matricular(e.sesion(titulo, desfase))

    assert [x.session.title for x in e.caso.execute(actor=e.actor)] == ["Nuevo", "Viejo"]


def test_puede_entrar_hoy_si_esta_en_su_ventana() -> None:
    e = Escenario()
    abierto = e.sesion("Abierto", timedelta(minutes=-5))
    futuro = e.sesion("Futuro", timedelta(days=1))
    e.matricular(abierto)
    e.matricular(futuro)

    por_titulo = {x.session.title: x.can_enter_now for x in e.caso.execute(actor=e.actor)}

    assert por_titulo == {"Abierto": True, "Futuro": False}


def test_quien_ya_esta_dentro_sigue_pasada_la_tolerancia() -> None:
    # La tolerancia (10 min por defecto) es para entrar por primera vez. A quien
    # ya esta matriculado no se le cierra la puerta a los 15 minutos por haber
    # reiniciado el equipo.
    e = Escenario()
    e.matricular(e.sesion("En marcha", timedelta(minutes=-30)))

    [examen] = e.caso.execute(actor=e.actor)

    assert examen.can_enter_now is True


def test_pasada_la_duracion_ya_no_puede_entrar() -> None:
    e = Escenario()
    e.matricular(e.sesion("Terminado", timedelta(hours=-3)))

    [examen] = e.caso.execute(actor=e.actor)

    assert examen.can_enter_now is False


def test_uno_ya_entregado_no_puede_volver_a_entrar() -> None:
    e = Escenario()
    e.matricular(e.sesion("Hecho", timedelta(minutes=-5)), entregado=True)

    [examen] = e.caso.execute(actor=e.actor)

    assert examen.can_enter_now is False
    assert examen.participant.submitted_at is not None


def test_una_matricula_sin_sesion_se_omite_en_vez_de_romper_el_panel() -> None:
    e = Escenario()
    e.matricular(e.sesion("Existe", timedelta(minutes=-5)))
    huerfana = SessionParticipant.enroll(
        session_id=uuid4(), student_id=ESTUDIANTE, consented_at=NOW
    )
    e.participantes.save(huerfana)

    assert [x.session.title for x in e.caso.execute(actor=e.actor)] == ["Existe"]


def test_un_docente_no_usa_este_panel() -> None:
    e = Escenario()
    docente = AuthenticatedUser(id=DOCENTE, role=UserRole.TEACHER)

    with pytest.raises(AuthorizationError):
        e.caso.execute(actor=docente)


def test_sin_autenticacion_usa_el_estudiante_de_desarrollo() -> None:
    e = Escenario()
    e.matricular(e.sesion("Dev", timedelta(minutes=-5)), DEFAULT_DEV_STUDENT_ID)

    assert [x.session.title for x in e.caso.execute()] == ["Dev"]
