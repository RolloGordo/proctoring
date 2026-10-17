"""Reglas de autorizacion de los casos de uso.

Estas reglas **no las cubre la base de datos**. RLS protege las escrituras
directas desde el cliente, pero la API usa la service role key y omite RLS por
completo, asi que esto es lo unico que separa a un estudiante de fabricar
evidencia contra otro.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from proctoring_api.adapters.outbound.memory.alert_repository import InMemoryAlertRepository
from proctoring_api.adapters.outbound.memory.event_repository import InMemoryEventRepository
from proctoring_api.adapters.outbound.memory.job_queue import InMemoryJobQueue
from proctoring_api.application.use_cases.list_session_events import ListSessionEvents
from proctoring_api.application.use_cases.register_event import (
    RegisterEvent,
    RegisterEventInput,
)
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.event import EventType, ProctoringEvent
from proctoring_api.domain.user import AuthenticatedUser, UserRole

from tests.conftest import NOW, FixedClock

SESSION = uuid4()
ANA = AuthenticatedUser(id=uuid4(), role=UserRole.STUDENT)
LUIS = AuthenticatedUser(id=uuid4(), role=UserRole.STUDENT)
DOCENTE = AuthenticatedUser(id=uuid4(), role=UserRole.TEACHER)


def an_input(student_id: object) -> RegisterEventInput:
    return RegisterEventInput(
        session_id=SESSION,
        student_id=student_id,  # type: ignore[arg-type]
        event_type=EventType.FOCUS_LOST,
        started_at=NOW - timedelta(minutes=1),
    )


@pytest.fixture
def register(
    event_repository: InMemoryEventRepository,
    job_queue: InMemoryJobQueue,
    clock: FixedClock,
    alert_repository: InMemoryAlertRepository,
) -> RegisterEvent:
    return RegisterEvent(event_repository, job_queue, clock, alert_repository)


class TestRegisterEvent:
    def test_a_student_can_report_about_themselves(self, register: RegisterEvent) -> None:
        result = register.execute(an_input(ANA.id), actor=ANA)
        assert result.id is not None

    def test_a_student_cannot_report_about_another(
        self, register: RegisterEvent, event_repository: InMemoryEventRepository
    ) -> None:
        # Sin esto, cualquiera con un token valido podria fabricar evidencia que
        # termina delante de un docente que decide sobre una nota.
        with pytest.raises(AuthorizationError, match="otro estudiante"):
            register.execute(an_input(LUIS.id), actor=ANA)

        assert event_repository.list_by_session(SESSION) == []

    def test_a_teacher_cannot_register_events(self, register: RegisterEvent) -> None:
        with pytest.raises(AuthorizationError, match="docente"):
            register.execute(an_input(ANA.id), actor=DOCENTE)

    def test_without_actor_nothing_is_checked(self, register: RegisterEvent) -> None:
        # actor=None es el modo sin autenticacion, que solo se permite en local.
        assert register.execute(an_input(LUIS.id), actor=None).id is not None


class TestListSessionEvents:
    @pytest.fixture
    def listing(self, event_repository: InMemoryEventRepository) -> ListSessionEvents:
        for student_id in (ANA.id, LUIS.id):
            event_repository.save(
                ProctoringEvent.create(
                    session_id=SESSION,
                    student_id=student_id,
                    event_type=EventType.FOCUS_LOST,
                    started_at=NOW,
                )
            )
        return ListSessionEvents(event_repository)

    def test_a_student_only_sees_their_own(self, listing: ListSessionEvents) -> None:
        result = listing.execute(SESSION, actor=ANA)

        assert len(result) == 1
        assert result[0].student_id == ANA.id

    def test_a_student_cannot_ask_for_someone_elses(self, listing: ListSessionEvents) -> None:
        # Pide los de Luis explicitamente y recibe los suyos: el filtro se ignora.
        result = listing.execute(SESSION, actor=ANA, student_id=LUIS.id)

        assert len(result) == 1
        assert result[0].student_id == ANA.id

    def test_a_teacher_sees_the_whole_session(self, listing: ListSessionEvents) -> None:
        assert len(listing.execute(SESSION, actor=DOCENTE)) == 2

    def test_a_teacher_can_filter_by_student(self, listing: ListSessionEvents) -> None:
        result = listing.execute(SESSION, actor=DOCENTE, student_id=LUIS.id)

        assert len(result) == 1
        assert result[0].student_id == LUIS.id
