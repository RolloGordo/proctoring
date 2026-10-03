"""Reloj del sistema."""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """Implementacion de `Clock` con la hora real, siempre en UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)
