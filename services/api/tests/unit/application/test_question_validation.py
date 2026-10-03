"""La pregunta de un evento tiene que ser de la misma sesion.

Sin esta regla, un cliente puede mandar el `question_id` de otro examen y el
servicio de IA acabaria comparando la transcripcion del estudiante con el
enunciado equivocado. La similitud saldria mal y la deteccion de IA por voz
daria un resultado sin sentido — justo lo que el proyecto mide como falso
positivo.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from proctoring_api.adapters.outbound.memory.alert_repository import InMemoryAlertRepository
from proctoring_api.adapters.outbound.memory.event_repository import InMemoryEventRepository
from proctoring_api.adapters.outbound.memory.job_queue import InMemoryJobQueue
from proctoring_api.adapters.outbound.memory.question_repository import (
    InMemoryQuestionRepository,
)
from proctoring_api.application.use_cases.register_event import (
    RegisterEvent,
    RegisterEventInput,
)
from proctoring_api.domain.errors import InvalidEventError
from proctoring_api.domain.event import EventType

from tests.conftest import NOW, FixedClock

SESSION = uuid4()
OTHER_SESSION = uuid4()
STUDENT = uuid4()

QUESTION_OF_THIS_SESSION = uuid4()
QUESTION_OF_ANOTHER_SESSION = uuid4()
QUESTION_THAT_DOES_NOT_EXIST = uuid4()


@pytest.fixture
def questions() -> InMemoryQuestionRepository:
    return InMemoryQuestionRepository(
        {
            QUESTION_OF_THIS_SESSION: SESSION,
            QUESTION_OF_ANOTHER_SESSION: OTHER_SESSION,
        }
    )


@pytest.fixture
def use_case(
    event_repository: InMemoryEventRepository,
    job_queue: InMemoryJobQueue,
    clock: FixedClock,
    alert_repository: InMemoryAlertRepository,
    questions: InMemoryQuestionRepository,
) -> RegisterEvent:
    return RegisterEvent(event_repository, job_queue, clock, alert_repository, questions)


def an_input(question_id: object) -> RegisterEventInput:
    return RegisterEventInput(
        session_id=SESSION,
        student_id=STUDENT,
        event_type=EventType.GAZE_AWAY,
        started_at=NOW - timedelta(minutes=1),
        question_id=question_id,  # type: ignore[arg-type]
        duration_ms=4_200,
    )


def test_accepts_a_question_of_the_same_session(use_case: RegisterEvent) -> None:
    assert use_case.execute(an_input(QUESTION_OF_THIS_SESSION)).id is not None


def test_rejects_a_question_from_another_session(
    use_case: RegisterEvent, event_repository: InMemoryEventRepository
) -> None:
    with pytest.raises(InvalidEventError, match="no pertenece a la sesion"):
        use_case.execute(an_input(QUESTION_OF_ANOTHER_SESSION))

    assert event_repository.list_by_session(SESSION) == []


def test_rejects_a_question_that_does_not_exist(use_case: RegisterEvent) -> None:
    with pytest.raises(InvalidEventError, match="no existe"):
        use_case.execute(an_input(QUESTION_THAT_DOES_NOT_EXIST))


def test_events_without_question_are_unaffected(
    use_case: RegisterEvent,
) -> None:
    payload = RegisterEventInput(
        session_id=SESSION,
        student_id=STUDENT,
        event_type=EventType.FOCUS_LOST,
        started_at=NOW - timedelta(minutes=1),
    )

    assert use_case.execute(payload).id is not None


def test_without_a_question_repository_nothing_is_checked(
    event_repository: InMemoryEventRepository,
    job_queue: InMemoryJobQueue,
    clock: FixedClock,
    alert_repository: InMemoryAlertRepository,
) -> None:
    """Modo memoria: no hay banco de preguntas contra el que comprobar.

    La composicion de `main.py` no cablea repositorio de preguntas cuando
    `EVENT_REPOSITORY=memory`, para que Rider y Jesus puedan mandar `gaze_away` y
    `speech_detected` antes de que exista un examen de verdad.
    """
    use_case = RegisterEvent(event_repository, job_queue, clock, alert_repository, None)

    assert use_case.execute(an_input(QUESTION_THAT_DOES_NOT_EXIST)).id is not None
