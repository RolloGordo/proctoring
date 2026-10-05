"""Repositorio de perfiles en memoria.

Para pruebas y para desarrollo local sin Supabase.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from uuid import UUID

from proctoring_api.domain.user import ProfileSummary, UserRole


class InMemoryProfileRepository:
    """Implementacion de `ProfileRepository` sobre un diccionario."""

    def __init__(
        self,
        roles: dict[UUID, UserRole] | None = None,
        summaries: Sequence[ProfileSummary] = (),
    ) -> None:
        self._roles: dict[UUID, UserRole] = dict(roles or {})
        self._summaries: dict[UUID, ProfileSummary] = {p.id: p for p in summaries}
        for summary in summaries:
            self._roles[summary.id] = summary.role
        self._lock = threading.Lock()

    def get_role(self, user_id: UUID) -> UserRole | None:
        with self._lock:
            return self._roles.get(user_id)

    def set_role(self, user_id: UUID, role: UserRole) -> None:
        """Registra un usuario. Solo para pruebas y desarrollo."""
        with self._lock:
            self._roles[user_id] = role

    def add_profile(self, summary: ProfileSummary) -> None:
        """Registra a alguien con nombre y correo. Solo para pruebas y desarrollo."""
        with self._lock:
            self._summaries[summary.id] = summary
            self._roles[summary.id] = summary.role

    def find_by_email(self, email: str) -> ProfileSummary | None:
        wanted = email.strip().casefold()
        with self._lock:
            for summary in self._summaries.values():
                if summary.email.casefold() == wanted:
                    return summary
        return None

    def get_summaries(self, user_ids: Sequence[UUID]) -> Mapping[UUID, ProfileSummary]:
        with self._lock:
            return {i: self._summaries[i] for i in user_ids if i in self._summaries}
