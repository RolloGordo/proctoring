"""Un docente solo accede a las sesiones que el creo.

Sin esta regla, cualquier docente del sistema puede leer la evidencia y las
alertas de los examenes de sus colegas con solo conocer un `session_id`. Es
informacion sobre estudiantes concretos y sobre decisiones academicas ajenas.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from proctoring_api.adapters.outbound.memory.alert_repository import InMemoryAlertRepository
from proctoring_api.adapters.outbound.memory.event_repository import InMemoryEventRepository
from proctoring_api.adapters.outbound.memory.exam_session_repository import (
    InMemoryExamSessionRepository,
)
from proctoring_api.application.use_cases.list_session_alerts import ListSessionAlerts
from proctoring_api.application.use_cases.list_session_events import ListSessionEvents
from proctoring_api.domain.alert import Alert
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.event import EventType, ProctoringEvent
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.severity import Severity
from proctoring_api.domain.user import AuthenticatedUser, UserRole

MY_SESSION = uuid4()
SOMEONE_ELSES_SESSION = uuid4()
UNKNOWN_SESSION = uuid4()

ME = AuthenticatedUser(id=uuid4(), role=UserRole.TEACHER)
ANOTHER_TEACHER = AuthenticatedUser(id=uuid4(), role=UserRole.TEACHER)
STUDENT = AuthenticatedUser(id=uuid4(), role=UserRole.STUDENT)

NOW = datetime(2026, 10, 3, 15, 0, 0, tzinfo=UTC)


def a_session(session_id: UUID, teacher_id: UUID) -> ExamSession:
    return ExamSession.create(
        teacher_id=teacher_id,
        title="Examen parcial",
        starts_at=NOW,
        duration_minutes=60,
        session_id=session_id,
    )


@pytest.fixture
def sessions() -> InMemoryExamSessionRepository:
    repository = InMemoryExamSessionRepository()
    repository.save(a_session(MY_SESSION, ME.id))
    repository.save(a_session(SOMEONE_ELSES_SESSION, ANOTHER_TEACHER.id))
    return repository


@pytest.fixture
def events(event_repository: InMemoryEventRepository) -> InMemoryEventRepository:
    for session_id in (MY_SESSION, SOMEONE_ELSES_SESSION):
        event_repository.save(
            ProctoringEvent.create(
                session_id=session_id,
                student_id=STUDENT.id,
                event_type=EventType.FOCUS_LOST,
                started_at=NOW,
            )
        )
    return event_repository


@pytest.fixture
def alerts(alert_repository: InMemoryAlertRepository) -> InMemoryAlertRepository:
    for session_id in (MY_SESSION, SOMEONE_ELSES_SESSION):
        alert_repository.save(
            Alert(
                id=uuid4(),
                event_id=uuid4(),
                session_id=session_id,
                student_id=STUDENT.id,
                severity=Severity.HIGH,
                reason="Se detecto a otra persona en camara",
                created_at=NOW,
            )
        )
    return alert_repository


class TestListingEvents:
    @pytest.fixture
    def use_case(
        self, events: InMemoryEventRepository, sessions: InMemoryExamSessionRepository
    ) -> ListSessionEvents:
        return ListSessionEvents(events, sessions)

    def test_a_teacher_reads_their_own_session(self, use_case: ListSessionEvents) -> None:
        assert len(use_case.execute(MY_SESSION, actor=ME)) == 1

    def test_a_teacher_cannot_read_a_colleagues_session(self, use_case: ListSessionEvents) -> None:
        with pytest.raises(AuthorizationError, match="acceso a esta sesion"):
            use_case.execute(SOMEONE_ELSES_SESSION, actor=ME)

    def test_an_unknown_session_answers_the_same(self, use_case: ListSessionEvents) -> None:
        # Mismo error que una sesion ajena: distinguirlos permitiria averiguar
        # que sesiones existen.
        with pytest.raises(AuthorizationError, match="acceso a esta sesion"):
            use_case.execute(UNKNOWN_SESSION, actor=ME)

    def test_students_are_unaffected(self, use_case: ListSessionEvents) -> None:
        # Al estudiante lo limita el filtro por su propio id, no la propiedad de
        # la sesion: no es dueno de ninguna.
        assert len(use_case.execute(SOMEONE_ELSES_SESSION, actor=STUDENT)) == 1

    def test_without_a_session_repository_nothing_is_checked(
        self, events: InMemoryEventRepository
    ) -> None:
        # Modo memoria: no hay sesiones creadas con las que comprobar.
        assert len(ListSessionEvents(events, None).execute(MY_SESSION, actor=ME)) == 1


class TestListingAlerts:
    @pytest.fixture
    def use_case(
        self, alerts: InMemoryAlertRepository, sessions: InMemoryExamSessionRepository
    ) -> ListSessionAlerts:
        return ListSessionAlerts(alerts, sessions)

    def test_a_teacher_reads_their_own_session(self, use_case: ListSessionAlerts) -> None:
        assert len(use_case.execute(MY_SESSION, actor=ME)) == 1

    def test_a_teacher_cannot_read_a_colleagues_session(self, use_case: ListSessionAlerts) -> None:
        with pytest.raises(AuthorizationError, match="acceso a esta sesion"):
            use_case.execute(SOMEONE_ELSES_SESSION, actor=ME)

    def test_a_student_is_still_rejected_first(self, use_case: ListSessionAlerts) -> None:
        with pytest.raises(AuthorizationError, match="Solo el docente"):
            use_case.execute(MY_SESSION, actor=STUDENT)
