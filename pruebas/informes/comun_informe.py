"""Piezas que comparten los informes armados desde los JSON de `pruebas/conftest.py`."""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

from plantilla import e, estado, imagen, tabla


def cargar(ruta: Path) -> dict[str, Any]:
    return json.loads(ruta.read_text(encoding="utf-8"))


def fecha(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")


def agrupar(casos: list[dict[str, Any]]) -> "OrderedDict[str, dict[str, Any]]":
    """Un caso con variantes (parametrizado) cuenta como un caso con N variantes."""
    g: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for c in casos:
        x = g.setdefault(
            c["id"],
            {"id": c["id"], "tecnica": c["tecnica"], "descripcion": c["descripcion"], "variantes": 0, "pasan": 0, "fallas": [], "segundos": 0.0, "evidencia": []},
        )
        x["variantes"] += 1
        x["segundos"] += c["segundos"]
        x["evidencia"] += c.get("evidencia", [])
        if c["resultado"] == "passed":
            x["pasan"] += 1
        else:
            x["fallas"].append(c.get("detalle") or c["prueba"])
    return g


def tabla_casos(grupos: "OrderedDict[str, dict[str, Any]]", con_tecnica: bool = True, etiqueta: str = "Técnica") -> str:
    filas = []
    for x in grupos.values():
        res = estado("passed") if not x["fallas"] else estado("failed")
        variantes = f"{x['pasan']}/{x['variantes']}" if x["variantes"] > 1 else ""
        fila = [f'<b style="white-space:nowrap">{e(x["id"])}</b>']
        if con_tecnica:
            fila.append(e(x["tecnica"]))
        fila += [e(x["descripcion"]), variantes, res]
        filas.append(fila)
    cab = ["ID"] + ([etiqueta] if con_tecnica else []) + ["Caso y resultado esperado", "Variantes", "Resultado"]
    return tabla(cab, filas, ())


def galeria(grupos: "OrderedDict[str, dict[str, Any]]", base: Path) -> str:
    partes = []
    for x in grupos.values():
        for ruta in x["evidencia"]:
            p = base / Path(ruta).name
            if p.exists() and not p.name.startswith("FALLO"):
                partes.append(imagen(p, f"{x['id']} · {x['descripcion']}"))
    return "".join(partes)
