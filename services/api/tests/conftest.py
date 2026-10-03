"""Fixtures compartidas."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from proctoring_api.adapters.outbound.memory.alert_repository import InMemoryAlertRepository
from proctoring_api.adapters.outbound.memory.event_repository import InMemoryEventRepository
from proctoring_api.adapters.outbound.memory.job_queue import InMemoryJobQueue
from proctoring_api.adapters.outbound.memory.profile_repository import InMemoryProfileRepository
from proctoring_api.application.ports.token_verifier import TokenClaims
from proctoring_api.application.use_cases.identify_user import IdentifyUser
from proctoring_api.config import Settings
from proctoring_api.domain.errors import AuthenticationError
from proctoring_api.domain.user import UserRole
from proctoring_api.main import create_app

#: Los ejemplos del contrato compartido, que son la misma fuente que usan la app
#: de escritorio y el spike de vision. Probar contra ellos es lo que garantiza que
#: la API y los clientes no se separen sin que algo se ponga rojo.
CONTRACT_EXAMPLES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "examples"

#: Hora de referencia, posterior a los `started_at` de los ejemplos del contrato.
NOW = datetime(2026, 10, 3, 15, 0, 0, tzinfo=UTC)

#: El `student_id` que traen los ejemplos del contrato: el "dueno" de esos eventos.
CONTRACT_STUDENT_ID = UUID("7b2e4d10-5c6f-4a8b-9d0e-2f3a4b5c6d71")
#: Otro estudiante, para probar que no puede reportar eventos ajenos.
OTHER_STUDENT_ID = UUID("1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d")
TEACHER_ID = UUID("0f9e8d7c-6b5a-4938-8271-6a5b4c3d2e1f")

STUDENT_TOKEN = "token-estudiante"
OTHER_STUDENT_TOKEN = "token-otro-estudiante"
TEACHER_TOKEN = "token-docente"


class FixedClock:
    """Reloj detenido, para que las pruebas no dependan de cuando se ejecutan."""

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment


class StubTokenVerifier:
    """Verificador de tokens de mentira.

    Las pruebas no deben depender de un proyecto de Supabase real ni de la red.
    Lo que se prueba aqui son las **reglas de autorizacion**; que la firma ES256
    se verifique bien es responsabilidad de PyJWT.
    """

    def __init__(self, tokens: dict[str, UUID]) -> None:
        self._tokens = tokens

    def verify(self, token: str) -> TokenClaims:
        user_id = self._tokens.get(token)
        if user_id is None:
            raise AuthenticationError("Token invalido")
        return TokenClaims(user_id=user_id)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def event_repository() -> InMemoryEventRepository:
    return InMemoryEventRepository()


@pytest.fixture
def job_queue() -> InMemoryJobQueue:
    return InMemoryJobQueue()


@pytest.fixture
def alert_repository() -> InMemoryAlertRepository:
    return InMemoryAlertRepository()


@pytest.fixture
def contract_example() -> Any:
    """Devuelve una funcion que carga `examples/<event_type>.json`."""

    def load(event_type: str) -> dict[str, Any]:
        path = CONTRACT_EXAMPLES / f"{event_type}.json"
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data

    return load


@pytest.fixture
def identify_user() -> IdentifyUser:
    """`IdentifyUser` con tres usuarios conocidos y sin red."""
    profiles = InMemoryProfileRepository(
        {
            CONTRACT_STUDENT_ID: UserRole.STUDENT,
            OTHER_STUDENT_ID: UserRole.STUDENT,
            TEACHER_ID: UserRole.TEACHER,
        }
    )
    verifier = StubTokenVerifier(
        {
            STUDENT_TOKEN: CONTRACT_STUDENT_ID,
            OTHER_STUDENT_TOKEN: OTHER_STUDENT_ID,
            TEACHER_TOKEN: TEACHER_ID,
        }
    )
    return IdentifyUser(verifier, profiles)


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "env": "test",
        "auth_enabled": False,
        "event_repository": "memory",
        "job_queue": "memory",
        "evidence_storage": "memory",
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def app(clock: FixedClock) -> FastAPI:
    """App **sin autenticacion**, para probar el contrato de los endpoints.

    Con el reloj fijo en `NOW`, los `started_at` de los ejemplos del contrato
    quedan siempre en el pasado y las pruebas no dependen de cuando se ejecuten.
    """
    return create_app(_settings(), clock=clock)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authed_app(clock: FixedClock, identify_user: IdentifyUser) -> FastAPI:
    """App **con autenticacion**, para probar las reglas de autorizacion."""
    return create_app(_settings(auth_enabled=True), clock=clock, identify_user=identify_user)


@pytest.fixture
def authed_client(authed_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(authed_app) as test_client:
        yield test_client
