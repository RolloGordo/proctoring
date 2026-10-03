"""Repositorio de preguntas en memoria, para pruebas.

En modo memoria la composicion de `main.py` **no cablea ningun** repositorio de
preguntas: no existe banco de preguntas porque nadie ha creado un examen, y
rechazar todo evento con `question_id` dejaria a Rider y a Jesus sin poder mandar
`gaze_away` ni `speech_detected` mientras desarrollan.

Este adaptador existe para que las pruebas puedan sembrar preguntas conocidas y
comprobar la regla de verdad.
"""

from __future__ import annotations

import threading
from uuid import UUID


class InMemoryQuestionRepository:
    """Implementacion de `QuestionRepository` sobre un diccionario."""

    def __init__(self, questions: dict[UUID, UUID] | None = None) -> None:
        #: question_id -> session_id
        self._questions: dict[UUID, UUID] = dict(questions or {})
        self._lock = threading.Lock()

    def find_session_id(self, question_id: UUID) -> UUID | None:
        with self._lock:
            return self._questions.get(question_id)

    def add(self, question_id: UUID, session_id: UUID) -> None:
        with self._lock:
            self._questions[question_id] = session_id
