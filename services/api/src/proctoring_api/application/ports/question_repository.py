"""Puerto de preguntas."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from proctoring_api.domain.question import Question


class QuestionRepository(Protocol):
    """Guarda y recupera las preguntas de un examen.

    `list_by_session` devuelve `Question`, que **incluye las respuestas
    correctas**. Quien lo llame es responsable de no entregarlas a un estudiante:
    para eso existe `Question.for_student()`.
    """

    def find_session_id(self, question_id: UUID) -> UUID | None:
        """Sesion a la que pertenece la pregunta, o `None` si no existe."""
        ...

    def save_many(self, questions: Sequence[Question]) -> None:
        """Persiste varias preguntas con sus opciones."""
        ...

    def list_by_session(self, session_id: UUID) -> Sequence[Question]:
        """Preguntas de una sesion, ordenadas por `position`."""
        ...

    def count_by_session(self, session_id: UUID) -> int:
        """Cuantas preguntas tiene ya la sesion."""
        ...
