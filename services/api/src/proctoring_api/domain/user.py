"""Usuario autenticado y su rol.

El rol **no** viaja en el JWT de Supabase: ahi el claim `role` vale siempre
`authenticated`, que es el rol de PostgreSQL, no el nuestro. El rol del sistema
vive en `public.profiles.role`, asi que identificar a alguien son dos pasos:
verificar el token y luego leer su perfil.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class UserRole(StrEnum):
    """Rol del sistema. Mismos valores que el enum `user_role` de PostgreSQL."""

    TEACHER = "teacher"
    STUDENT = "student"


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Quien esta haciendo la peticion."""

    id: UUID
    role: UserRole
    email: str | None = None

    @property
    def is_teacher(self) -> bool:
        return self.role is UserRole.TEACHER

    @property
    def is_student(self) -> bool:
        return self.role is UserRole.STUDENT


@dataclass(frozen=True, slots=True)
class ProfileSummary:
    """Lo que el sistema sabe de una persona para mostrarla: quién es.

    No lleva contraseña ni nada de Auth: solo lo que ya está en `public.profiles`.
    """

    id: UUID
    role: UserRole
    email: str
    full_name: str
