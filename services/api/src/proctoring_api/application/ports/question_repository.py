"""Puerto de consulta de preguntas."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class QuestionRepository(Protocol):
    """Resuelve a que sesion pertenece una pregunta."""

    def find_session_id(self, question_id: UUID) -> UUID | None:
        """Sesion a la que pertenece la pregunta, o `None` si no existe."""
        ...
