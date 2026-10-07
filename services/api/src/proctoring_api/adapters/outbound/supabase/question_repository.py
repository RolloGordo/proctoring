"""Preguntas y opciones sobre Supabase.

Una pregunta vive en dos tablas: `questions` y `question_options`. Se escriben en
ese orden porque la segunda tiene clave foranea a la primera.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from supabase import Client

from proctoring_api.domain.grading import MANUAL_TYPES
from proctoring_api.domain.question import (
    Question,
    QuestionOption,
    QuestionSummary,
    QuestionType,
)

QUESTIONS_TABLE = "questions"
OPTIONS_TABLE = "question_options"

COLUMNS = (
    "id, session_id, bank_id, position, question_type, statement, points, "
    "correct_numeric_answer, numeric_tolerance, correct_text_answer, source_format"
)
OPTION_COLUMNS = "id, question_id, position, option_text, is_correct"


class SupabaseQuestionRepository:
    """Implementacion de `QuestionRepository` contra PostgreSQL via PostgREST."""

    def __init__(self, client: Client) -> None:
        self._client = client
        #: question_id -> session_id. No cambia nunca una vez creada la pregunta,
        #: y esta consulta se hace en cada `gaze_away` y cada `speech_detected`.
        self._session_cache: dict[UUID, UUID] = {}
        self._lock = threading.Lock()

    def find_session_id(self, question_id: UUID) -> UUID | None:
        with self._lock:
            cached = self._session_cache.get(question_id)
        if cached is not None:
            return cached

        response = (
            self._client.table(QUESTIONS_TABLE)
            .select("session_id")
            .eq("id", str(question_id))
            .limit(1)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        if not rows:
            return None

        raw = rows[0].get("session_id")
        if not isinstance(raw, str):
            return None

        session_id = UUID(raw)
        with self._lock:
            self._session_cache[question_id] = session_id
        return session_id

    def save_many(self, questions: Sequence[Question]) -> None:
        if not questions:
            return

        self._client.table(QUESTIONS_TABLE).insert([_question_row(q) for q in questions]).execute()

        opciones = [_option_row(q.id, opcion) for q in questions for opcion in q.options]
        if opciones:
            self._client.table(OPTIONS_TABLE).insert(opciones).execute()

        with self._lock:
            for pregunta in questions:
                # Las de banco no tienen sesion: cachearlas con `None` haria que
                # `find_session_id` devolviera un acierto falso.
                if pregunta.session_id is not None:
                    self._session_cache[pregunta.id] = pregunta.session_id

    def list_by_session(self, session_id: UUID) -> Sequence[Question]:
        response = (
            self._client.table(QUESTIONS_TABLE)
            .select(COLUMNS)
            .eq("session_id", str(session_id))
            .order("position", desc=False)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        if not rows:
            return []

        opciones = self._options_of(session_id)
        return [_to_entity(row, opciones.get(UUID(row["id"]), ())) for row in rows]

    def list_by_bank(self, bank_id: UUID) -> Sequence[Question]:
        return self.list_by_banks([bank_id])

    def list_by_banks(self, bank_ids: Sequence[UUID]) -> Sequence[Question]:
        if not bank_ids:
            return []

        response = (
            self._client.table(QUESTIONS_TABLE)
            .select(COLUMNS)
            .in_("bank_id", [str(i) for i in bank_ids])
            .order("position", desc=False)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        if not rows:
            return []

        opciones = self._options_of_questions([UUID(row["id"]) for row in rows])
        return [_to_entity(row, opciones.get(UUID(row["id"]), ())) for row in rows]

    def count_by_bank(self, bank_id: UUID) -> int:
        response = (
            self._client.table(QUESTIONS_TABLE).select("id").eq("bank_id", str(bank_id)).execute()
        )
        return len(cast("list[dict[str, Any]]", response.data))

    def count_by_session(self, session_id: UUID) -> int:
        response = (
            self._client.table(QUESTIONS_TABLE)
            .select("id")
            .eq("session_id", str(session_id))
            .execute()
        )
        return len(cast("list[dict[str, Any]]", response.data))

    def summarize_sessions(self, session_ids: Sequence[UUID]) -> Mapping[UUID, QuestionSummary]:
        if not session_ids:
            return {}

        # Solo dos columnas de todas las sesiones, en una consulta: el panel no
        # necesita los enunciados ni las respuestas correctas para mostrar "7 de 10".
        response = (
            self._client.table(QUESTIONS_TABLE)
            .select("session_id, points, question_type")
            .in_("session_id", [str(i) for i in session_ids])
            .execute()
        )
        summary: dict[UUID, QuestionSummary] = {}
        for row in cast("list[dict[str, Any]]", response.data):
            session_id = UUID(row["session_id"])
            previous = summary.get(session_id)
            summary[session_id] = QuestionSummary(
                total_points=(previous.total_points if previous else Decimal(0))
                + Decimal(str(row["points"])),
                has_manual_questions=(previous.has_manual_questions if previous else False)
                or QuestionType(row["question_type"]) in MANUAL_TYPES,
            )
        return summary

    def _options_of_questions(
        self, question_ids: Sequence[UUID]
    ) -> dict[UUID, tuple[QuestionOption, ...]]:
        """Las opciones de esas preguntas, en una sola consulta.

        Existe aparte de `_options_of` porque las preguntas de un banco no cuelgan
        de ninguna sesion: no se pueden pedir filtrando por `session_id`.
        """
        if not question_ids:
            return {}

        response = (
            self._client.table(OPTIONS_TABLE)
            .select(OPTION_COLUMNS)
            .in_("question_id", [str(i) for i in question_ids])
            .order("position", desc=False)
            .execute()
        )
        return _agrupar_opciones(cast("list[dict[str, Any]]", response.data))

    def _options_of(self, session_id: UUID) -> dict[UUID, tuple[QuestionOption, ...]]:
        """Todas las opciones de la sesion en una sola consulta.

        Una consulta por pregunta convertiria un examen de 40 preguntas en 41
        viajes a la base.
        """
        response = (
            self._client.table(OPTIONS_TABLE)
            .select(f"{OPTION_COLUMNS}, questions!inner(session_id)")
            .eq("questions.session_id", str(session_id))
            .order("position", desc=False)
            .execute()
        )
        return _agrupar_opciones(cast("list[dict[str, Any]]", response.data))


def _agrupar_opciones(rows: list[dict[str, Any]]) -> dict[UUID, tuple[QuestionOption, ...]]:
    agrupadas: dict[UUID, list[QuestionOption]] = {}
    for row in rows:
        question_id = UUID(row["question_id"])
        agrupadas.setdefault(question_id, []).append(
            QuestionOption(
                id=UUID(row["id"]),
                position=row["position"],
                option_text=row["option_text"],
                is_correct=bool(row["is_correct"]),
            )
        )
    return {k: tuple(v) for k, v in agrupadas.items()}


def _question_row(question: Question) -> dict[str, Any]:
    return {
        "id": str(question.id),
        "session_id": str(question.session_id) if question.session_id else None,
        "bank_id": str(question.bank_id) if question.bank_id else None,
        "position": question.position,
        "question_type": question.question_type.value,
        "statement": question.statement,
        "points": str(question.points),
        "correct_numeric_answer": (
            str(question.correct_numeric_answer)
            if question.correct_numeric_answer is not None
            else None
        ),
        "numeric_tolerance": (
            str(question.numeric_tolerance) if question.numeric_tolerance is not None else None
        ),
        "correct_text_answer": question.correct_text_answer,
        "source_format": question.source_format,
    }


def _option_row(question_id: UUID, option: QuestionOption) -> dict[str, Any]:
    return {
        "id": str(option.id),
        "question_id": str(question_id),
        "position": option.position,
        "option_text": option.option_text,
        "is_correct": option.is_correct,
    }


def _to_entity(row: dict[str, Any], options: tuple[QuestionOption, ...]) -> Question:
    def decimal_o_none(valor: Any) -> Decimal | None:
        return Decimal(str(valor)) if valor is not None else None

    sesion = row.get("session_id")
    banco = row.get("bank_id")
    return Question(
        id=UUID(row["id"]),
        session_id=UUID(sesion) if sesion else None,
        bank_id=UUID(banco) if banco else None,
        position=row["position"],
        question_type=QuestionType(row["question_type"]),
        statement=row["statement"],
        points=Decimal(str(row["points"])),
        options=options,
        correct_numeric_answer=decimal_o_none(row.get("correct_numeric_answer")),
        numeric_tolerance=decimal_o_none(row.get("numeric_tolerance")),
        correct_text_answer=row.get("correct_text_answer"),
        source_format=row.get("source_format"),
    )
