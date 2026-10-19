"""La pregunta de un evento tiene que ser de la misma sesion.

Sin esta regla, un cliente puede mandar el `question_id` de otro examen y el
servicio de IA acabaria comparando la transcripcion del estudiante con el
enunciado equivocado. La similitud saldria mal y la deteccion de IA por voz
daria un resultado sin sentido — justo lo que el proyecto mide como falso
positivo.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from proctoring_api.adapters.outbound.memory.alert_repository import InMemoryAlertRepository
from proctoring_api.adapters.outbound.memory.event_repository import InMemoryEventRepository
from proctoring_api.adapters.outbound.memory.job_queue import InMemoryJobQueue
from proctoring_api.adapters.outbound.memory.question_bank_repository import (
    InMemoryQuestionBankRepository,
)
from proctoring_api.adapters.outbound.memory.question_repository import (
    InMemoryQuestionRepository,
)
from proctoring_api.application.use_cases.register_event import (
    RegisterEvent,
    RegisterEventInput,
)
from proctoring_api.domain.errors import InvalidEventError
from proctoring_api.domain.event import EventType
from proctoring_api.domain.question import Question, QuestionType
from proctoring_api.domain.question_bank import QuestionBank

from tests.conftest import NOW, FixedClock

SESSION = uuid4()
OTHER_SESSION = uuid4()
STUDENT = uuid4()

QUESTION_OF_THIS_SESSION = uuid4()
QUESTION_OF_ANOTHER_SESSION = uuid4()
QUESTION_THAT_DOES_NOT_EXIST = uuid4()


def una_pregunta(session_id: UUID, question_id: UUID) -> Question:
    return Question.create(
        session_id=session_id,
        position=1,
        question_type=QuestionType.ESSAY,
        statement="Explica que es RLS",
        question_id=question_id,
    )


@pytest.fixture
def questions() -> InMemoryQuestionRepository:
    return InMemoryQuestionRepository(
        [
            una_pregunta(SESSION, QUESTION_OF_THIS_SESSION),
            una_pregunta(OTHER_SESSION, QUESTION_OF_ANOTHER_SESSION),
        ]
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


# --- Preguntas de banco -------------------------------------------------------
#
# **El fallo que dejo sin evidencia a todo examen armado desde un banco.** Estas
# preguntas tienen `session_id` nulo porque las comparte cualquier examen al que
# se asocie el banco. La regla daba por hecho que toda pregunta trae sesion, asi
# que resolvia a `None` y rechazaba cada senal con "la pregunta no existe": el
# docente se quedaba sin una sola alerta y sin una sola captura, y nada lo decia.

BANK_OF_THIS_SESSION = uuid4()
BANK_OF_NOBODY = uuid4()
QUESTION_FROM_OUR_BANK = uuid4()
QUESTION_FROM_ANOTHER_BANK = uuid4()


def una_pregunta_de_banco(bank_id: UUID, question_id: UUID) -> Question:
    return Question.create(
        bank_id=bank_id,
        position=1,
        question_type=QuestionType.ESSAY,
        statement="Explica que es RLS",
        question_id=question_id,
    )


@pytest.fixture
def banks() -> InMemoryQuestionBankRepository:
    repositorio = InMemoryQuestionBankRepository()
    repositorio.save(
        QuestionBank.create(
            teacher_id=uuid4(),
            name="Banco de prueba",
            created_at=NOW,
            bank_id=BANK_OF_THIS_SESSION,
        )
    )
    repositorio.attach_to_session(SESSION, BANK_OF_THIS_SESSION)
    return repositorio


@pytest.fixture
def use_case_with_banks(
    event_repository: InMemoryEventRepository,
    job_queue: InMemoryJobQueue,
    clock: FixedClock,
    alert_repository: InMemoryAlertRepository,
    banks: InMemoryQuestionBankRepository,
) -> RegisterEvent:
    questions = InMemoryQuestionRepository(
        [
            una_pregunta_de_banco(BANK_OF_THIS_SESSION, QUESTION_FROM_OUR_BANK),
            una_pregunta_de_banco(BANK_OF_NOBODY, QUESTION_FROM_ANOTHER_BANK),
        ]
    )
    return RegisterEvent(event_repository, job_queue, clock, alert_repository, questions, banks)


def test_accepts_a_question_from_a_bank_attached_to_the_session(
    use_case_with_banks: RegisterEvent,
) -> None:
    assert use_case_with_banks.execute(an_input(QUESTION_FROM_OUR_BANK)).id is not None


def test_rejects_a_question_from_a_bank_that_is_not_attached(
    use_case_with_banks: RegisterEvent, event_repository: InMemoryEventRepository
) -> None:
    # La regla original sigue en pie: no se puede mandar el enunciado de otro
    # examen, porque el servicio de IA compararia con el texto equivocado.
    with pytest.raises(InvalidEventError, match="no esta asociado"):
        use_case_with_banks.execute(an_input(QUESTION_FROM_ANOTHER_BANK))

    assert event_repository.list_by_session(SESSION) == []
