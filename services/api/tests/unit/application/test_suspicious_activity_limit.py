"""Tope de actividades sospechosas (reunión del 14/11/2026)."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from proctoring_api.adapters.outbound.memory.alert_repository import InMemoryAlertRepository
from proctoring_api.adapters.outbound.memory.event_repository import InMemoryEventRepository
from proctoring_api.adapters.outbound.memory.exam_session_repository import (
    InMemoryExamSessionRepository,
)
from proctoring_api.adapters.outbound.memory.job_queue import InMemoryJobQueue
from proctoring_api.application.use_cases.register_event import (
    RegisterEvent,
    RegisterEventInput,
)
from proctoring_api.application.use_cases.review_case import ListSessionRisk
from proctoring_api.domain.alert import is_limit_alert
from proctoring_api.domain.event import EventType
from proctoring_api.domain.exam_session import (
    ExamSession,
    InvalidExamSessionError,
    SupervisionPreset,
)
from proctoring_api.domain.risk import RiskLevel

from tests.conftest import NOW, FixedClock

STUDENT = uuid4()
OTHER = uuid4()


def a_session(limit: int | None) -> ExamSession:
    return ExamSession.create(
        teacher_id=uuid4(),
        title="Parcial",
        starts_at=NOW,
        duration_minutes=60,
        preset=SupervisionPreset.STRICT,
        suspicious_activity_limit=limit,
    )


@pytest.fixture
def sessions() -> InMemoryExamSessionRepository:
    return InMemoryExamSessionRepository()


@pytest.fixture
def use_case(
    event_repository: InMemoryEventRepository,
    job_queue: InMemoryJobQueue,
    clock: FixedClock,
    alert_repository: InMemoryAlertRepository,
    sessions: InMemoryExamSessionRepository,
) -> RegisterEvent:
    return RegisterEvent(event_repository, job_queue, clock, alert_repository, sessions=sessions)


def proceso(session: ExamSession, student: object = STUDENT) -> RegisterEventInput:
    # Un proceso sospechoso siempre es alerta alta: cuenta como advertencia.
    return RegisterEventInput(
        session_id=session.id,
        student_id=student,  # type: ignore[arg-type]
        event_type=EventType.SUSPICIOUS_PROCESS,
        started_at=NOW - timedelta(seconds=5),
    )


class TestElTope:
    def test_cuenta_las_advertencias_y_avisa_una_sola_vez_al_llegar(
        self,
        use_case: RegisterEvent,
        sessions: InMemoryExamSessionRepository,
        alert_repository: InMemoryAlertRepository,
    ) -> None:
        sesion = a_session(3)
        sessions.save(sesion)

        salidas = [use_case.execute(proceso(sesion)) for _ in range(5)]

        assert [s.warnings for s in salidas] == [1, 2, 3, 4, 5]
        assert {s.warning_limit for s in salidas} == {3}
        avisos = [a for a in alert_repository.list_by_session(sesion.id) if is_limit_alert(a)]
        assert len(avisos) == 1
        assert "3 actividades sospechosas" in avisos[0].reason

    def test_las_senales_leves_no_cuentan(
        self, use_case: RegisterEvent, sessions: InMemoryExamSessionRepository
    ) -> None:
        sesion = a_session(2)
        sessions.save(sesion)
        leve = RegisterEventInput(
            session_id=sesion.id,
            student_id=STUDENT,
            event_type=EventType.FOCUS_LOST,
            started_at=NOW - timedelta(seconds=5),
            duration_ms=500,
        )

        salida = use_case.execute(leve)

        assert salida.warnings is None

    def test_sin_tope_no_cuenta_nada(
        self, use_case: RegisterEvent, sessions: InMemoryExamSessionRepository
    ) -> None:
        sesion = a_session(None)
        sessions.save(sesion)

        salida = use_case.execute(proceso(sesion))

        assert salida.warnings is None
        assert salida.warning_limit is None

    def test_rechaza_un_tope_fuera_de_rango(self) -> None:
        with pytest.raises(InvalidExamSessionError):
            a_session(0)
        with pytest.raises(InvalidExamSessionError):
            a_session(101)

    def test_se_puede_quitar_al_editar(self) -> None:
        sesion = a_session(5)
        assert sesion.with_changes(suspicious_activity_limit=8).suspicious_activity_limit == 8
        assert (
            sesion.with_changes(clear_suspicious_activity_limit=True).suspicious_activity_limit
            is None
        )
        assert sesion.with_changes(title="Otro").suspicious_activity_limit == 5


class TestElSemaforo:
    def test_quien_llega_al_tope_va_a_rojo_aunque_sus_puntos_no_alcancen(
        self,
        use_case: RegisterEvent,
        sessions: InMemoryExamSessionRepository,
        event_repository: InMemoryEventRepository,
        alert_repository: InMemoryAlertRepository,
    ) -> None:
        sesion = a_session(1)
        sessions.save(sesion)
        use_case.execute(proceso(sesion))

        riesgo = ListSessionRisk(event_repository, sessions, alert_repository).execute(sesion.id)

        assert riesgo[STUDENT].over_limit is True
        assert riesgo[STUDENT].warnings == 1
        assert riesgo[STUDENT].level is RiskLevel.HIGH
