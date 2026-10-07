"""Bancos de preguntas en memoria."""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from uuid import UUID

from proctoring_api.application.ports.question_repository import QuestionRepository
from proctoring_api.domain.question_bank import QuestionBank


class InMemoryQuestionBankRepository:
    """Implementacion de `QuestionBankRepository` sobre diccionarios."""

    def __init__(self, questions: QuestionRepository | None = None) -> None:
        self._banks: dict[UUID, QuestionBank] = {}
        #: session_id -> bancos atados, en el orden en que se ataron.
        self._attached: dict[UUID, list[UUID]] = {}
        #: Para contar preguntas hace falta mirar el repositorio de preguntas.
        #: Sin el, `count_questions` devuelve vacio y quien lo use ve ceros.
        self._questions = questions
        self._lock = threading.Lock()

    def save(self, bank: QuestionBank) -> None:
        with self._lock:
            self._banks[bank.id] = bank

    def find_by_id(self, bank_id: UUID) -> QuestionBank | None:
        with self._lock:
            return self._banks.get(bank_id)

    def list_by_teacher(self, teacher_id: UUID) -> Sequence[QuestionBank]:
        with self._lock:
            mios = [b for b in self._banks.values() if b.teacher_id == teacher_id]
        return sorted(mios, key=lambda b: b.created_at, reverse=True)

    def count_questions(self, bank_ids: Sequence[UUID]) -> Mapping[UUID, int]:
        if self._questions is None:
            return {}
        conteo: dict[UUID, int] = {}
        for bank_id in bank_ids:
            cantidad = len(self._questions.list_by_bank(bank_id))
            if cantidad:
                conteo[bank_id] = cantidad
        return conteo

    def attach_to_session(self, session_id: UUID, bank_id: UUID) -> bool:
        with self._lock:
            atados = self._attached.setdefault(session_id, [])
            if bank_id in atados:
                return False
            atados.append(bank_id)
            return True

    def detach_from_session(self, session_id: UUID, bank_id: UUID) -> None:
        with self._lock:
            atados = self._attached.get(session_id)
            if atados and bank_id in atados:
                atados.remove(bank_id)

    def list_session_banks(self, session_id: UUID) -> Sequence[QuestionBank]:
        with self._lock:
            ids = list(self._attached.get(session_id, []))
            return [self._banks[i] for i in ids if i in self._banks]
