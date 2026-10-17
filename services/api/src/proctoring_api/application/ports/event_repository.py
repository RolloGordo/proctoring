"""Puerto de persistencia de eventos."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from proctoring_api.domain.event import ProctoringEvent


class EventRepository(Protocol):
    """Guarda y recupera eventos de proctoring.

    No hay `update` ni `delete` a proposito: los eventos son evidencia. RLS en
    Supabase tampoco los permite. Quien implemente este puerto no debe anadirlos.
    """

    def save(self, event: ProctoringEvent) -> None:
        """Persiste un evento ya validado."""
        ...

    def find_by_id(self, event_id: UUID) -> ProctoringEvent | None:
        """Un evento por su id, o `None` si no existe.

        Lo necesita el servicio de IA: por la cola solo viaja el `event_id`.
        """
        ...

    def list_by_session(
        self, session_id: UUID, student_id: UUID | None = None
    ) -> Sequence[ProctoringEvent]:
        """Eventos de una sesion, ordenados por `started_at` ascendente.

        Si se pasa `student_id`, filtra solo los de ese estudiante.
        """
        ...
