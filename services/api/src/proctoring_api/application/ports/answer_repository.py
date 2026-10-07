"""Puerto de respuestas del estudiante."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from proctoring_api.domain.answer import Answer


class AnswerRepository(Protocol):
    """Guarda y recupera lo que cada estudiante respondió.

    `save_many` tiene que ser **idempotente por `(participant_id, question_id)`**:
    la pantalla del examen guarda cada vez que el estudiante cambia de respuesta,
    así que la misma pregunta llega muchas veces y la última gana.
    """

    def save_many(self, answers: Sequence[Answer]) -> None:
        """Crea o reemplaza las respuestas recibidas."""
        ...

    def list_by_participant(self, participant_id: UUID) -> Sequence[Answer]:
        """Las respuestas de un participante, para retomar el examen."""
        ...

    def count_by_question(self, question_id: UUID) -> int:
        """Cuantos estudiantes respondieron esa pregunta.

        Es lo que decide si una pregunta todavia se puede corregir: cambiarle la
        alternativa correcta a una ya contestada reescribiria la nota de quien la
        respondio bien.
        """
        ...
