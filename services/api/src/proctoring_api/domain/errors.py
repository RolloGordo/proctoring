"""Errores del dominio.

Son errores de **regla de negocio**, no de forma. Un cuerpo mal formado lo rechaza
el adaptador HTTP antes de llegar aqui (422); lo que llega aqui ya tiene la forma
correcta pero viola una regla, y el adaptador lo traduce al codigo que toque.

| Error | HTTP | Significado |
|---|---|---|
| `InvalidEventError` | 400 | el evento no cumple una regla del dominio |
| `AuthenticationError` | 401 | no se pudo saber quien eres |
| `AuthorizationError` | 403 | se sabe quien eres, y no puedes hacer esto |
"""

from __future__ import annotations


class DomainError(Exception):
    """Base de todos los errores de dominio."""


class InvalidEventError(DomainError):
    """Un evento de proctoring no cumple las reglas del dominio."""


class AuthenticationError(DomainError):
    """No se pudo identificar al usuario: falta el token, es invalido o vencio."""


class AuthorizationError(DomainError):
    """El usuario esta identificado pero no puede realizar esta accion."""
