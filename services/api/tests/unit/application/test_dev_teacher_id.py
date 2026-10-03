"""El docente ficticio del modo sin autenticacion es configurable.

`exam_sessions.teacher_id` tiene clave foranea a `profiles`. Con el id ficticio
por defecto, crear una sesion contra Supabase falla porque ese docente no existe.
Poder sustituirlo por el id de un docente real es lo que permite probar el camino
completo contra la base antes de que exista el login.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from proctoring_api.adapters.outbound.memory.exam_session_repository import (
    InMemoryExamSessionRepository,
)
from proctoring_api.application.use_cases.create_exam_session import (
    DEFAULT_DEV_TEACHER_ID,
    CreateExamSession,
    CreateExamSessionInput,
)
from proctoring_api.application.use_cases.list_teacher_sessions import ListTeacherSessions
from proctoring_api.config import Settings
from proctoring_api.domain.user import AuthenticatedUser, UserRole

REAL_TEACHER = UUID("743c74c5-4beb-4183-beac-3c9984211f60")
STARTS_AT = datetime(2026, 10, 10, 14, 0, tzinfo=UTC)


def an_input() -> CreateExamSessionInput:
    return CreateExamSessionInput(title="Examen parcial", starts_at=STARTS_AT, duration_minutes=90)


@pytest.fixture
def sessions() -> InMemoryExamSessionRepository:
    return InMemoryExamSessionRepository()


def test_uses_the_default_when_not_configured(
    sessions: InMemoryExamSessionRepository,
) -> None:
    session = CreateExamSession(sessions).execute(an_input())

    assert session.teacher_id == DEFAULT_DEV_TEACHER_ID


def test_uses_the_configured_teacher(sessions: InMemoryExamSessionRepository) -> None:
    session = CreateExamSession(sessions, REAL_TEACHER).execute(an_input())

    assert session.teacher_id == REAL_TEACHER


def test_listing_matches_what_was_created(
    sessions: InMemoryExamSessionRepository,
) -> None:
    # Si el id de creacion y el de listado no coincidieran, el docente crearia
    # sesiones que luego no ve.
    CreateExamSession(sessions, REAL_TEACHER).execute(an_input())

    listed = ListTeacherSessions(sessions, REAL_TEACHER).execute()

    assert len(listed) == 1
    assert listed[0].teacher_id == REAL_TEACHER


def test_a_real_actor_always_wins_over_the_dev_id(
    sessions: InMemoryExamSessionRepository,
) -> None:
    # Con autenticacion activa el id ficticio no se usa nunca, aunque este puesto.
    teacher = AuthenticatedUser(id=uuid4(), role=UserRole.TEACHER)

    session = CreateExamSession(sessions, REAL_TEACHER).execute(an_input(), actor=teacher)

    assert session.teacher_id == teacher.id


class TestSettings:
    def test_default_value(self) -> None:
        assert Settings(_env_file=None).dev_teacher_id == DEFAULT_DEV_TEACHER_ID  # type: ignore[call-arg]

    def test_reads_the_environment_variable(self) -> None:
        settings = Settings(_env_file=None, dev_teacher_id=REAL_TEACHER)  # type: ignore[call-arg]

        assert settings.dev_teacher_id == REAL_TEACHER
