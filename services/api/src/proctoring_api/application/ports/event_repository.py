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

    def list_by_episode(
        self, session_id: UUID, student_id: UUID, episode_id: str
    ) -> Sequence[ProctoringEvent]:
        """Los informes ya guardados de un episodio (`metadata.episode_id`).

        Los necesita el registro de eventos para avisar al docente solo cuando
        un episodio sube de severidad, y no en cada informe.
        """
        ...

    def list_by_session(
        self, session_id: UUID, student_id: UUID | None = None
    ) -> Sequence[ProctoringEvent]:
        """Eventos de una sesion, ordenados por `started_at` ascendente.

        Si se pasa `student_id`, filtra solo los de ese estudiante.
        """
        ...
