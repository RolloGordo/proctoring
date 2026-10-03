"""Fixtures compartidas."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from proctoring_api.adapters.outbound.memory.event_repository import InMemoryEventRepository
from proctoring_api.adapters.outbound.memory.job_queue import InMemoryJobQueue
from proctoring_api.config import Settings
from proctoring_api.main import create_app

#: Los ejemplos del contrato compartido, que son la misma fuente que usan la app
#: de escritorio y el spike de vision. Probar contra ellos es lo que garantiza que
#: la API y los clientes no se separen sin que algo se ponga rojo.
CONTRACT_EXAMPLES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "examples"


class FixedClock:
    """Reloj detenido, para que las pruebas no dependan de cuando se ejecutan."""

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment


#: Hora de referencia, posterior a los `started_at` de los ejemplos del contrato.
NOW = datetime(2026, 10, 3, 15, 0, 0, tzinfo=UTC)


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
def contract_example() -> Any:
    """Devuelve una funcion que carga `examples/<event_type>.json`."""

    def load(event_type: str) -> dict[str, Any]:
        path = CONTRACT_EXAMPLES / f"{event_type}.json"
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data

    return load


@pytest.fixture
def app(clock: FixedClock) -> FastAPI:
    """App con adaptadores en memoria: sin Supabase, sin Redis, sin red.

    Con el reloj fijo en `NOW`, los `started_at` de los ejemplos del contrato
    quedan siempre en el pasado y las pruebas no dependen de cuando se ejecuten.
    """
    return create_app(
        Settings(
            env="test",
            event_repository="memory",
            job_queue="memory",
            evidence_storage="memory",
        ),
        clock=clock,
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
