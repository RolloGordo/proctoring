"""Respuestas sobre la tabla `public.answers` de Supabase."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from supabase import Client

from proctoring_api.domain.answer import Answer

TABLE = "answers"
COLUMNS = (
    "id, participant_id, question_id, selected_option_id, text_answer, numeric_answer, answered_at"
)


class SupabaseAnswerRepository:
    """Implementacion de `AnswerRepository` contra PostgreSQL via PostgREST."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def save_many(self, answers: Sequence[Answer]) -> None:
        if not answers:
            return

        # upsert sobre (participant_id, question_id), la clave unica de la tabla:
        # cambiar de respuesta reemplaza la anterior en una sola ida y vuelta.
        self._client.table(TABLE).upsert(
            [_to_row(a) for a in answers], on_conflict="participant_id,question_id"
        ).execute()

    def list_by_participant(self, participant_id: UUID) -> Sequence[Answer]:
        response = (
            self._client.table(TABLE)
            .select(COLUMNS)
            .eq("participant_id", str(participant_id))
            .order("answered_at", desc=False)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        return [_to_entity(row) for row in rows]


def _to_row(answer: Answer) -> dict[str, Any]:
    return {
        "id": str(answer.id),
        "participant_id": str(answer.participant_id),
        "question_id": str(answer.question_id),
        "selected_option_id": (
            str(answer.selected_option_id) if answer.selected_option_id else None
        ),
        "text_answer": answer.text_answer,
        # numeric llega como texto para no perder decimales por el camino.
        "numeric_answer": str(answer.numeric_answer) if answer.numeric_answer is not None else None,
        "answered_at": answer.answered_at.isoformat(),
    }


def _to_entity(row: dict[str, Any]) -> Answer:
    opcion = row.get("selected_option_id")
    numero = row.get("numeric_answer")
    return Answer(
        id=UUID(row["id"]),
        participant_id=UUID(row["participant_id"]),
        question_id=UUID(row["question_id"]),
        answered_at=datetime.fromisoformat(row["answered_at"]),
        selected_option_id=UUID(opcion) if opcion else None,
        text_answer=row.get("text_answer"),
        numeric_answer=Decimal(str(numero)) if numero is not None else None,
    )
