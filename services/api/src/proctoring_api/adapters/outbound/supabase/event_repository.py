"""Repositorio de eventos sobre la tabla `public.events` de Supabase.

Se activa con `EVENT_REPOSITORY=supabase`. Usa la **service role key**, que omite
RLS: es deliberado, porque la API es el unico camino privilegiado del sistema.

La contrapartida es importante y esta en el README: como RLS no protege estas
escrituras, comprobar que el `student_id` del evento es de verdad el usuario
autenticado le corresponde a la capa de aplicacion, no a la base de datos.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from supabase import Client

from proctoring_api.domain.event import EventType, ProctoringEvent

TABLE = "events"

#: Columnas que se piden y se escriben. Explicitas a proposito: si alguien anade
#: una columna a la tabla, esto no se rompe en silencio.
COLUMNS = (
    "id, session_id, student_id, question_id, event_type, "
    "started_at, duration_ms, metadata, evidence_path"
)


class SupabaseEventRepository:
    """Implementacion de `EventRepository` contra PostgreSQL via PostgREST."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def save(self, event: ProctoringEvent) -> None:
        self._client.table(TABLE).insert(_to_row(event)).execute()

    def list_by_session(
        self, session_id: UUID, student_id: UUID | None = None
    ) -> Sequence[ProctoringEvent]:
        query = self._client.table(TABLE).select(COLUMNS).eq("session_id", str(session_id))
        if student_id is not None:
            query = query.eq("student_id", str(student_id))

        # El indice events_session_student_started_idx cubre exactamente este orden.
        response = query.order("started_at", desc=False).execute()
        # El SDK tipa `data` como JSON generico; un select sobre una tabla siempre
        # devuelve filas, y el cast lo acota sin mentirle a mypy en el resto.
        rows = cast("list[dict[str, Any]]", response.data)
        return [_to_entity(row) for row in rows]


def _to_row(event: ProctoringEvent) -> dict[str, Any]:
    """Entidad -> fila de PostgREST (JSON)."""
    return {
        "id": str(event.id),
        "session_id": str(event.session_id),
        "student_id": str(event.student_id),
        "question_id": str(event.question_id) if event.question_id else None,
        "event_type": event.event_type.value,
        "started_at": event.started_at.isoformat(),
        "duration_ms": event.duration_ms,
        "metadata": dict(event.metadata),
        "evidence_path": event.evidence_path,
    }


def _to_entity(row: dict[str, Any]) -> ProctoringEvent:
    """Fila de PostgREST -> entidad.

    Se reconstruye con el constructor directo y no con `create`: lo que esta en la
    tabla ya paso por la validacion al insertarse, y volver a validarlo haria que
    un cambio de reglas rompiera la lectura de evidencia historica.
    """
    question_id = row.get("question_id")
    return ProctoringEvent(
        id=UUID(row["id"]),
        session_id=UUID(row["session_id"]),
        student_id=UUID(row["student_id"]),
        question_id=UUID(question_id) if question_id else None,
        event_type=EventType(row["event_type"]),
        started_at=datetime.fromisoformat(row["started_at"]),
        duration_ms=row["duration_ms"],
        metadata=row.get("metadata") or {},
        evidence_path=row.get("evidence_path"),
    )
