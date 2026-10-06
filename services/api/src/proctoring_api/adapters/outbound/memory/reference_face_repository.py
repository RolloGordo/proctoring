"""Caras de referencia en memoria."""

from __future__ import annotations

import threading
from uuid import UUID

from proctoring_api.application.ports.reference_face_repository import ReferenceFace


class InMemoryReferenceFaceRepository:
    """Implementacion de `ReferenceFaceRepository` sobre un diccionario."""

    def __init__(self) -> None:
        self._faces: dict[UUID, ReferenceFace] = {}
        self._lock = threading.Lock()

    def save(self, face: ReferenceFace) -> None:
        with self._lock:
            self._faces[face.student_id] = face

    def find(self, student_id: UUID) -> ReferenceFace | None:
        with self._lock:
            return self._faces.get(student_id)
