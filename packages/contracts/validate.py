#!/usr/bin/env python3
"""Valida que todos los examples/*.json cumplan event.schema.json.

Lo corre el CI (job `contracts`) y se puede correr a mano:

    python packages/contracts/validate.py

Requiere `jsonschema`:

    pip install jsonschema
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover
    sys.exit("Falta la dependencia `jsonschema`. Instalala con: pip install jsonschema")

AQUI = Path(__file__).resolve().parent
ESQUEMA = AQUI / "event.schema.json"
EJEMPLOS = AQUI / "examples"


def main() -> int:
    esquema = json.loads(ESQUEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(esquema)
    validador = Draft202012Validator(esquema, format_checker=FormatChecker())

    archivos = sorted(EJEMPLOS.glob("*.json"))
    if not archivos:
        print(f"No hay ejemplos en {EJEMPLOS}", file=sys.stderr)
        return 1

    # Cada event_type del enum necesita su ejemplo: es lo que la app, la web y las
    # pruebas de la API usan como cuerpo de referencia.
    tipos_schema = set(esquema["properties"]["event_type"]["enum"])
    tipos_vistos: set[str] = set()
    fallos = 0

    for archivo in archivos:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        errores = sorted(validador.iter_errors(datos), key=lambda e: list(e.path))
        if errores:
            fallos += 1
            print(f"FALLA  {archivo.name}")
            for error in errores:
                ruta = ".".join(str(p) for p in error.path) or "(raiz)"
                print(f"       {ruta}: {error.message}")
            continue

        if archivo.stem != datos["event_type"]:
            fallos += 1
            print(
                f"FALLA  {archivo.name}: el nombre del archivo no coincide con "
                f"event_type={datos['event_type']!r}"
            )
            continue

        tipos_vistos.add(datos["event_type"])
        print(f"ok     {archivo.name}")

    faltantes = sorted(tipos_schema - tipos_vistos)
    if faltantes:
        fallos += 1
        print(f"FALTAN ejemplos para: {', '.join(faltantes)}")

    if fallos:
        print(f"\n{fallos} problema(s).")
        return 1

    print(f"\n{len(archivos)} ejemplos validos, uno por cada event_type.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
