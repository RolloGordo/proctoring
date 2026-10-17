"""Puerto de la cara de referencia de cada estudiante."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ReferenceFace:
    """La cara con la que se compara al estudiante al entrar a un examen.

    Se registra **una vez**. `embedding` lo calcula el servicio de IA la primera
    vez que la usa y se guarda para no recalcularlo en cada examen.
    """

    student_id: UUID
    storage_path: str
    embedding: list[float] | None
    model_version: str | None
    registered_at: datetime


class ReferenceFaceRepository(Protocol):
    """Guarda y recupera la cara de referencia."""

    def save(self, face: ReferenceFace) -> None:
        """Crea o reemplaza la referencia de ese estudiante."""
        ...

    def find(self, student_id: UUID) -> ReferenceFace | None:
        """La referencia, o `None` si el estudiante todavia no registro una."""
        ...
