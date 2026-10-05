"""Puerto de decisiones del docente."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from proctoring_api.domain.decision import Decision


class DecisionRepository(Protocol):
    """Guarda y recupera las decisiones.

    No hay `update` ni `delete` a proposito: una decision es evidencia. Si el
    docente cambia de parecer, se registra **otra**, y el historial queda.
    """

    def save(self, decision: Decision) -> None:
        """Registra la decision."""
        ...

    def list_by_session(
        self, session_id: UUID, student_id: UUID | None = None
    ) -> Sequence[Decision]:
        """Decisiones de una sesion, de la mas reciente a la mas antigua.

        Si se pasa `student_id`, solo las de ese estudiante.
        """
        ...
