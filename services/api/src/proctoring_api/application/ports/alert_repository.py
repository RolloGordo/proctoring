"""Puerto de persistencia de alertas."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from proctoring_api.domain.alert import Alert


class AlertRepository(Protocol):
    """Guarda y recupera las alertas que ve el docente.

    Guardar una alerta **es** notificar: la tabla `alerts` esta publicada en
    Supabase Realtime, asi que la insercion llega sola al navegador del docente.
    No hace falta un notificador aparte (ADR-0007).
    """

    def save(self, alert: Alert) -> None:
        """Persiste la alerta. Es lo que dispara el aviso en vivo."""
        ...

    def list_by_session(self, session_id: UUID, student_id: UUID | None = None) -> Sequence[Alert]:
        """Alertas de una sesion, de la mas reciente a la mas antigua.

        Lo necesita el docente que abre la pantalla con el examen ya empezado:
        Realtime solo trae lo que pasa a partir de ese momento.
        """
        ...
