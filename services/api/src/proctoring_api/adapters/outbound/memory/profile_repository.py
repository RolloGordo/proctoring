"""Repositorio de perfiles en memoria.

Para pruebas y para desarrollo local sin Supabase.
"""

from __future__ import annotations

import threading
from uuid import UUID

from proctoring_api.domain.user import UserRole


class InMemoryProfileRepository:
    """Implementacion de `ProfileRepository` sobre un diccionario."""

    def __init__(self, roles: dict[UUID, UserRole] | None = None) -> None:
        self._roles: dict[UUID, UserRole] = dict(roles or {})
        self._lock = threading.Lock()

    def get_role(self, user_id: UUID) -> UserRole | None:
        with self._lock:
            return self._roles.get(user_id)

    def set_role(self, user_id: UUID, role: UserRole) -> None:
        """Registra un usuario. Solo para pruebas y desarrollo."""
        with self._lock:
            self._roles[user_id] = role
