"""Puerto de reloj.

Existe para que los casos de uso no llamen a `datetime.now()` directamente: con el
reloj detras de un puerto, las pruebas fijan la hora y dejan de depender de cuando
se ejecutan.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Fuente de la hora actual, siempre con zona horaria."""

    def now(self) -> datetime:
        """Hora actual en UTC, con `tzinfo`."""
        ...
