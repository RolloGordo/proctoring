"""Analisis de audio sobre la tabla `public.audio_analyses`."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from supabase import Client

from proctoring_api.domain.audio_analysis import AudioAnalysis

TABLE = "audio_analyses"
COLUMNS = (
    "id, event_id, transcript, similarity, synthetic_voice_score, "
    "matched_question_id, processing_ms, model_versions, processed_at"
)


class SupabaseAudioAnalysisRepository:
    """Implementacion de `AudioAnalysisRepository` contra PostgreSQL via PostgREST."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def save(self, analysis: AudioAnalysis) -> None:
        # upsert sobre event_id, que es unico: RQ reintenta hasta tres veces y un
        # reintento debe reemplazar el resultado, no anadir otra fila.
        self._client.table(TABLE).upsert(_to_row(analysis), on_conflict="event_id").execute()

    def find_by_event(self, event_id: UUID) -> AudioAnalysis | None:
        response = (
            self._client.table(TABLE)
            .select(COLUMNS)
            .eq("event_id", str(event_id))
            .limit(1)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        return _to_entity(rows[0]) if rows else None


def _to_row(analysis: AudioAnalysis) -> dict[str, Any]:
    return {
        "id": str(analysis.id),
        "event_id": str(analysis.event_id),
        "transcript": analysis.transcript,
        "similarity": analysis.similarity,
        "synthetic_voice_score": analysis.synthetic_voice_score,
        "matched_question_id": (
            str(analysis.matched_question_id) if analysis.matched_question_id else None
        ),
        "processing_ms": analysis.processing_ms,
        "model_versions": analysis.model_versions,
        "processed_at": analysis.processed_at.isoformat(),
    }


def _to_entity(row: dict[str, Any]) -> AudioAnalysis:
    pregunta = row.get("matched_question_id")
    return AudioAnalysis(
        id=UUID(row["id"]),
        event_id=UUID(row["event_id"]),
        transcript=row.get("transcript"),
        similarity=row.get("similarity"),
        synthetic_voice_score=row.get("synthetic_voice_score"),
        matched_question_id=UUID(pregunta) if pregunta else None,
        processing_ms=row.get("processing_ms"),
        model_versions=row.get("model_versions") or {},
        processed_at=datetime.fromisoformat(row["processed_at"]),
    )
