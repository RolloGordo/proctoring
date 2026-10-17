"""Que un evento genere (o no) una alerta al docente.

Guardar una alerta **es** notificar: la tabla `alerts` esta publicada en Supabase
Realtime, asi que la insercion llega sola al navegador del docente (ADR-0007).
Estas pruebas son lo que sostiene la meta de avisar en menos de 5 s.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from proctoring_api.adapters.outbound.memory.alert_repository import InMemoryAlertRepository
from proctoring_api.adapters.outbound.memory.event_repository import InMemoryEventRepository
from proctoring_api.adapters.outbound.memory.job_queue import InMemoryJobQueue
from proctoring_api.application.use_cases.register_event import (
    RegisterEvent,
    RegisterEventInput,
)
from proctoring_api.domain.event import EventType
from proctoring_api.domain.severity import Severity

from tests.conftest import NOW, FixedClock

SESSION = uuid4()
STUDENT = uuid4()
QUESTION = uuid4()


@pytest.fixture
def use_case(
    event_repository: InMemoryEventRepository,
    job_queue: InMemoryJobQueue,
    clock: FixedClock,
    alert_repository: InMemoryAlertRepository,
) -> RegisterEvent:
    return RegisterEvent(event_repository, job_queue, clock, alert_repository)


def an_input(event_type: EventType, duration_ms: int = 0, **extra: object) -> RegisterEventInput:
    return RegisterEventInput(
        session_id=SESSION,
        student_id=STUDENT,
        event_type=event_type,
        started_at=NOW - timedelta(minutes=1),
        duration_ms=duration_ms,
        **extra,  # type: ignore[arg-type]
    )


class TestAlertIsCreated:
    def test_high_severity_creates_an_alert(
        self, use_case: RegisterEvent, alert_repository: InMemoryAlertRepository
    ) -> None:
        result = use_case.execute(an_input(EventType.EXTRA_PERSON))

        alerts = alert_repository.list_by_session(SESSION)
        assert len(alerts) == 1
        assert alerts[0].event_id == result.id
        assert alerts[0].severity is Severity.HIGH
        assert alerts[0].reason == "Se detecto a otra persona en camara"

    def test_medium_severity_creates_an_alert(
        self, use_case: RegisterEvent, alert_repository: InMemoryAlertRepository
    ) -> None:
        use_case.execute(an_input(EventType.FOCUS_LOST, duration_ms=8_400))

        alerts = alert_repository.list_by_session(SESSION)
        assert len(alerts) == 1
        assert alerts[0].severity is Severity.MEDIUM

    def test_the_alert_carries_session_and_student(
        self, use_case: RegisterEvent, alert_repository: InMemoryAlertRepository
    ) -> None:
        # La web del docente se suscribe a Realtime filtrando por session_id: sin
        # esa columna en la fila, el aviso no le llegaria.
        use_case.execute(an_input(EventType.EXTRA_DISPLAY))

        alert = alert_repository.list_by_session(SESSION)[0]
        assert alert.session_id == SESSION
        assert alert.student_id == STUDENT
        assert alert.created_at == NOW


class TestAlertIsNotCreated:
    def test_low_severity_does_not_alert(
        self, use_case: RegisterEvent, alert_repository: InMemoryAlertRepository
    ) -> None:
        use_case.execute(an_input(EventType.FOCUS_LOST, duration_ms=500))

        assert alert_repository.list_by_session(SESSION) == []

    def test_speech_detected_does_not_alert_on_its_own(
        self, use_case: RegisterEvent, alert_repository: InMemoryAlertRepository
    ) -> None:
        """El caso que define el diferencial del proyecto.

        Hablar en voz alta no es trampa. La alerta por consulta a un asistente de
        IA la crea `services/ai` cuando confirma las **dos** condiciones. Alertar
        aqui seria acusar a quien lee la pregunta en voz alta para concentrarse.
        """
        use_case.execute(an_input(EventType.SPEECH_DETECTED, 5_600, question_id=QUESTION))

        assert alert_repository.list_by_session(SESSION) == []

    def test_a_rejected_event_leaves_no_alert(
        self, use_case: RegisterEvent, alert_repository: InMemoryAlertRepository
    ) -> None:
        from proctoring_api.domain.errors import InvalidEventError

        with pytest.raises(InvalidEventError):
            use_case.execute(an_input(EventType.EXTRA_PERSON, duration_ms=-1))

        assert alert_repository.list_by_session(SESSION) == []


def test_alerts_come_back_newest_first(
    use_case: RegisterEvent, alert_repository: InMemoryAlertRepository
) -> None:
    for _ in range(3):
        use_case.execute(an_input(EventType.EXTRA_PERSON))

    alerts = alert_repository.list_by_session(SESSION)
    assert len(alerts) == 3
    assert [a.created_at for a in alerts] == sorted([a.created_at for a in alerts], reverse=True)
