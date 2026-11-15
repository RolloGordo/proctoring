"""Leer todas las filas de una consulta, de mil en mil.

PostgREST corta cada respuesta en `max_rows` filas (1000 en Supabase, local y
en la nube) y no avisa: la respuesta llega con 200 y simplemente le faltan
filas. En la carga de infracciones del 14/11/2026 un examen de 60 estudiantes
juntó 2520 señales; la API devolvía las 1000 más viejas, así que las nuevas no
aparecían en «Todas las señales» y el semáforo se calculaba con datos a medias.

Por eso las listas que crecen con el examen se leen por páginas hasta que una
llega incompleta. La consulta se construye de nuevo en cada página: el
constructor de postgrest acumula parámetros y reusarlo repetiría el rango.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

#: Igual al `max_rows` de Supabase: pedir más no sirve, el servidor recorta.
PAGINA = 1000


def todas_las_filas(consulta: Callable[[], Any], pagina: int | None = None) -> list[dict[str, Any]]:
    """Ejecuta `consulta()` por rangos y junta las filas, en el orden que pida."""
    pagina = pagina or PAGINA
    filas: list[dict[str, Any]] = []
    while True:
        respuesta = consulta().range(len(filas), len(filas) + pagina - 1).execute()
        lote = cast("list[dict[str, Any]]", respuesta.data)
        filas.extend(lote)
        if len(lote) < pagina:
            return filas
