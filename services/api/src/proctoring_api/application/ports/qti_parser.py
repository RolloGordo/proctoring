"""Puerto del analizador de QTI.

El analizador es un **adaptador de entrada**: traduce un formato externo a lo
que la aplicación entiende. El caso de uso no puede importarlo —la regla de
dependencias va de adaptadores a aplicación, nunca al revés— así que se declara
aquí su forma y se inyecta.

Que sea un puerto tiene además un efecto práctico: el caso de uso se prueba con
un analizador falso, sin escribir XML, y el XML se prueba en el adaptador.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class QtiIssue(Protocol):
    """Un ítem que no se pudo convertir, o que se califica distinto aquí."""

    @property
    def item_id(self) -> str: ...

    @property
    def reason(self) -> str: ...


class QtiParseResult(Protocol):
    """Lo que devuelve el analizador.

    `questions` son diccionarios y no entidades a propósito: el analizador es
    puro y no conoce el dominio. Traducirlos es trabajo del caso de uso.
    """

    @property
    def questions(self) -> Sequence[Mapping[str, Any]]: ...

    @property
    def issues(self) -> Sequence[QtiIssue]: ...

    @property
    def warnings(self) -> Sequence[QtiIssue]: ...


class QtiParser(Protocol):
    """Lee un archivo QTI 2.1.

    Raises:
        ValueError: si el archivo no es QTI 2.1 legible. Un ítem suelto que no
            se entienda **no** es esto: eso vuelve en `issues`, para que importar
            cuarenta preguntas no falle por una.
    """

    def __call__(self, xml: bytes) -> QtiParseResult: ...
