"""Matrículas sobre la tabla `public.session_participants` de Supabase."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from supabase import Client

from proctoring_api.domain.participant import SessionParticipant, VerificationStatus

TABLE = "session_participants"
COLUMNS = (
    "id, session_id, student_id, attempt, verification_status, verified_at, "
    "verification_reviewed_by, consent_at, requested_in_person, started_at, "
    "submitted_at, score"
)


class SupabaseParticipantRepository:
    """Implementacion de `ParticipantRepository` contra PostgreSQL via PostgREST."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def save(self, participant: SessionParticipant) -> None:
        # upsert sobre la clave unica (session_id, student_id, attempt): el
        # estudiante consiente una vez y luego se actualiza su estado conforme
        # verifica, empieza y entrega.
        self._client.table(TABLE).upsert(
            _to_row(participant), on_conflict="session_id,student_id,attempt"
        ).execute()

    def find(self, session_id: UUID, student_id: UUID) -> SessionParticipant | None:
        response = (
            self._client.table(TABLE)
            .select(COLUMNS)
            .eq("session_id", str(session_id))
            .eq("student_id", str(student_id))
            .limit(1)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        return _to_entity(rows[0]) if rows else None

    def find_by_id(self, participant_id: UUID) -> SessionParticipant | None:
        response = (
            self._client.table(TABLE)
            .select(COLUMNS)
            .eq("id", str(participant_id))
            .limit(1)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        return _to_entity(rows[0]) if rows else None

    def list_by_student(self, student_id: UUID) -> Sequence[SessionParticipant]:
        response = (
            self._client.table(TABLE)
            .select(COLUMNS)
            .eq("student_id", str(student_id))
            .order("consent_at", desc=True)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        return [_to_entity(row) for row in rows]

    def list_by_session(self, session_id: UUID) -> Sequence[SessionParticipant]:
        response = (
            self._client.table(TABLE)
            .select(COLUMNS)
            .eq("session_id", str(session_id))
            .order("consent_at", desc=False)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        return [_to_entity(row) for row in rows]


def _to_row(participant: SessionParticipant) -> dict[str, Any]:
    return {
        "id": str(participant.id),
        "session_id": str(participant.session_id),
        "student_id": str(participant.student_id),
        "attempt": participant.attempt,
        "verification_status": participant.verification_status.value,
        "verified_at": _iso(participant.verified_at),
        "verification_reviewed_by": (
            str(participant.verification_reviewed_by)
            if participant.verification_reviewed_by
            else None
        ),
        "consent_at": _iso(participant.consent_at),
        "requested_in_person": participant.requested_in_person,
        "started_at": _iso(participant.started_at),
        "submitted_at": _iso(participant.submitted_at),
        "score": participant.score,
    }


def _iso(momento: datetime | None) -> str | None:
    return momento.isoformat() if momento else None


def _parse(valor: Any) -> datetime | None:
    return datetime.fromisoformat(valor) if isinstance(valor, str) else None


def _to_entity(row: dict[str, Any]) -> SessionParticipant:
    revisor = row.get("verification_reviewed_by")
    return SessionParticipant(
        id=UUID(row["id"]),
        session_id=UUID(row["session_id"]),
        student_id=UUID(row["student_id"]),
        attempt=row["attempt"],
        verification_status=VerificationStatus(row["verification_status"]),
        consent_at=_parse(row.get("consent_at")),
        verified_at=_parse(row.get("verified_at")),
        verification_reviewed_by=UUID(revisor) if revisor else None,
        requested_in_person=bool(row.get("requested_in_person", False)),
        started_at=_parse(row.get("started_at")),
        submitted_at=_parse(row.get("submitted_at")),
        score=row.get("score"),
    )
