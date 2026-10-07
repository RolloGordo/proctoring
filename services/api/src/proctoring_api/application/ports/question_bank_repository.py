"""Puerto de bancos de preguntas."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol
from uuid import UUID

from proctoring_api.domain.question_bank import QuestionBank


class QuestionBankRepository(Protocol):
    """Guarda bancos y de que bancos extrae cada examen."""

    def save(self, bank: QuestionBank) -> None:
        """Crea el banco."""
        ...

    def find_by_id(self, bank_id: UUID) -> QuestionBank | None:
        """El banco, o `None` si no existe."""
        ...

    def list_by_teacher(self, teacher_id: UUID) -> Sequence[QuestionBank]:
        """Bancos de un docente, del mas reciente al mas antiguo."""
        ...

    def count_questions(self, bank_ids: Sequence[UUID]) -> Mapping[UUID, int]:
        """Cuantas preguntas tiene cada banco, en una sola consulta.

        Los bancos vacios no aparecen: quien lo use trata la ausencia como cero.
        """
        ...

    def attach_to_session(self, session_id: UUID, bank_id: UUID) -> bool:
        """Ata un banco a un examen. `False` si ya estaba atado.

        Idempotente: atar dos veces no es un error ni crea una fila repetida.
        """
        ...

    def detach_from_session(self, session_id: UUID, bank_id: UUID) -> None:
        """Quita el banco del examen. Las preguntas del banco no se tocan."""
        ...

    def list_session_banks(self, session_id: UUID) -> Sequence[QuestionBank]:
        """Los bancos de los que extrae un examen."""
        ...
