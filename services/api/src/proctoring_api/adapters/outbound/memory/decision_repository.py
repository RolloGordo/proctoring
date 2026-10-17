"""Repositorio de decisiones en memoria."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from uuid import UUID

from proctoring_api.domain.decision import Decision


class InMemoryDecisionRepository:
    """Implementacion de `DecisionRepository` sobre una lista."""

    def __init__(self) -> None:
        self._decisions: list[Decision] = []
        self._lock = threading.Lock()

    def save(self, decision: Decision) -> None:
        with self._lock:
            self._decisions.append(decision)

    def list_by_session(
        self, session_id: UUID, student_id: UUID | None = None
    ) -> Sequence[Decision]:
        with self._lock:
            snapshot = list(enumerate(self._decisions))

        found = [
            (index, d)
            for index, d in snapshot
            if d.session_id == session_id and (student_id is None or d.student_id == student_id)
        ]
        # La mas reciente primero. Con la misma hora gana la guardada despues: sin
        # este desempate el orden dependeria de como ordena Python los empates, y
        # "la decision vigente" no puede depender de eso.
        found.sort(key=lambda item: (item[1].decided_at, item[0]), reverse=True)
        return [d for _, d in found]
