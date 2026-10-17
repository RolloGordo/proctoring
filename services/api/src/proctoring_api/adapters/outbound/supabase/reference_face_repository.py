"""Caras de referencia sobre la tabla `public.reference_faces`."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from supabase import Client

from proctoring_api.application.ports.reference_face_repository import ReferenceFace

TABLE = "reference_faces"
COLUMNS = "student_id, storage_path, embedding, model_version, registered_at"


class SupabaseReferenceFaceRepository:
    """Implementacion de `ReferenceFaceRepository` contra PostgreSQL via PostgREST."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def save(self, face: ReferenceFace) -> None:
        self._client.table(TABLE).upsert(_to_row(face), on_conflict="student_id").execute()

    def find(self, student_id: UUID) -> ReferenceFace | None:
        response = (
            self._client.table(TABLE)
            .select(COLUMNS)
            .eq("student_id", str(student_id))
            .limit(1)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        return _to_entity(rows[0]) if rows else None


def _to_row(face: ReferenceFace) -> dict[str, Any]:
    return {
        "student_id": str(face.student_id),
        "storage_path": face.storage_path,
        "embedding": face.embedding,
        "model_version": face.model_version,
        "registered_at": face.registered_at.isoformat(),
    }


def _to_entity(row: dict[str, Any]) -> ReferenceFace:
    return ReferenceFace(
        student_id=UUID(row["student_id"]),
        storage_path=row["storage_path"],
        embedding=row.get("embedding"),
        model_version=row.get("model_version"),
        registered_at=datetime.fromisoformat(row["registered_at"]),
    )
