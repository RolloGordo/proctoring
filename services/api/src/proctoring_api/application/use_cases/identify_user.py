"""Caso de uso: identificar al usuario que hace la peticion."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from uuid import UUID

from proctoring_api.application.ports.profile_repository import ProfileRepository
from proctoring_api.application.ports.token_verifier import TokenVerifier
from proctoring_api.domain.errors import AuthenticationError
from proctoring_api.domain.user import AuthenticatedUser, UserRole

#: Cuanto se recuerda el rol de una persona. La prueba de carga (ADR-0011)
#: mostro que leer `profiles` en **cada** peticion era la primera de cuatro
#: consultas seguidas de «mi estado» y la mas repetida de toda la API. El rol
#: solo cambia cuando la service role asciende a alguien a docente, asi que un
#: minuto de retraso en ese caso no le quita nada a nadie.
ROLE_TTL_SECONDS = 60.0

#: Cuantas personas se recuerdan por proceso. Mil estudiantes en examen caben
#: de sobra; el tope evita que la memoria crezca sin limite.
ROLE_CACHE_SIZE = 10_000


class _RolesRecientes:
    """Los roles leidos hace poco, por proceso, con caducidad y tope de tamaño."""

    def __init__(self, ttl: float, tamano: int, reloj: Callable[[], float]) -> None:
        self._ttl = ttl
        self._tamano = tamano
        self._reloj = reloj
        self._roles: OrderedDict[UUID, tuple[UserRole, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, user_id: UUID) -> UserRole | None:
        with self._lock:
            entrada = self._roles.get(user_id)
            if entrada is None:
                return None
            rol, caduca = entrada
            if self._reloj() >= caduca:
                del self._roles[user_id]
                return None
            self._roles.move_to_end(user_id)
            return rol

    def put(self, user_id: UUID, rol: UserRole) -> None:
        with self._lock:
            self._roles[user_id] = (rol, self._reloj() + self._ttl)
            self._roles.move_to_end(user_id)
            while len(self._roles) > self._tamano:
                self._roles.popitem(last=False)


class IdentifyUser:
    """Convierte un token en un `AuthenticatedUser` con su rol.

    Son dos pasos porque el JWT de Supabase no trae nuestro rol: primero se
    verifica la firma del token y despues se lee `public.profiles`. La firma se
    verifica **siempre**; lo que se recuerda un minuto es solo el rol.
    """

    def __init__(
        self,
        tokens: TokenVerifier,
        profiles: ProfileRepository,
        *,
        role_ttl_seconds: float = ROLE_TTL_SECONDS,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._tokens = tokens
        self._profiles = profiles
        self._roles = (
            _RolesRecientes(role_ttl_seconds, ROLE_CACHE_SIZE, reloj)
            if role_ttl_seconds > 0
            else None
        )

    def execute(self, token: str) -> AuthenticatedUser:
        """Identifica al portador del token.

        Raises:
            AuthenticationError: token invalido, vencido, o usuario sin perfil.
        """
        claims = self._tokens.verify(token)

        role = self._roles.get(claims.user_id) if self._roles else None
        if role is None:
            role = self._profiles.get_role(claims.user_id)
            if role is None:
                # Existe en Auth pero no en profiles. No se le asigna un rol por
                # defecto: adivinar aqui es como se acaba dando permisos de
                # docente a quien no los tiene. Y no se recuerda: quien se acaba
                # de registrar tiene que poder reintentar enseguida.
                raise AuthenticationError(
                    "El usuario no tiene perfil en el sistema. Si acabas de registrarte, "
                    "vuelve a intentarlo; si persiste, avisa al docente."
                )
            if self._roles:
                self._roles.put(claims.user_id, role)

        return AuthenticatedUser(id=claims.user_id, role=role, email=claims.email)
