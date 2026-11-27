"""Registra cada caso con su identificador, técnica y descripción para el informe.

Cada prueba documenta en su docstring `ID | técnica | lo que se espera`. Al terminar
se escribe `RESULTADOS` (JSON) con eso, el resultado y la duración: es la materia
prima del informe en PDF, así que el informe no puede decir nada que no haya corrido.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

_casos: list[dict[str, Any]] = []
_inicio = time.time()


def _partes(item: pytest.Item) -> tuple[str, str, str]:
    doc = (getattr(item, "function", None).__doc__ or "").strip() if hasattr(item, "function") else ""
    primera, _, resto = doc.partition("\n")
    trozos = [t.strip() for t in primera.split("|")]
    if len(trozos) >= 3:
        return trozos[0], trozos[1], " | ".join(trozos[2:]) + (" " + " ".join(resto.split()) if resto else "")
    return item.name, "", doc


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):  # type: ignore[no-untyped-def]
    resultado = yield
    informe = resultado.get_result()
    if informe.when == "call" or (informe.when == "setup" and informe.outcome != "passed"):
        ident, tecnica, descripcion = _partes(item)
        detalle = ""
        if informe.failed and os.environ.get("CAPTURAS"):
            # En E2E, la pantalla en el momento del fallo: lo que vería quien depura.
            for nombre, valor in getattr(item, "funcargs", {}).items():
                if hasattr(valor, "screenshot") and hasattr(valor, "url"):
                    try:
                        ruta = Path(os.environ["CAPTURAS"]) / f"FALLO-{item.name}-{nombre}.png"
                        valor.screenshot(path=str(ruta), full_page=True)
                        item.user_properties.append(("evidencia", str(ruta)))
                    except Exception:  # noqa: BLE001 - la captura no debe tapar el fallo real
                        pass
        if informe.failed:
            crash = getattr(informe.longrepr, "reprcrash", None)
            detalle = (crash.message if crash else str(informe.longrepr)).strip().splitlines()[0][:400]
        elif informe.skipped and isinstance(informe.longrepr, tuple):
            detalle = str(informe.longrepr[2])[:400]
        _casos.append(
            {
                "id": ident,
                "tecnica": tecnica,
                "descripcion": descripcion,
                "archivo": item.nodeid.split("::")[0],
                "prueba": item.name,
                "resultado": informe.outcome,
                "segundos": round(informe.duration, 3),
                "detalle": detalle,
                "evidencia": [v for k, v in item.user_properties if k == "evidencia"],
                "medidas": {k[7:]: v for k, v in item.user_properties if k.startswith("medida_")},
            }
        )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    destino = os.environ.get("RESULTADOS")
    if not destino:
        return
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    Path(destino).write_text(
        json.dumps(
            {
                "inicio": _inicio,
                "fin": time.time(),
                "api": os.environ.get("API_URL", ""),
                "casos": _casos,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
