"""Caso de uso `IdentifyUser`."""

from __future__ import annotations

from uuid import uuid4

import pytest

from proctoring_api.adapters.outbound.memory.profile_repository import InMemoryProfileRepository
from proctoring_api.application.use_cases.identify_user import IdentifyUser
from proctoring_api.domain.errors import AuthenticationError
from proctoring_api.domain.user import UserRole

from tests.conftest import StubTokenVerifier

STUDENT = uuid4()
TEACHER = uuid4()
SIN_PERFIL = uuid4()


@pytest.fixture
def use_case() -> IdentifyUser:
    profiles = InMemoryProfileRepository({STUDENT: UserRole.STUDENT, TEACHER: UserRole.TEACHER})
    verifier = StubTokenVerifier(
        {"t-student": STUDENT, "t-teacher": TEACHER, "t-sin-perfil": SIN_PERFIL}
    )
    return IdentifyUser(verifier, profiles)


def test_identifies_a_student(use_case: IdentifyUser) -> None:
    user = use_case.execute("t-student")

    assert user.id == STUDENT
    assert user.is_student
    assert not user.is_teacher


def test_identifies_a_teacher(use_case: IdentifyUser) -> None:
    user = use_case.execute("t-teacher")

    assert user.id == TEACHER
    assert user.is_teacher


def test_rejects_an_invalid_token(use_case: IdentifyUser) -> None:
    with pytest.raises(AuthenticationError):
        use_case.execute("token-inventado")


def test_rejects_a_user_without_profile(use_case: IdentifyUser) -> None:
    """Existe en Auth pero no en `profiles`.

    No se le asigna un rol por defecto: adivinar aqui es como se acaba dando
    permisos de docente a quien no los tiene. Falla cerrado.
    """
    with pytest.raises(AuthenticationError, match="perfil"):
        use_case.execute("t-sin-perfil")
