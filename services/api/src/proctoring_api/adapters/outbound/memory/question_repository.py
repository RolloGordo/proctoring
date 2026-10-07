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

    def list_by_bank(self, bank_id: UUID) -> Sequence[Question]:
        with self._lock:
            snapshot = list(self._questions.values())

        del_banco = [q for q in snapshot if q.bank_id == bank_id]
        return sorted(del_banco, key=lambda q: q.position)

    def list_by_banks(self, bank_ids: Sequence[UUID]) -> Sequence[Question]:
        wanted = set(bank_ids)
        with self._lock:
            snapshot = list(self._questions.values())

        de_los_bancos = [q for q in snapshot if q.bank_id in wanted]
        return sorted(de_los_bancos, key=lambda q: (q.position, str(q.id)))

    def count_by_bank(self, bank_id: UUID) -> int:
        with self._lock:
            return sum(1 for q in self._questions.values() if q.bank_id == bank_id)

    def count_by_session(self, session_id: UUID) -> int:
        with self._lock:
            return sum(1 for q in self._questions.values() if q.session_id == session_id)

    def summarize_sessions(self, session_ids: Sequence[UUID]) -> Mapping[UUID, QuestionSummary]:
        wanted = set(session_ids)
        with self._lock:
            snapshot = [q for q in self._questions.values() if q.session_id in wanted]

        summary: dict[UUID, QuestionSummary] = {}
        for question in snapshot:
            # El filtro de arriba ya descarta las de banco; esto lo hace explicito
            # para quien lea y para el verificador de tipos.
            if question.session_id is None:
                continue
            previous = summary.get(question.session_id)
            summary[question.session_id] = QuestionSummary(
                total_points=(previous.total_points if previous else Decimal(0)) + question.points,
                has_manual_questions=(previous.has_manual_questions if previous else False)
                or question.question_type in MANUAL_TYPES,
            )
        return summary

    def find_by_id(self, question_id: UUID) -> Question | None:
        with self._lock:
            return self._questions.get(question_id)

    def delete(self, question_id: UUID) -> None:
        with self._lock:
            self._questions.pop(question_id, None)

    def clear(self) -> None:
        """Vacia el repositorio. Solo para pruebas."""
        with self._lock:
            self._questions.clear()
