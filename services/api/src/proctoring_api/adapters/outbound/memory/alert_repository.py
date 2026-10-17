"""Repositorio de alertas en memoria.

Sin Supabase no hay Realtime, asi que aqui "notificar" se queda en guardar. Sirve
para las pruebas y para desarrollo local.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from uuid import UUID

from proctoring_api.domain.alert import Alert


class InMemoryAlertRepository:
    """Implementacion de `AlertRepository` sobre una lista, protegida con lock."""

    def __init__(self) -> None:
        self._alerts: list[Alert] = []
        self._lock = threading.Lock()

    def save(self, alert: Alert) -> None:
        with self._lock:
            self._alerts.append(alert)

    def list_by_session(self, session_id: UUID, student_id: UUID | None = None) -> Sequence[Alert]:
        with self._lock:
            snapshot = list(self._alerts)

        matches = [
            alert
            for alert in snapshot
            if alert.session_id == session_id
            and (student_id is None or alert.student_id == student_id)
        ]
        # De la mas reciente a la mas antigua: lo primero que el docente quiere ver.
        return sorted(matches, key=lambda alert: alert.created_at, reverse=True)

    def clear(self) -> None:
        """Vacia el repositorio. Solo para pruebas."""
        with self._lock:
            self._alerts.clear()
