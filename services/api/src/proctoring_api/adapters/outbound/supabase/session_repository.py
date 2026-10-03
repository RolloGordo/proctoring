"""Consulta de `public.exam_sessions` para saber de quien es una sesion."""

from __future__ import annotations

import threading
from typing import Any, cast
from uuid import UUID

from supabase import Client

TABLE = "exam_sessions"


class SupabaseSessionRepository:
    """Implementacion de `SessionRepository` con cache permanente.

    `exam_sessions.teacher_id` no cambia: una sesion no cambia de dueno. Por eso
    el resultado positivo se cachea sin caducidad, y la comprobacion de acceso no
    anade una consulta a cada lectura de eventos o de alertas — que es lo que la
    pantalla en vivo del docente hace continuamente.

    Los negativos no se cachean: la sesion puede crearse despues.
    """

    def __init__(self, client: Client) -> None:
        self._client = client
        self._cache: dict[UUID, UUID] = {}
        self._lock = threading.Lock()

    def find_teacher_id(self, session_id: UUID) -> UUID | None:
        with self._lock:
            cached = self._cache.get(session_id)
        if cached is not None:
            return cached

        response = (
            self._client.table(TABLE)
            .select("teacher_id")
            .eq("id", str(session_id))
            .limit(1)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        if not rows:
            return None

        raw = rows[0].get("teacher_id")
        if not isinstance(raw, str):
            return None

        teacher_id = UUID(raw)
        with self._lock:
            self._cache[session_id] = teacher_id
        return teacher_id
