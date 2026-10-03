"""Puerto de consulta de sesiones de examen."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class SessionRepository(Protocol):
    """Resuelve de quien es una sesion de examen."""

    def find_teacher_id(self, session_id: UUID) -> UUID | None:
        """Docente dueno de la sesion, o `None` si la sesion no existe."""
        ...
