"""PostgREST corta en `max_rows` filas sin avisar: las listas del examen se leen enteras."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast
from uuid import UUID

import pytest

from proctoring_api.adapters.outbound.supabase import paginas
from proctoring_api.adapters.outbound.supabase.alert_repository import SupabaseAlertRepository
from proctoring_api.adapters.outbound.supabase.event_repository import SupabaseEventRepository
from proctoring_api.domain.alert import Alert
from proctoring_api.domain.event import EventType, ProctoringEvent
from proctoring_api.domain.severity import Severity

from tests.doubles import FakeSupabaseClient

if TYPE_CHECKING:
    from supabase import Client

SESSION = UUID("3f1a7c20-9b4e-4d2a-8f6c-1e2d3a4b5c60")
STUDENT = UUID("7b2e4d10-5c6f-4a8b-9d0e-2f3a4b5c6d71")
INICIO = datetime(2026, 11, 14, 15, 0, tzinfo=UTC)


def _evento(segundo: int) -> ProctoringEvent:
    return ProctoringEvent.create(
        session_id=SESSION,
        student_id=STUDENT,
        question_id=None,
        event_type=EventType.FOCUS_LOST,
        started_at=INICIO + timedelta(seconds=segundo),
        duration_ms=1_000,
        metadata={},
        evidence_path=None,
    )


def test_las_senales_pasan_de_las_mil_filas_que_corta_postgrest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Página de 10 en vez de 1000 para no crear miles de filas: misma lógica.
    monkeypatch.setattr(paginas, "PAGINA", 10)
    fake = FakeSupabaseClient({"events": []}, max_rows=10)
    repositorio = SupabaseEventRepository(cast("Client", fake))
    for segundo in range(25):
        repositorio.save(_evento(segundo))

    leidos = repositorio.list_by_session(SESSION)

    assert len(leidos) == 25
    # Sin huecos ni repetidos, y la más nueva incluida: es la que el docente busca.
    assert [e.started_at for e in leidos] == sorted(e.started_at for e in leidos)
    assert leidos[-1].started_at == INICIO + timedelta(seconds=24)


def test_las_alertas_tambien_se_leen_enteras(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paginas, "PAGINA", 10)
    fake = FakeSupabaseClient({"alerts": []}, max_rows=10)
    repositorio = SupabaseAlertRepository(cast("Client", fake))
    for segundo in range(23):
        evento = _evento(segundo)
        repositorio.save(
            Alert.from_event(evento, Severity.HIGH, INICIO + timedelta(seconds=segundo))
        )

    leidas = repositorio.list_by_session(SESSION)

    assert len(leidas) == 23
    assert len({a.id for a in leidas}) == 23
    assert leidas[0].created_at == INICIO + timedelta(seconds=22)
