"""Decisiones sobre la tabla `public.decisions` de Supabase."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from supabase import Client

from proctoring_api.domain.decision import Decision, DecisionType

TABLE = "decisions"
COLUMNS = "id, session_id, student_id, teacher_id, decision, justification, decided_at"


class SupabaseDecisionRepository:
    """Implementacion de `DecisionRepository` contra PostgreSQL via PostgREST."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def save(self, decision: Decision) -> None:
        self._client.table(TABLE).insert(_to_row(decision)).execute()

    def list_by_session(
        self, session_id: UUID, student_id: UUID | None = None
    ) -> Sequence[Decision]:
        query = self._client.table(TABLE).select(COLUMNS).eq("session_id", str(session_id))
        if student_id is not None:
            query = query.eq("student_id", str(student_id))

        response = query.order("decided_at", desc=True).execute()
        return [_to_entity(row) for row in cast("list[dict[str, Any]]", response.data)]


def _to_row(decision: Decision) -> dict[str, Any]:
    return {
        "id": str(decision.id),
        "session_id": str(decision.session_id),
        "student_id": str(decision.student_id),
        "teacher_id": str(decision.teacher_id),
        "decision": decision.decision.value,
        "justification": decision.justification,
        "decided_at": decision.decided_at.isoformat(),
    }


def _to_entity(row: dict[str, Any]) -> Decision:
    return Decision(
        id=UUID(row["id"]),
        session_id=UUID(row["session_id"]),
        student_id=UUID(row["student_id"]),
        teacher_id=UUID(row["teacher_id"]),
        decision=DecisionType(row["decision"]),
        justification=row["justification"],
        decided_at=datetime.fromisoformat(row["decided_at"]),
    )
