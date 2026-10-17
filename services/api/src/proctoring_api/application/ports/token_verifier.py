"""Puerto de verificacion de tokens."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Lo que el token dice del usuario, ya verificado.

    Deliberadamente pequeno: solo lo que la API necesita. El rol **no** esta aqui
    porque el JWT de Supabase no lo trae; se lee de `public.profiles`.
    """

    user_id: UUID
    email: str | None = None


class TokenVerifier(Protocol):
    """Comprueba que un token sea autentico y no haya vencido."""

    def verify(self, token: str) -> TokenClaims:
        """Verifica la firma y la vigencia del token.

        Raises:
            AuthenticationError: si el token es invalido, vencio o no se puede
                verificar su firma.
        """
        ...
