"""Puerto de persistencia de sesiones de examen."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from proctoring_api.domain.exam_session import ExamSession


class ExamSessionRepository(Protocol):
    """Guarda y recupera sesiones de examen.

    `find_teacher_id` existe aparte de `find_by_id` porque la comprobacion de
    acceso se hace en **cada** lectura de eventos y de alertas: traer la sesion
    entera para mirar una columna seria pagar de mas en el camino que mas se
    recorre (la pantalla en vivo del docente).
    """

    def save(self, session: ExamSession) -> None:
        """Persiste la sesion y sus modulos."""
        ...

    def find_by_id(self, session_id: UUID) -> ExamSession | None:
        """La sesion con sus modulos, o `None` si no existe."""
        ...

    def find_teacher_id(self, session_id: UUID) -> UUID | None:
        """Docente dueno de la sesion, o `None` si la sesion no existe."""
        ...

    def list_by_teacher(self, teacher_id: UUID) -> Sequence[ExamSession]:
        """Sesiones de un docente, de la mas proxima a la mas antigua."""
        ...

    def find_many(self, session_ids: Sequence[UUID]) -> Sequence[ExamSession]:
        """Las sesiones con esos ids, en una sola consulta. Los que no existen se omiten.

        Existe para el panel del estudiante, que muestra varios examenes a la
        vez: pedirlos de uno en uno seria una consulta por fila.
        """
        ...

    def find_by_access_code(self, access_code: str) -> ExamSession | None:
        """La sesion con ese codigo de acceso, o `None` si no existe.

        Es como entra el estudiante: teclea el codigo que le dio el docente.
        """
        ...

    def access_code_exists(self, access_code: str) -> bool:
        """Si ese codigo de acceso ya esta en uso."""
        ...
