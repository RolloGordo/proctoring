"""Traduccion de errores del dominio a respuestas HTTP."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from proctoring_api.domain.errors import DomainError


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


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
