"""Compara corridas: latencia, errores, rendimiento y CPU, en tablas Markdown.

    uv run python comparar.py mil-1r mil-2r mil-4r

Lee `resultados/<nombre>_stats.csv` (Locust) y `resultados/<nombre>-recursos.csv`
(`recursos.py`). Las cifras del informe salen de aquí, no copiadas a mano.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

RESULTADOS = Path(__file__).resolve().parent / "resultados"
CLAVE = [
    "ingreso: código",
    "sala de espera: mi estado",
    "examen: preguntas",
    "examen: guardar respuestas",
    "examen: señal de supervisión",
    "entrega",
    "docente: sala de espera",
]


def stats(nombre: str) -> dict[str, dict[str, str]]:
    with (RESULTADOS / f"{nombre}_stats.csv").open(encoding="utf-8", errors="replace") as f:
        filas = list(csv.DictReader(f))
    # Locust en Windows escribe el CSV en la página de códigos de la consola:
    # se emparejan los nombres por su versión sin tildes.
    return {_llano(fila["Name"]): fila for fila in filas}


def _llano(texto: str) -> str:
    return "".join(c for c in texto if c.isascii() and c != "�")


def cpu(nombre: str) -> dict[str, tuple[float, float]]:
    """CPU media y máxima por grupo, sumando réplicas en cada instante."""
    ruta = RESULTADOS / f"{nombre}-recursos.csv"
    if not ruta.exists():
        return {}
    por_instante: dict[tuple[str, str], float] = defaultdict(float)
    with ruta.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            por_instante[(fila["grupo"], fila["t"])] += float(fila["cpu_pct"])
    grupos: dict[str, list[float]] = defaultdict(list)
    for (grupo, _), valor in por_instante.items():
        grupos[grupo].append(valor)
    return {g: (sum(v) / len(v), max(v)) for g, v in grupos.items()}


def main(nombres: list[str]) -> None:
    datos = {n: stats(n) for n in nombres}
    print("| Corrida | Peticiones | Errores | Peticiones/s | p50 | p95 | p99 |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for n in nombres:
        t = datos[n]["Aggregated"]
        errores = int(t["Failure Count"]) / max(int(t["Request Count"]), 1)
        print(
            f"| {n} | {int(t['Request Count']):,} | {int(t['Failure Count'])} ({errores:.2%}) "
            f"| {float(t['Requests/s']):.1f} | {t['50%']} ms | {t['95%']} ms | {t['99%']} ms |"
        )

    print("\n**p95 por endpoint (ms)**\n")
    print("| Endpoint | " + " | ".join(nombres) + " |")
    print("|---|" + "---:|" * len(nombres))
    for endpoint in CLAVE:
        celdas = [datos[n].get(_llano(endpoint), {}).get("95%", "—") for n in nombres]
        print(f"| {endpoint} | " + " | ".join(celdas) + " |")

    print("\n**CPU (% de un núcleo; media / máximo)**\n")
    grupos = ["api (réplicas)", "postgrest", "postgres", "kong"]
    print("| Corrida | " + " | ".join(grupos) + " |")
    print("|---|" + "---:|" * len(grupos))
    for n in nombres:
        c = cpu(n)
        celdas = [f"{c[g][0]:.0f} / {c[g][1]:.0f}" if g in c else "—" for g in grupos]
        print(f"| {n} | " + " | ".join(celdas) + " |")


if __name__ == "__main__":
    main(sys.argv[1:])
