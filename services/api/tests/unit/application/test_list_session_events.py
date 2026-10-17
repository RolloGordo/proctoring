"""Caso de uso `ListSessionEvents`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from proctoring_api.adapters.outbound.memory.event_repository import InMemoryEventRepository
from proctoring_api.application.use_cases.list_session_events import ListSessionEvents
from proctoring_api.domain.event import EventType, ProctoringEvent

SESSION = uuid4()
OTHER_SESSION = uuid4()
ANA = uuid4()
LUIS = uuid4()
BASE = datetime(2026, 10, 3, 14, 0, 0, tzinfo=UTC)


def an_event(
    *, session_id: object = SESSION, student_id: object = ANA, minutes: int = 0
) -> ProctoringEvent:
    return ProctoringEvent.create(
        session_id=session_id,  # type: ignore[arg-type]
        student_id=student_id,  # type: ignore[arg-type]
        event_type=EventType.FOCUS_LOST,
        started_at=BASE + timedelta(minutes=minutes),
    )


@pytest.fixture
def use_case(event_repository: InMemoryEventRepository) -> ListSessionEvents:
    return ListSessionEvents(event_repository)


def test_returns_only_the_requested_session(
    use_case: ListSessionEvents, event_repository: InMemoryEventRepository
) -> None:
    event_repository.save(an_event())
    event_repository.save(an_event(session_id=OTHER_SESSION))

    result = use_case.execute(SESSION)

    assert len(result) == 1
    assert result[0].session_id == SESSION


def test_filters_by_student(
    use_case: ListSessionEvents, event_repository: InMemoryEventRepository
) -> None:
    event_repository.save(an_event(student_id=ANA))
    event_repository.save(an_event(student_id=LUIS))

    assert len(use_case.execute(SESSION)) == 2
    assert len(use_case.execute(SESSION, student_id=ANA)) == 1


def test_is_ordered_chronologically(
    use_case: ListSessionEvents, event_repository: InMemoryEventRepository
) -> None:
    # La pantalla de revision del docente es una linea de tiempo: el orden es
    # parte del contrato, no un detalle de la implementacion.
    event_repository.save(an_event(minutes=10))
    event_repository.save(an_event(minutes=0))
    event_repository.save(an_event(minutes=5))

    result = use_case.execute(SESSION)

    assert [event.started_at for event in result] == [
        BASE,
        BASE + timedelta(minutes=5),
        BASE + timedelta(minutes=10),
    ]


def test_returns_empty_for_an_unknown_session(use_case: ListSessionEvents) -> None:
    assert use_case.execute(uuid4()) == []
