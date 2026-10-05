"""Puerto de preguntas."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol
from uuid import UUID

from proctoring_api.domain.question import Question, QuestionSummary


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

    def summarize_sessions(self, session_ids: Sequence[UUID]) -> Mapping[UUID, QuestionSummary]:
        """Puntos totales y si hay preguntas manuales, de varias sesiones a la vez.

        Existe para el panel del estudiante, que muestra "7 de 10" en cada examen
        entregado: traer las preguntas enteras de cada uno seria una consulta por
        fila y traeria las respuestas correctas sin necesidad.
        """
        ...
