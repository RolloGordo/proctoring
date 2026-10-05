"""Lectura de `public.profiles` para saber el rol de un usuario."""

from __future__ import annotations

import threading
import time
from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID

from supabase import Client

from proctoring_api.domain.user import ProfileSummary, UserRole

TABLE = "profiles"
SUMMARY_COLUMNS = "id, role, email, full_name"

#: El rol de alguien no cambia en mitad de un examen, y sin cache cada peticion
#: metria una consulta extra en el camino del POST de eventos. Corto a proposito:
#: si un administrador degrada a alguien, deja de ser docente en un minuto.
CACHE_TTL_SECONDS = 60


class SupabaseProfileRepository:
    """Implementacion de `ProfileRepository` con cache de corta duracion."""

    def __init__(self, client: Client, *, cache_ttl: int = CACHE_TTL_SECONDS) -> None:
        self._client = client
        self._cache_ttl = cache_ttl
        self._cache: dict[UUID, tuple[float, UserRole | None]] = {}
        self._lock = threading.Lock()

    def get_role(self, user_id: UUID) -> UserRole | None:
        cached = self._read_cache(user_id)
        if cached is not _MISS:
            return cast("UserRole | None", cached)

        response = (
            self._client.table(TABLE).select("role").eq("id", str(user_id)).limit(1).execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)

        role: UserRole | None = None
        if rows:
            raw = rows[0].get("role")
            if isinstance(raw, str):
                try:
                    role = UserRole(raw)
                except ValueError:
                    # Rol desconocido en la tabla: se trata como "sin perfil" en
                    # vez de adivinar. Fallar cerrado, no abierto.
                    role = None

        with self._lock:
            self._cache[user_id] = (time.monotonic() + self._cache_ttl, role)
        return role

    def find_by_email(self, email: str) -> ProfileSummary | None:
        # Supabase Auth guarda los correos en minuscula y el trigger los copia
        # tal cual, asi que se compara en minuscula. `eq` y no `ilike`: en un
        # `ilike`, el guion bajo de un correo valdria como comodin.
        response = (
            self._client.table(TABLE)
            .select(SUMMARY_COLUMNS)
            .eq("email", email.strip().lower())
            .limit(1)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        return _to_summary(rows[0]) if rows else None

    def get_summaries(self, user_ids: Sequence[UUID]) -> Mapping[UUID, ProfileSummary]:
        if not user_ids:
            return {}

        response = (
            self._client.table(TABLE)
            .select(SUMMARY_COLUMNS)
            .in_("id", [str(i) for i in user_ids])
            .execute()
        )
        summaries = (_to_summary(row) for row in cast("list[dict[str, Any]]", response.data))
        return {summary.id: summary for summary in summaries if summary is not None}

    def _read_cache(self, user_id: UUID) -> object:
        with self._lock:
            entry = self._cache.get(user_id)
            if entry is None:
                return _MISS
            expires_at, role = entry
            if time.monotonic() >= expires_at:
                del self._cache[user_id]
                return _MISS
            return role


#: Centinela: `None` es un valor valido en cache (usuario sin perfil), asi que no
#: sirve para distinguir "no esta cacheado".
_MISS = object()


def _to_summary(row: dict[str, Any]) -> ProfileSummary | None:
    """Un perfil con rol desconocido se descarta: fallar cerrado, no abierto."""
    try:
        role = UserRole(row["role"])
    except (KeyError, ValueError):
        return None
    return ProfileSummary(
        id=UUID(row["id"]),
        role=role,
        email=row.get("email") or "",
        full_name=row.get("full_name") or row.get("email") or "",
    )
