"""Traduccion de errores del dominio a respuestas HTTP.

Starlette busca el manejador recorriendo la jerarquia de la excepcion, asi que
los registrados para las subclases ganan al de `DomainError`.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from proctoring_api.domain.errors import (
    AuthenticationError,
    AuthorizationError,
    DomainError,
)


async def domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """`DomainError` -> 400 con el mensaje tal cual.

    400 y no 422: el cuerpo tenia la forma correcta (eso ya lo valido Pydantic) y
    lo que fallo fue una regla de negocio. La distincion importa para quien integra
    la app de escritorio: 422 es "arregla el JSON", 400 es "arregla la logica".
    """
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def authentication_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """`AuthenticationError` -> 401. No sabemos quien eres."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def authorization_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """`AuthorizationError` -> 403. Sabemos quien eres, y no puedes hacer esto."""
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AuthenticationError, authentication_error_handler)
    app.add_exception_handler(AuthorizationError, authorization_error_handler)
    app.add_exception_handler(DomainError, domain_error_handler)
