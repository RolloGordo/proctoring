"""Repositorio de alertas sobre la tabla `public.alerts` de Supabase.

Esta tabla esta en la publicacion de Realtime (migracion
`20261003120200_realtime_and_storage.sql`), asi que **insertar aqui es notificar**:
el navegador del docente, suscrito por `session_id`, recibe la fila sin preguntar
nada. Ver ADR-0007.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from supabase import Client

from proctoring_api.domain.alert import Alert
from proctoring_api.domain.severity import Severity

TABLE = "alerts"
COLUMNS = "id, event_id, session_id, student_id, severity, reason, created_at"


class SupabaseAlertRepository:
    """Implementacion de `AlertRepository` contra PostgreSQL via PostgREST."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def save(self, alert: Alert) -> None:
        self._client.table(TABLE).insert(_to_row(alert)).execute()

    def list_by_session(self, session_id: UUID, student_id: UUID | None = None) -> Sequence[Alert]:
        query = self._client.table(TABLE).select(COLUMNS).eq("session_id", str(session_id))
        if student_id is not None:
            query = query.eq("student_id", str(student_id))

        # El indice alerts_session_id_idx es (session_id, created_at).
        response = query.order("created_at", desc=True).execute()
        rows = cast("list[dict[str, Any]]", response.data)
        return [_to_entity(row) for row in rows]


def _to_row(alert: Alert) -> dict[str, Any]:
    return {
        "id": str(alert.id),
        "event_id": str(alert.event_id),
        "session_id": str(alert.session_id),
        "student_id": str(alert.student_id),
        "severity": alert.severity.value,
        "reason": alert.reason,
        "created_at": alert.created_at.isoformat(),
    }


def _to_entity(row: dict[str, Any]) -> Alert:
    return Alert(
        id=UUID(row["id"]),
        event_id=UUID(row["event_id"]),
        session_id=UUID(row["session_id"]),
        student_id=UUID(row["student_id"]),
        severity=Severity(row["severity"]),
        reason=row["reason"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
