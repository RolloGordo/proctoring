"""Puerto de lectura de perfiles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol
from uuid import UUID

from proctoring_api.domain.user import ProfileSummary, UserRole


class ProfileRepository(Protocol):
    """Lee el perfil del sistema de un usuario de Auth."""

    def get_role(self, user_id: UUID) -> UserRole | None:
        """Rol del usuario, o `None` si no tiene fila en `profiles`.

        Que no tenga perfil no es un caso raro: pasa entre que alguien se registra
        en Auth y el trigger `on_auth_user_created` crea su fila. Se trata como
        "todavia no es nadie en este sistema", no como un error.
        """
        ...

    def find_by_email(self, email: str) -> ProfileSummary | None:
        """El perfil con ese correo, o `None`. No distingue mayusculas.

        Es como un docente matricula a un estudiante: escribe su correo.
        """
        ...

    def get_summaries(self, user_ids: Sequence[UUID]) -> Mapping[UUID, ProfileSummary]:
        """Nombre y correo de varias personas en una sola consulta.

        Los que no tienen perfil se omiten. Existe para listas (los miembros de un
        curso, la sala de espera): pedirlos de uno en uno seria una consulta por
        fila.
        """
        ...
