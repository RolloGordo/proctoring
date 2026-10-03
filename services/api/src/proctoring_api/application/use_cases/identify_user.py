"""Caso de uso: identificar al usuario que hace la peticion."""

from __future__ import annotations

from proctoring_api.application.ports.profile_repository import ProfileRepository
from proctoring_api.application.ports.token_verifier import TokenVerifier
from proctoring_api.domain.errors import AuthenticationError
from proctoring_api.domain.user import AuthenticatedUser


class IdentifyUser:
    """Convierte un token en un `AuthenticatedUser` con su rol.

    Son dos pasos porque el JWT de Supabase no trae nuestro rol: primero se
    verifica la firma del token y despues se lee `public.profiles`.
    """

    def __init__(self, tokens: TokenVerifier, profiles: ProfileRepository) -> None:
        self._tokens = tokens
        self._profiles = profiles

    def execute(self, token: str) -> AuthenticatedUser:
        """Identifica al portador del token.

        Raises:
            AuthenticationError: token invalido, vencido, o usuario sin perfil.
        """
        claims = self._tokens.verify(token)

        role = self._profiles.get_role(claims.user_id)
        if role is None:
            # Existe en Auth pero no en profiles. No se le asigna un rol por
            # defecto: adivinar aqui es como se acaba dando permisos de docente
            # a quien no los tiene.
            raise AuthenticationError(
                "El usuario no tiene perfil en el sistema. Si acabas de registrarte, "
                "vuelve a intentarlo; si persiste, avisa al docente."
            )

        return AuthenticatedUser(id=claims.user_id, role=role, email=claims.email)
