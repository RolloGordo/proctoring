"""Puerto de lectura de perfiles."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from proctoring_api.domain.user import UserRole


class ProfileRepository(Protocol):
    """Lee el perfil del sistema de un usuario de Auth."""

    def get_role(self, user_id: UUID) -> UserRole | None:
        """Rol del usuario, o `None` si no tiene fila en `profiles`.

        Que no tenga perfil no es un caso raro: pasa entre que alguien se registra
        en Auth y el trigger `on_auth_user_created` crea su fila. Se trata como
        "todavia no es nadie en este sistema", no como un error.
        """
        ...
