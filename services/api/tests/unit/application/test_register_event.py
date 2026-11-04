"""Caso de uso `RegisterEvent`, con adaptadores en memoria."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

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
from proctoring_api.domain.errors import InvalidEventError
from proctoring_api.domain.event import EventType
from proctoring_api.domain.exam_session import (
    ExamSession,
    SupervisionModule,
    SupervisionPreset,
    UnwatchedSignalError,
)
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
            an_input(
                event_type=EventType.SPEECH_DETECTED,
                question_id=QUESTION,
                evidence_path="session/student/audio.webm",
            )
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


class CountingSessions(InMemoryExamSessionRepository):
    """Cuenta las lecturas, para comprobar la memoria de un minuto."""

    def __init__(self) -> None:
        super().__init__()
        self.reads = 0

    def find_by_id(self, session_id: UUID) -> ExamSession | None:
        self.reads += 1
        return super().find_by_id(session_id)


class TestWhatTheTeacherTurnedOff:
    """Un examen personalizado no registra lo que el docente no activo."""

    @pytest.fixture
    def sessions(self) -> CountingSessions:
        return CountingSessions()

    @pytest.fixture
    def guarded(
        self,
        event_repository: InMemoryEventRepository,
        job_queue: InMemoryJobQueue,
        clock: FixedClock,
        alert_repository: InMemoryAlertRepository,
        sessions: CountingSessions,
    ) -> RegisterEvent:
        return RegisterEvent(
            event_repository, job_queue, clock, alert_repository, sessions=sessions
        )

    @staticmethod
    def a_session(
        sessions: InMemoryExamSessionRepository,
        preset: SupervisionPreset,
        modules: dict[SupervisionModule, dict[str, object]] | None = None,
    ) -> ExamSession:
        session = ExamSession.create(
            teacher_id=uuid4(),
            title="Parcial",
            starts_at=NOW,
            duration_minutes=60,
            preset=preset,
            modules=modules,
        )
        sessions.save(session)
        return session

    def test_a_signal_of_a_module_turned_off_is_not_stored(
        self,
        guarded: RegisterEvent,
        sessions: CountingSessions,
        event_repository: InMemoryEventRepository,
        alert_repository: InMemoryAlertRepository,
    ) -> None:
        session = self.a_session(
            sessions, SupervisionPreset.CUSTOM, {SupervisionModule.FOCUS_LOSS: {}}
        )

        with pytest.raises(UnwatchedSignalError):
            guarded.execute(
                an_input(session_id=session.id, event_type=EventType.SUSPICIOUS_PROCESS)
            )

        assert list(event_repository.list_by_session(session.id)) == []
        assert list(alert_repository.list_by_session(session.id)) == []

    def test_a_signal_of_a_module_turned_on_is_stored(
        self,
        guarded: RegisterEvent,
        sessions: CountingSessions,
        event_repository: InMemoryEventRepository,
    ) -> None:
        session = self.a_session(
            sessions, SupervisionPreset.CUSTOM, {SupervisionModule.FOCUS_LOSS: {}}
        )

        guarded.execute(an_input(session_id=session.id, duration_ms=8_000))

        assert len(event_repository.list_by_session(session.id)) == 1

    def test_presets_keep_registering_the_desktop_signals(
        self,
        guarded: RegisterEvent,
        sessions: CountingSessions,
        event_repository: InMemoryEventRepository,
    ) -> None:
        # `standard` no tiene `screen_capture` y aun asi tiene que avisar de
        # AnyDesk, como antes.
        session = self.a_session(sessions, SupervisionPreset.STANDARD)

        guarded.execute(an_input(session_id=session.id, event_type=EventType.SUSPICIOUS_PROCESS))

        assert len(event_repository.list_by_session(session.id)) == 1

    def test_the_session_is_read_once_a_minute_at_most(
        self, guarded: RegisterEvent, sessions: CountingSessions
    ) -> None:
        session = self.a_session(
            sessions, SupervisionPreset.CUSTOM, {SupervisionModule.FOCUS_LOSS: {}}
        )

        for _ in range(5):
            guarded.execute(an_input(session_id=session.id))

        assert sessions.reads == 1
