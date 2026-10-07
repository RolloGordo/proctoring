"""Bancos de preguntas sobre `public.question_banks` y `public.exam_session_banks`."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from supabase import Client

from proctoring_api.domain.question_bank import QuestionBank

BANKS_TABLE = "question_banks"
LINKS_TABLE = "exam_session_banks"
QUESTIONS_TABLE = "questions"
COLUMNS = "id, teacher_id, course_id, name, description, created_at"


class SupabaseQuestionBankRepository:
    """Implementacion de `QuestionBankRepository` contra PostgreSQL via PostgREST."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def save(self, bank: QuestionBank) -> None:
        self._client.table(BANKS_TABLE).insert(_to_row(bank)).execute()

    def find_by_id(self, bank_id: UUID) -> QuestionBank | None:
        response = (
            self._client.table(BANKS_TABLE)
            .select(COLUMNS)
            .eq("id", str(bank_id))
            .limit(1)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        return _to_entity(rows[0]) if rows else None

    def list_by_teacher(self, teacher_id: UUID) -> Sequence[QuestionBank]:
        response = (
            self._client.table(BANKS_TABLE)
            .select(COLUMNS)
            .eq("teacher_id", str(teacher_id))
            .order("created_at", desc=True)
            .execute()
        )
        return [_to_entity(row) for row in cast("list[dict[str, Any]]", response.data)]

    def count_questions(self, bank_ids: Sequence[UUID]) -> Mapping[UUID, int]:
        if not bank_ids:
            return {}

        # Una sola columna de todos los bancos a la vez: el listado no necesita
        # los enunciados ni las respuestas correctas para decir "40 preguntas".
        response = (
            self._client.table(QUESTIONS_TABLE)
            .select("bank_id")
            .in_("bank_id", [str(i) for i in bank_ids])
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        return dict(Counter(UUID(row["bank_id"]) for row in rows if row.get("bank_id")))

    def attach_to_session(self, session_id: UUID, bank_id: UUID) -> bool:
        existe = (
            self._client.table(LINKS_TABLE)
            .select("bank_id")
            .eq("session_id", str(session_id))
            .eq("bank_id", str(bank_id))
            .limit(1)
            .execute()
        )
        if cast("list[dict[str, Any]]", existe.data):
            return False

        self._client.table(LINKS_TABLE).insert(
            {"session_id": str(session_id), "bank_id": str(bank_id)}
        ).execute()
        return True

    def detach_from_session(self, session_id: UUID, bank_id: UUID) -> None:
        self._client.table(LINKS_TABLE).delete().eq("session_id", str(session_id)).eq(
            "bank_id", str(bank_id)
        ).execute()

    def list_session_banks(self, session_id: UUID) -> Sequence[QuestionBank]:
        atados = (
            self._client.table(LINKS_TABLE)
            .select("bank_id")
            .eq("session_id", str(session_id))
            .order("added_at", desc=False)
            .execute()
        )
        ids = [row["bank_id"] for row in cast("list[dict[str, Any]]", atados.data)]
        if not ids:
            return []

        response = self._client.table(BANKS_TABLE).select(COLUMNS).in_("id", ids).execute()
        bancos = {
            b.id: b for b in (_to_entity(r) for r in cast("list[dict[str, Any]]", response.data))
        }
        # En el orden en que se ataron, que es el que eligio el docente.
        return [bancos[UUID(i)] for i in ids if UUID(i) in bancos]


def _to_row(bank: QuestionBank) -> dict[str, Any]:
    """La fila que se escribe. Vive aparte para que una prueba pueda comprobar
    que todo lo que se escribe esta tambien en `COLUMNS`, que es lo que se lee."""
    return {
        "id": str(bank.id),
        "teacher_id": str(bank.teacher_id),
        "course_id": str(bank.course_id) if bank.course_id else None,
        "name": bank.name,
        "description": bank.description,
        "created_at": bank.created_at.isoformat(),
    }


def _to_entity(row: dict[str, Any]) -> QuestionBank:
    curso = row.get("course_id")
    return QuestionBank(
        id=UUID(row["id"]),
        teacher_id=UUID(row["teacher_id"]),
        course_id=UUID(curso) if curso else None,
        name=row["name"],
        description=row.get("description"),
        created_at=datetime.fromisoformat(row["created_at"]),
    )
