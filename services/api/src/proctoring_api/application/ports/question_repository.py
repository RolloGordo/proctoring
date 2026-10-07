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
        """Persiste varias preguntas con sus opciones.

        Crea las que no existen y **reemplaza** las que si, opciones incluidas:
        corregir una pregunta pasa por aqui.
        """
        ...

    def find_by_id(self, question_id: UUID) -> Question | None:
        """La pregunta con sus opciones y su respuesta correcta, o `None`."""
        ...

    def delete(self, question_id: UUID) -> None:
        """Borra la pregunta y sus opciones. Borrar una que no existe no es un error."""
        ...

    def list_by_session(self, session_id: UUID) -> Sequence[Question]:
        """Preguntas de una sesion, ordenadas por `position`."""
        ...

    def list_by_bank(self, bank_id: UUID) -> Sequence[Question]:
        """Preguntas de un banco, ordenadas por `position`."""
        ...

    def list_by_banks(self, bank_ids: Sequence[UUID]) -> Sequence[Question]:
        """Preguntas de varios bancos, en una sola consulta.

        Es lo que un examen tiene disponible para sortear: pedirlas banco por
        banco seria una consulta por banco en el camino mas caliente, el de
        servir el examen.
        """
        ...

    def count_by_bank(self, bank_id: UUID) -> int:
        """Cuantas preguntas tiene ya el banco. Sirve para numerar la siguiente."""
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
