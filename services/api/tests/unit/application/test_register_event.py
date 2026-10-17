"""Caso de uso `RegisterEvent`, con adaptadores en memoria."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from proctoring_api.adapters.outbound.memory.alert_repository import InMemoryAlertRepository
from proctoring_api.adapters.outbound.memory.event_repository import InMemoryEventRepository
from proctoring_api.adapters.outbound.memory.job_queue import InMemoryJobQueue
from proctoring_api.application.use_cases.register_event import (
    RegisterEvent,
    RegisterEventInput,
)
from proctoring_api.domain.errors import InvalidEventError
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


def an_input(**overrides: object) -> RegisterEventInput:
    kwargs: dict[str, object] = {
        "session_id": SESSION,
        "student_id": STUDENT,
        "event_type": EventType.FOCUS_LOST,
        "started_at": NOW - timedelta(minutes=1),
    }
    kwargs.update(overrides)
    return RegisterEventInput(**kwargs)  # type: ignore[arg-type]


class TestPersistence:
    def test_saves_the_event(
        self, use_case: RegisterEvent, event_repository: InMemoryEventRepository
    ) -> None:
        result = use_case.execute(an_input(duration_ms=8_400))

        stored = event_repository.list_by_session(SESSION)
        assert len(stored) == 1
        assert stored[0].id == result.id
        assert stored[0].duration_ms == 8_400

    def test_returns_the_default_severity(self, use_case: RegisterEvent) -> None:
        assert use_case.execute(an_input(duration_ms=8_400)).severity is Severity.MEDIUM
        assert use_case.execute(an_input(duration_ms=100)).severity is Severity.LOW


class TestAudioAnalysisQueue:
    def test_speech_detected_is_enqueued(
        self, use_case: RegisterEvent, job_queue: InMemoryJobQueue
    ) -> None:
        result = use_case.execute(
            an_input(event_type=EventType.SPEECH_DETECTED, question_id=QUESTION)
        )

        assert list(job_queue.audio_analysis_jobs) == [result.id]

    @pytest.mark.parametrize(
        "event_type",
        [
            EventType.FOCUS_LOST,
            EventType.FACE_ABSENT,
            EventType.EXTRA_PERSON,
            EventType.EXTRA_DISPLAY,
            EventType.SUSPICIOUS_PROCESS,
            EventType.IDENTITY_CHECK,
        ],
    )
    def test_nothing_else_is_enqueued(
        self,
        use_case: RegisterEvent,
        job_queue: InMemoryJobQueue,
        event_type: EventType,
    ) -> None:
        # Encolar de mas significa gastar CPU del servicio de IA en audio que no
        # existe: cada trabajo inutil come presupuesto del plan gratuito.
        use_case.execute(an_input(event_type=event_type))

        assert list(job_queue.audio_analysis_jobs) == []

    def test_is_not_enqueued_when_saving_fails(
        self,
        job_queue: InMemoryJobQueue,
        clock: FixedClock,
        alert_repository: InMemoryAlertRepository,
    ) -> None:
        class FailingRepository:
            def save(self, event: object) -> None:
                raise RuntimeError("base de datos caida")

            def list_by_session(self, *args: object, **kwargs: object) -> list[object]:
                return []

        use_case = RegisterEvent(
            FailingRepository(),  # type: ignore[arg-type]
            job_queue,
            clock,
            alert_repository,
        )

        with pytest.raises(RuntimeError):
            use_case.execute(an_input(event_type=EventType.SPEECH_DETECTED, question_id=QUESTION))

        # Si se encolara antes de guardar, el worker buscaria un evento inexistente.
        assert list(job_queue.audio_analysis_jobs) == []


class TestDomainRules:
    def test_rejects_speech_detected_without_question(self, use_case: RegisterEvent) -> None:
        with pytest.raises(InvalidEventError, match="question_id"):
            use_case.execute(an_input(event_type=EventType.SPEECH_DETECTED))

    def test_rejects_negative_duration(self, use_case: RegisterEvent) -> None:
        with pytest.raises(InvalidEventError, match="duration_ms"):
            use_case.execute(an_input(duration_ms=-5))

    def test_rejects_naive_started_at(self, use_case: RegisterEvent) -> None:
        with pytest.raises(InvalidEventError, match="zona horaria"):
            use_case.execute(an_input(started_at=datetime(2026, 10, 3, 14, 0)))


class TestClockSkew:
    def test_accepts_events_from_the_past(self, use_case: RegisterEvent) -> None:
        # Un reintento tras quedarse sin red llega tarde a proposito.
        result = use_case.execute(an_input(started_at=NOW - timedelta(hours=2)))
        assert result.id is not None

    def test_accepts_small_clock_skew(self, use_case: RegisterEvent) -> None:
        result = use_case.execute(an_input(started_at=NOW + timedelta(minutes=4)))
        assert result.id is not None

    def test_rejects_events_far_in_the_future(self, use_case: RegisterEvent) -> None:
        # Una marca de tiempo futura romperia el orden cronologico de la evidencia,
        # que es justo lo que el docente revisa.
        with pytest.raises(InvalidEventError, match="futuro"):
            use_case.execute(an_input(started_at=NOW + timedelta(hours=1)))

    def test_does_not_save_a_rejected_event(
        self, use_case: RegisterEvent, event_repository: InMemoryEventRepository
    ) -> None:
        with pytest.raises(InvalidEventError):
            use_case.execute(an_input(started_at=NOW + timedelta(days=1)))

        assert event_repository.list_by_session(SESSION) == []


def test_normalises_started_at_to_utc(
    use_case: RegisterEvent, event_repository: InMemoryEventRepository
) -> None:
    lima = timedelta(hours=-5)
    started_at = datetime(2026, 10, 3, 9, 0, 0, tzinfo=UTC) + lima

    use_case.execute(an_input(started_at=started_at))

    stored = event_repository.list_by_session(SESSION)[0]
    assert stored.started_at.utcoffset() == timedelta(0)
