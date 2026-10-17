"""Adaptadores de Supabase, con un cliente de mentira.

Hasta ahora estos cuatro adaptadores no tenian ni una prueba: podian estar rotos
y nos habriamos enterado en la demo. Lo que se comprueba aqui es nuestro codigo
—nombres de columna, filtros, orden, traduccion fila <-> entidad y las caches—,
no PostgreSQL.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest

from proctoring_api.adapters.outbound.supabase.alert_repository import SupabaseAlertRepository
from proctoring_api.adapters.outbound.supabase.event_repository import SupabaseEventRepository
from proctoring_api.adapters.outbound.supabase.profile_repository import (
    SupabaseProfileRepository,
)
from proctoring_api.adapters.outbound.supabase.question_repository import (
    SupabaseQuestionRepository,
)
from proctoring_api.domain.alert import Alert
from proctoring_api.domain.event import EventType, ProctoringEvent
from proctoring_api.domain.severity import Severity
from proctoring_api.domain.user import UserRole

from tests.doubles import FakeSupabaseClient

if TYPE_CHECKING:
    from supabase import Client

SESSION = UUID("3f1a7c20-9b4e-4d2a-8f6c-1e2d3a4b5c60")
STUDENT = UUID("7b2e4d10-5c6f-4a8b-9d0e-2f3a4b5c6d71")
OTHER_STUDENT = UUID("1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d")
QUESTION = UUID("a9c8b7d6-1e2f-4a3b-8c9d-0e1f2a3b4c82")
STARTED_AT = datetime(2026, 10, 3, 14, 21, 5, tzinfo=UTC)


def as_client(fake: FakeSupabaseClient) -> Client:
    return cast("Client", fake)


class TestEventRepository:
    @pytest.fixture
    def fake(self) -> FakeSupabaseClient:
        return FakeSupabaseClient({"events": []})

    @pytest.fixture
    def repository(self, fake: FakeSupabaseClient) -> SupabaseEventRepository:
        return SupabaseEventRepository(as_client(fake))

    def test_insert_uses_the_schema_column_names(
        self, repository: SupabaseEventRepository, fake: FakeSupabaseClient
    ) -> None:
        event = ProctoringEvent.create(
            session_id=SESSION,
            student_id=STUDENT,
            question_id=QUESTION,
            event_type=EventType.GAZE_AWAY,
            started_at=STARTED_AT,
            duration_ms=4_200,
            metadata={"yaw_deg": -31.4},
            evidence_path="a/b/c.jpg",
        )

        repository.save(event)

        row = fake.tables["events"].inserted[0]
        assert set(row) == {
            "id",
            "session_id",
            "student_id",
            "question_id",
            "event_type",
            "started_at",
            "duration_ms",
            "metadata",
            "evidence_path",
        }
        # Los uuid y el enum tienen que ir como texto, no como objetos de Python.
        assert row["session_id"] == str(SESSION)
        assert row["event_type"] == "gaze_away"
        assert row["metadata"] == {"yaw_deg": -31.4}

    def test_null_question_and_evidence_are_sent_as_null(
        self, repository: SupabaseEventRepository, fake: FakeSupabaseClient
    ) -> None:
        repository.save(
            ProctoringEvent.create(
                session_id=SESSION,
                student_id=STUDENT,
                event_type=EventType.FOCUS_LOST,
                started_at=STARTED_AT,
            )
        )

        row = fake.tables["events"].inserted[0]
        assert row["question_id"] is None
        assert row["evidence_path"] is None

    def test_round_trip(
        self, repository: SupabaseEventRepository, fake: FakeSupabaseClient
    ) -> None:
        original = ProctoringEvent.create(
            session_id=SESSION,
            student_id=STUDENT,
            question_id=QUESTION,
            event_type=EventType.SPEECH_DETECTED,
            started_at=STARTED_AT,
            duration_ms=5_600,
            metadata={"source": "silero_vad"},
            evidence_path="a/b/c.webm",
        )
        repository.save(original)

        [recovered] = repository.list_by_session(SESSION)

        assert recovered == original

    def test_filters_by_session_and_student(self, repository: SupabaseEventRepository) -> None:
        for student_id in (STUDENT, OTHER_STUDENT):
            repository.save(
                ProctoringEvent.create(
                    session_id=SESSION,
                    student_id=student_id,
                    event_type=EventType.FOCUS_LOST,
                    started_at=STARTED_AT,
                )
            )
        repository.save(
            ProctoringEvent.create(
                session_id=uuid4(),
                student_id=STUDENT,
                event_type=EventType.FOCUS_LOST,
                started_at=STARTED_AT,
            )
        )

        assert len(repository.list_by_session(SESSION)) == 2
        assert len(repository.list_by_session(SESSION, STUDENT)) == 1

    def test_ordered_by_started_at_ascending(self, repository: SupabaseEventRepository) -> None:
        for hour in (16, 14, 15):
            repository.save(
                ProctoringEvent.create(
                    session_id=SESSION,
                    student_id=STUDENT,
                    event_type=EventType.FOCUS_LOST,
                    started_at=STARTED_AT.replace(hour=hour),
                )
            )

        hours = [event.started_at.hour for event in repository.list_by_session(SESSION)]
        assert hours == [14, 15, 16]


class TestAlertRepository:
    @pytest.fixture
    def fake(self) -> FakeSupabaseClient:
        return FakeSupabaseClient({"alerts": []})

    @pytest.fixture
    def repository(self, fake: FakeSupabaseClient) -> SupabaseAlertRepository:
        return SupabaseAlertRepository(as_client(fake))

    def an_alert(self, minute: int = 0, severity: Severity = Severity.HIGH) -> Alert:
        return Alert(
            id=uuid4(),
            event_id=uuid4(),
            session_id=SESSION,
            student_id=STUDENT,
            severity=severity,
            reason="Se detecto a otra persona en camara",
            created_at=STARTED_AT.replace(minute=minute),
        )

    def test_insert_uses_the_schema_column_names(
        self, repository: SupabaseAlertRepository, fake: FakeSupabaseClient
    ) -> None:
        repository.save(self.an_alert())

        row = fake.tables["alerts"].inserted[0]
        assert set(row) == {
            "id",
            "event_id",
            "session_id",
            "student_id",
            "severity",
            "reason",
            "created_at",
        }
        assert row["severity"] == "high"

    def test_round_trip(self, repository: SupabaseAlertRepository) -> None:
        alert = self.an_alert()
        repository.save(alert)

        [recovered] = repository.list_by_session(SESSION)

        assert recovered == alert

    def test_newest_first(self, repository: SupabaseAlertRepository) -> None:
        # El docente quiere ver lo ultimo que paso, no lo primero.
        for minute in (10, 30, 20):
            repository.save(self.an_alert(minute=minute))

        minutes = [alert.created_at.minute for alert in repository.list_by_session(SESSION)]
        assert minutes == [30, 20, 10]


class TestProfileRepository:
    @pytest.fixture
    def fake(self) -> FakeSupabaseClient:
        return FakeSupabaseClient(
            {
                "profiles": [
                    {"id": str(STUDENT), "role": "student"},
                    {"id": str(OTHER_STUDENT), "role": "teacher"},
                ]
            }
        )

    @pytest.fixture
    def repository(self, fake: FakeSupabaseClient) -> SupabaseProfileRepository:
        return SupabaseProfileRepository(as_client(fake))

    def test_reads_the_role(self, repository: SupabaseProfileRepository) -> None:
        assert repository.get_role(STUDENT) is UserRole.STUDENT
        assert repository.get_role(OTHER_STUDENT) is UserRole.TEACHER

    def test_unknown_user_has_no_role(self, repository: SupabaseProfileRepository) -> None:
        assert repository.get_role(uuid4()) is None

    def test_an_unexpected_role_value_is_treated_as_none(self, fake: FakeSupabaseClient) -> None:
        # Falla cerrado: un rol que no entendemos no concede nada.
        fake.tables["profiles"].rows.append({"id": str(QUESTION), "role": "admin"})
        repository = SupabaseProfileRepository(as_client(fake))

        assert repository.get_role(QUESTION) is None

    def test_the_result_is_cached(
        self, repository: SupabaseProfileRepository, fake: FakeSupabaseClient
    ) -> None:
        # Sin cache, cada POST de evento metería una consulta extra en el camino
        # mas caliente del sistema.
        repository.get_role(STUDENT)
        repository.get_role(STUDENT)
        repository.get_role(STUDENT)

        assert fake.tables["profiles"].select_count == 1

    def test_the_cache_expires(self, fake: FakeSupabaseClient) -> None:
        # Si un administrador degrada a alguien, deja de ser docente en un minuto.
        repository = SupabaseProfileRepository(as_client(fake), cache_ttl=0)

        repository.get_role(STUDENT)
        repository.get_role(STUDENT)

        assert fake.tables["profiles"].select_count == 2


class TestQuestionRepository:
    @pytest.fixture
    def fake(self) -> FakeSupabaseClient:
        return FakeSupabaseClient(
            {"questions": [{"id": str(QUESTION), "session_id": str(SESSION)}]}
        )

    @pytest.fixture
    def repository(self, fake: FakeSupabaseClient) -> SupabaseQuestionRepository:
        return SupabaseQuestionRepository(as_client(fake))

    def test_resolves_the_session(self, repository: SupabaseQuestionRepository) -> None:
        assert repository.find_session_id(QUESTION) == SESSION

    def test_unknown_question(self, repository: SupabaseQuestionRepository) -> None:
        assert repository.find_session_id(uuid4()) is None

    def test_positive_results_are_cached_forever(
        self, repository: SupabaseQuestionRepository, fake: FakeSupabaseClient
    ) -> None:
        # questions.session_id no cambia nunca una vez creada la pregunta.
        repository.find_session_id(QUESTION)
        repository.find_session_id(QUESTION)

        assert fake.tables["questions"].select_count == 1

    def test_negative_results_are_not_cached(
        self, repository: SupabaseQuestionRepository, fake: FakeSupabaseClient
    ) -> None:
        # Una pregunta puede crearse despues de que se consulte.
        unknown = uuid4()
        assert repository.find_session_id(unknown) is None

        fake.tables["questions"].rows.append({"id": str(unknown), "session_id": str(SESSION)})

        assert repository.find_session_id(unknown) == SESSION
