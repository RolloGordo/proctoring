"""Caso de uso `IdentifyUser`."""

from __future__ import annotations

from uuid import UUID, uuid4

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


class CuentaLecturas(InMemoryProfileRepository):
    """Cuenta cuántas veces se lee `profiles`: lo que la caché tiene que ahorrar."""

    def __init__(self, roles: dict[UUID, UserRole]) -> None:
        super().__init__(roles)
        self.lecturas = 0

    def get_role(self, user_id: UUID) -> UserRole | None:
        self.lecturas += 1
        return super().get_role(user_id)


class Reloj:
    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora


class TestRolRecordado:
    """ADR-0011: el rol se recuerda un minuto; la firma se verifica siempre."""

    def armar(self, **kw: float) -> tuple[IdentifyUser, CuentaLecturas, Reloj]:
        perfiles = CuentaLecturas({STUDENT: UserRole.STUDENT, TEACHER: UserRole.TEACHER})
        reloj = Reloj()
        verifier = StubTokenVerifier({"t-student": STUDENT, "t-sin-perfil": SIN_PERFIL})
        return IdentifyUser(verifier, perfiles, reloj=reloj, **kw), perfiles, reloj

    def test_la_segunda_peticion_no_vuelve_a_leer_profiles(self) -> None:
        caso, perfiles, _ = self.armar()

        for _ in range(5):
            assert caso.execute("t-student").is_student

        assert perfiles.lecturas == 1

    def test_pasado_el_minuto_se_vuelve_a_leer(self) -> None:
        caso, perfiles, reloj = self.armar(role_ttl_seconds=60)
        caso.execute("t-student")

        reloj.ahora += 61
        caso.execute("t-student")

        assert perfiles.lecturas == 2

    def test_un_token_invalido_falla_aunque_el_rol_este_recordado(self) -> None:
        caso, _, _ = self.armar()
        caso.execute("t-student")

        with pytest.raises(AuthenticationError):
            caso.execute("token-inventado")

    def test_sin_perfil_no_se_recuerda(self) -> None:
        caso, perfiles, _ = self.armar()

        for _ in range(2):
            with pytest.raises(AuthenticationError):
                caso.execute("t-sin-perfil")

        assert perfiles.lecturas == 2

    def test_con_ttl_cero_no_se_recuerda_nada(self) -> None:
        caso, perfiles, _ = self.armar(role_ttl_seconds=0)

        caso.execute("t-student")
        caso.execute("t-student")

        assert perfiles.lecturas == 2
