"""Repositorio de respuestas en memoria."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from uuid import UUID

from proctoring_api.domain.answer import Answer


class InMemoryAnswerRepository:
    """Implementacion de `AnswerRepository` sobre un diccionario."""

    def __init__(self, answers: Sequence[Answer] = ()) -> None:
        #: (participant_id, question_id) -> respuesta. La misma clave unica que
        #: la tabla `answers`: responder otra vez sobrescribe.
        self._answers: dict[tuple[UUID, UUID], Answer] = {
            (a.participant_id, a.question_id): a for a in answers
        }
        self._lock = threading.Lock()

    def save_many(self, answers: Sequence[Answer]) -> None:
        with self._lock:
            for answer in answers:
                self._answers[(answer.participant_id, answer.question_id)] = answer

    def list_by_participant(self, participant_id: UUID) -> Sequence[Answer]:
        with self._lock:
            snapshot = list(self._answers.values())

        suyas = [a for a in snapshot if a.participant_id == participant_id]
        return sorted(suyas, key=lambda a: a.answered_at)

    def clear(self) -> None:
        """Vacia el repositorio. Solo para pruebas."""
        with self._lock:
            self._answers.clear()
