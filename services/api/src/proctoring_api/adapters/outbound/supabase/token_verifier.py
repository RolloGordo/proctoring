"""Verificacion de los JWT que emite Supabase Auth.

El proyecto usa **claves asimetricas ES256** y publica la parte publica en
`/auth/v1/.well-known/jwks.json`. Eso significa que la API verifica firmas sin
conocer ningun secreto: aunque alguien robara la configuracion de este servicio,
no podria falsificar un token.

Las claves se cachean en memoria con un tiempo de vida, para no pedir el JWKS en
cada peticion (eso metaria una llamada de red en el camino mas caliente del
sistema, que es justo el POST de eventos).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import jwt
from jwt import PyJWKClient

from proctoring_api.application.ports.token_verifier import TokenClaims
from proctoring_api.domain.errors import AuthenticationError

#: Supabase emite ES256 en proyectos nuevos y RS256 en algunos migrados.
#: La lista es cerrada a proposito: aceptar "el que diga el token" es como se
#: cuelan los ataques de confusion de algoritmo (alg=none, alg=HS256 con la
#: clave publica como secreto).
ALLOWED_ALGORITHMS = ["ES256", "RS256"]

#: Claim `aud` que pone Supabase para un usuario que inicio sesion.
AUDIENCE = "authenticated"

logger = logging.getLogger(__name__)

#: Cuanto se cachea el JWKS antes de volver a pedirlo.
JWKS_LIFESPAN_SECONDS = 600


class SupabaseTokenVerifier:
    """Implementacion de `TokenVerifier` contra el JWKS del proyecto."""

    def __init__(self, project_url: str, *, jwks_lifespan: int = JWKS_LIFESPAN_SECONDS) -> None:
        base = project_url.rstrip("/")
        self._issuer = f"{base}/auth/v1"
        self._jwks_client = PyJWKClient(
            f"{base}/auth/v1/.well-known/jwks.json",
            cache_keys=True,
            lifespan=jwks_lifespan,
        )

    def verify(self, token: str) -> TokenClaims:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            payload: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=AUDIENCE,
                issuer=self._issuer,
                # Sin `sub` no hay a quien atribuir el evento; sin `exp` el token
                # no caduca nunca.
                options={"require": ["exp", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("La sesion expiro; vuelve a iniciar sesion") from exc
        except jwt.PyJWKClientConnectionError as exc:
            # De verdad no se pudo: el JWKS de Supabase no respondió.
            logger.warning("No se pudo traer el JWKS de Supabase: %s", exc)
            raise AuthenticationError("No se pudo verificar el token en este momento") from exc
        except (jwt.InvalidTokenError, jwt.PyJWKClientError) as exc:
            # SEC-07: el detalle va al log, no a la respuesta. Antes se devolvía
            # tal cual («Invalid header string: 'utf-8' codec can't decode…»),
            # y un token falsificado sin `kid` contestaba «no se pudo verificar
            # en este momento», como si fuera un fallo pasajero.
            logger.info("Token rechazado: %s", exc)
            raise AuthenticationError("Sesion invalida; vuelve a iniciar sesion") from exc
        except Exception as exc:
            logger.warning("Fallo inesperado al verificar un token: %s", exc)
            raise AuthenticationError("No se pudo verificar el token en este momento") from exc

        try:
            user_id = UUID(payload["sub"])
        except (KeyError, ValueError) as exc:
            raise AuthenticationError("El token no identifica a un usuario valido") from exc

        email = payload.get("email")
        return TokenClaims(user_id=user_id, email=email if isinstance(email, str) else None)
