"""Repositorio de preguntas en memoria, para pruebas y desarrollo."""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from decimal import Decimal
from uuid import UUID

from proctoring_api.domain.grading import MANUAL_TYPES
from proctoring_api.domain.question import Question, QuestionSummary


class InMemoryQuestionRepository:
    """Implementacion de `QuestionRepository` sobre un diccionario."""

    def __init__(self, questions: Sequence[Question] = ()) -> None:
        self._questions: dict[UUID, Question] = {q.id: q for q in questions}
        self._lock = threading.Lock()

    def find_session_id(self, question_id: UUID) -> UUID | None:
        with self._lock:
            pregunta = self._questions.get(question_id)
        return pregunta.session_id if pregunta else None

    def save_many(self, questions: Sequence[Question]) -> None:
        with self._lock:
            for pregunta in questions:
                self._questions[pregunta.id] = pregunta

    def list_by_session(self, session_id: UUID) -> Sequence[Question]:
        with self._lock:
            snapshot = list(self._questions.values())

        de_la_sesion = [q for q in snapshot if q.session_id == session_id]
        return sorted(de_la_sesion, key=lambda q: q.position)

    def count_by_session(self, session_id: UUID) -> int:
        with self._lock:
            return sum(1 for q in self._questions.values() if q.session_id == session_id)

    def summarize_sessions(self, session_ids: Sequence[UUID]) -> Mapping[UUID, QuestionSummary]:
        wanted = set(session_ids)
        with self._lock:
            snapshot = [q for q in self._questions.values() if q.session_id in wanted]

        summary: dict[UUID, QuestionSummary] = {}
        for question in snapshot:
            previous = summary.get(question.session_id)
            summary[question.session_id] = QuestionSummary(
                total_points=(previous.total_points if previous else Decimal(0)) + question.points,
                has_manual_questions=(previous.has_manual_questions if previous else False)
                or question.question_type in MANUAL_TYPES,
            )
        return summary

    def clear(self) -> None:
        """Vacia el repositorio. Solo para pruebas."""
        with self._lock:
            self._questions.clear()
