"""Consulta de `public.questions` para validar el `question_id` de un evento."""

from __future__ import annotations

import threading
from typing import Any, cast
from uuid import UUID

from supabase import Client

TABLE = "questions"


class SupabaseQuestionRepository:
    """Implementacion de `QuestionRepository` con cache permanente.

    La pertenencia de una pregunta a una sesion **no cambia nunca** una vez
    creada: `questions.session_id` no se actualiza. Por eso el resultado positivo
    se cachea sin caducidad, y asi la validacion no mete una consulta extra en
    cada `gaze_away` y cada `speech_detected`, que son los eventos mas frecuentes
    del sistema.

    Los negativos no se cachean: una pregunta puede crearse despues.
    """

    def __init__(self, client: Client) -> None:
        self._client = client
        self._cache: dict[UUID, UUID] = {}
        self._lock = threading.Lock()

    def find_session_id(self, question_id: UUID) -> UUID | None:
        with self._lock:
            cached = self._cache.get(question_id)
        if cached is not None:
            return cached

        response = (
            self._client.table(TABLE)
            .select("session_id")
            .eq("id", str(question_id))
            .limit(1)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        if not rows:
            return None

        raw = rows[0].get("session_id")
        if not isinstance(raw, str):
            return None

        session_id = UUID(raw)
        with self._lock:
            self._cache[question_id] = session_id
        return session_id
