"""Errores del dominio.

Son errores de **regla de negocio**, no de forma. Un cuerpo mal formado lo rechaza
el adaptador HTTP antes de llegar aqui (422); lo que llega aqui ya tiene la forma
correcta pero viola una regla, y el adaptador lo traduce a 400.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base de todos los errores de dominio."""


class InvalidEventError(DomainError):
    """Un evento de proctoring no cumple las reglas del dominio."""
