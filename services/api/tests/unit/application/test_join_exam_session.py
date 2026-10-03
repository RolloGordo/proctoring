"""Entrada del estudiante con el código de acceso."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from proctoring_api.adapters.outbound.memory.exam_session_repository import (
    InMemoryExamSessionRepository,
)
from proctoring_api.application.use_cases.join_exam_session import (
    ExamSessionNotFoundError,
    JoinExamSession,
    normalise_access_code,
)
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.user import AuthenticatedUser, UserRole

from tests.conftest import NOW, FixedClock

ESTUDIANTE = AuthenticatedUser(id=uuid4(), role=UserRole.STUDENT)
DOCENTE = AuthenticatedUser(id=uuid4(), role=UserRole.TEACHER)


def una_sesion(*, empieza_en: timedelta = timedelta(0), tolerancia: int = 10) -> ExamSession:
    return ExamSession.create(
        teacher_id=DOCENTE.id,
        title="Parcial de Taller Integrador",
        starts_at=NOW + empieza_en,
        duration_minutes=90,
        entry_tolerance_minutes=tolerancia,
        access_code="KK8M5E",
    )


@pytest.fixture
def sessions() -> InMemoryExamSessionRepository:
    repositorio = InMemoryExamSessionRepository()
    repositorio.save(una_sesion())
    return repositorio


@pytest.fixture
def use_case(sessions: InMemoryExamSessionRepository, clock: FixedClock) -> JoinExamSession:
    return JoinExamSession(sessions, clock)


class TestNormalizacion:
    @pytest.mark.parametrize("escrito", ["KK8M5E", "kk8m5e", " KK8M5E ", "KK8-M5E", "kk 8m 5e"])
    def test_acepta_como_lo_teclee_el_estudiante(
        self, use_case: JoinExamSession, escrito: str
    ) -> None:
        # Lo lee de una pizarra o de un chat: llega con espacios, guiones y en
        # cualquier caja. Rechazarlo por eso sería hacerle perder el examen.
        assert use_case.execute(escrito, actor=ESTUDIANTE).session.access_code == "KK8M5E"

    def test_la_funcion_es_pura(self) -> None:
        assert normalise_access_code("  kk8-m5e ") == "KK8M5E"


class TestCodigoDesconocido:
    def test_un_codigo_inventado_no_existe(self, use_case: JoinExamSession) -> None:
        with pytest.raises(ExamSessionNotFoundError, match="ningún examen"):
            use_case.execute("ZZZZZZ", actor=ESTUDIANTE)

    def test_el_mensaje_no_distingue_entre_mal_escrito_y_ajeno(
        self, use_case: JoinExamSession
    ) -> None:
        # Un mensaje distinto permitiria tantear codigos hasta dar con uno valido.
        mensajes = []
        for codigo in ("AAAAAA", "BBBBBB"):
            try:
                use_case.execute(codigo, actor=ESTUDIANTE)
            except ExamSessionNotFoundError as fallo:
                mensajes.append(str(fallo))

        assert len(mensajes) == 2
        assert mensajes[0] == mensajes[1]
        # Y no filtra el codigo probado.
        assert "AAAAAA" not in mensajes[0]


class TestVentanaDeIngreso:
    def test_puede_entrar_cuando_el_examen_esta_abierto(self, use_case: JoinExamSession) -> None:
        assert use_case.execute("KK8M5E", actor=ESTUDIANTE).can_enter_now is True

    def test_todavia_no_ha_empezado(
        self, sessions: InMemoryExamSessionRepository, clock: FixedClock
    ) -> None:
        sessions.clear()
        sessions.save(una_sesion(empieza_en=timedelta(hours=2)))

        resultado = JoinExamSession(sessions, clock).execute("KK8M5E", actor=ESTUDIANTE)

        # Encuentra el examen y muestra la sala de espera, pero no deja entrar.
        assert resultado.can_enter_now is False
        assert resultado.opens_at > NOW

    def test_la_tolerancia_ya_vencio(
        self, sessions: InMemoryExamSessionRepository, clock: FixedClock
    ) -> None:
        sessions.clear()
        sessions.save(una_sesion(empieza_en=timedelta(minutes=-30), tolerancia=10))

        assert (
            JoinExamSession(sessions, clock).execute("KK8M5E", actor=ESTUDIANTE).can_enter_now
            is False
        )


class TestAutorizacion:
    def test_un_docente_no_entra_por_codigo(self, use_case: JoinExamSession) -> None:
        with pytest.raises(AuthorizationError, match="desde su panel"):
            use_case.execute("KK8M5E", actor=DOCENTE)

    def test_sin_actor_funciona(self, use_case: JoinExamSession) -> None:
        # Modo sin autenticación, que solo se permite en local y en pruebas.
        assert use_case.execute("KK8M5E").session.access_code == "KK8M5E"
