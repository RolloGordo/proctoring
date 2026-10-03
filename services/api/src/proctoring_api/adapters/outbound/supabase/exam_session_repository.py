"""Repositorio de sesiones de examen sobre Supabase.

Una sesion vive en dos tablas: `exam_sessions` y `session_modules`. Se escriben
en ese orden porque la segunda tiene una clave foranea a la primera.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from supabase import Client

from proctoring_api.domain.exam_session import (
    ExamSession,
    SessionStatus,
    SupervisionModule,
    SupervisionPreset,
)

SESSIONS_TABLE = "exam_sessions"
MODULES_TABLE = "session_modules"

COLUMNS = (
    "id, course_id, teacher_id, title, description, starts_at, duration_minutes, "
    "entry_tolerance_minutes, access_code, preset, max_attempts, shuffle_questions, "
    "shuffle_options, allow_back_navigation, status"
)


class SupabaseExamSessionRepository:
    """Implementacion de `ExamSessionRepository` contra PostgreSQL via PostgREST."""

    def __init__(self, client: Client) -> None:
        self._client = client
        #: session_id -> teacher_id. Una sesion no cambia de dueno, asi que el
        #: positivo se cachea sin caducidad: la comprobacion de acceso se hace en
        #: cada lectura de eventos y de alertas.
        self._owner_cache: dict[UUID, UUID] = {}
        self._lock = threading.Lock()

    def save(self, session: ExamSession) -> None:
        self._client.table(SESSIONS_TABLE).insert(_to_row(session)).execute()

        if session.modules:
            self._client.table(MODULES_TABLE).insert(
                [
                    {
                        "session_id": str(session.id),
                        "module": module.value,
                        "enabled": True,
                        "settings": settings,
                    }
                    for module, settings in session.modules.items()
                ]
            ).execute()

        with self._lock:
            self._owner_cache[session.id] = session.teacher_id

    def find_by_id(self, session_id: UUID) -> ExamSession | None:
        response = (
            self._client.table(SESSIONS_TABLE)
            .select(COLUMNS)
            .eq("id", str(session_id))
            .limit(1)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        if not rows:
            return None

        return _to_entity(rows[0], self._modules_of(session_id))

    def find_teacher_id(self, session_id: UUID) -> UUID | None:
        with self._lock:
            cached = self._owner_cache.get(session_id)
        if cached is not None:
            return cached

        response = (
            self._client.table(SESSIONS_TABLE)
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
            self._owner_cache[session_id] = teacher_id
        return teacher_id

    def list_by_teacher(self, teacher_id: UUID) -> Sequence[ExamSession]:
        response = (
            self._client.table(SESSIONS_TABLE)
            .select(COLUMNS)
            .eq("teacher_id", str(teacher_id))
            .order("starts_at", desc=True)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        # Sin los modulos: el listado no los muestra y traerlos seria una consulta
        # por sesion. El detalle (`find_by_id`) si los incluye.
        return [_to_entity(row, {}) for row in rows]

    def find_by_access_code(self, access_code: str) -> ExamSession | None:
        response = (
            self._client.table(SESSIONS_TABLE)
            .select(COLUMNS)
            .eq("access_code", access_code)
            .limit(1)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        if not rows:
            return None

        session = _to_entity(rows[0], {})
        return _to_entity(rows[0], self._modules_of(session.id))

    def access_code_exists(self, access_code: str) -> bool:
        response = (
            self._client.table(SESSIONS_TABLE)
            .select("id")
            .eq("access_code", access_code)
            .limit(1)
            .execute()
        )
        return bool(cast("list[dict[str, Any]]", response.data))

    def _modules_of(self, session_id: UUID) -> dict[SupervisionModule, dict[str, Any]]:
        response = (
            self._client.table(MODULES_TABLE)
            .select("module, enabled, settings")
            .eq("session_id", str(session_id))
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        return {
            SupervisionModule(row["module"]): row.get("settings") or {}
            for row in rows
            if row.get("enabled", True)
        }


def _to_row(session: ExamSession) -> dict[str, Any]:
    return {
        "id": str(session.id),
        "course_id": str(session.course_id) if session.course_id else None,
        "teacher_id": str(session.teacher_id),
        "title": session.title,
        "description": session.description,
        "starts_at": session.starts_at.isoformat(),
        "duration_minutes": session.duration_minutes,
        "entry_tolerance_minutes": session.entry_tolerance_minutes,
        "access_code": session.access_code,
        "preset": session.preset.value,
        "max_attempts": session.max_attempts,
        "shuffle_questions": session.shuffle_questions,
        "shuffle_options": session.shuffle_options,
        "allow_back_navigation": session.allow_back_navigation,
        "status": session.status.value,
    }


def _to_entity(
    row: dict[str, Any], modules: dict[SupervisionModule, dict[str, Any]]
) -> ExamSession:
    course_id = row.get("course_id")
    return ExamSession(
        id=UUID(row["id"]),
        teacher_id=UUID(row["teacher_id"]),
        title=row["title"],
        starts_at=datetime.fromisoformat(row["starts_at"]),
        duration_minutes=row["duration_minutes"],
        access_code=row["access_code"],
        course_id=UUID(course_id) if course_id else None,
        description=row.get("description"),
        entry_tolerance_minutes=row["entry_tolerance_minutes"],
        preset=SupervisionPreset(row["preset"]),
        status=SessionStatus(row["status"]),
        max_attempts=row["max_attempts"],
        shuffle_questions=row["shuffle_questions"],
        shuffle_options=row["shuffle_options"],
        allow_back_navigation=row["allow_back_navigation"],
        modules=modules,
    )
