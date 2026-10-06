"""Autenticación de los endpoints internos que usa `services/ai`.

El worker **no es un usuario**: no tiene correo ni rol, y pedirle un token de
Supabase significaría darle una cuenta con permisos sobre datos de estudiantes.
Se autentica con un **secreto compartido** en la cabecera `X-Internal-Token`.

Esto no es autenticación de usuarios de segunda: es la frontera entre dos
servicios nuestros, que ya se hablan por una cola. El secreto vale para decir
"soy el worker", nada más; estos endpoints no dejan leer evidencia de nadie.
"""

from __future__ import annotations

import secrets

from fastapi import Header, Request

from proctoring_api.config import Settings
from proctoring_api.domain.errors import AuthenticationError

HEADER = "X-Internal-Token"


def verify_internal_token(
    request: Request,
    x_internal_token: str | None = Header(default=None, alias=HEADER),
) -> None:
    """Comprueba el secreto del servicio interno.

    Sin `INTERNAL_API_TOKEN` configurado, los endpoints internos solo funcionan
    con la autenticación desactivada (desarrollo local). `create_app` se niega a
    arrancar sin el secreto en cualquier otro caso, así que esto no puede quedar
    abierto por olvido en un despliegue.

    Raises:
        AuthenticationError: si falta el secreto o no coincide.
    """
    settings: Settings = request.app.state.settings
    esperado = settings.internal_api_token

    if not esperado:
        if settings.auth_enabled:
            raise AuthenticationError("Los endpoints internos no estan configurados")
        return

    if x_internal_token is None:
        raise AuthenticationError(f"Falta la cabecera {HEADER}")

    # Comparación en tiempo constante: comparar con `!=` filtra, por el tiempo
    # que tarda, cuántos caracteres iniciales acertó quien lo intenta.
    if not secrets.compare_digest(x_internal_token, esperado):
        raise AuthenticationError("Token interno invalido")
