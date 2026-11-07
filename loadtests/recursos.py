"""Mide CPU y memoria de cada contenedor mientras corre la carga.

La latencia que ve Locust dice *que* algo va lento; esto dice *dónde*: si la
réplica está al 100 % de su CPU, falta escalar la API; si lo está la base,
añadir réplicas no va a ayudar. Escribe un CSV y, al terminar, un resumen.

    uv run python recursos.py resultados/mil-4r-recursos.csv   # Ctrl+C o matar para parar
"""

from __future__ import annotations

import csv
import json
import signal
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

#: Qué contenedores interesan y con qué nombre se agrupan.
GRUPOS = {
    "carga-api": "api (réplicas)",
    "carga-lb": "balanceador",
    "carga-redis": "redis",
    "supabase_db": "postgres",
    "supabase_rest": "postgrest",
    "supabase_kong": "kong",
    "supabase_auth": "auth",
}


def grupo(nombre: str) -> str | None:
    return next((g for prefijo, g in GRUPOS.items() if nombre.startswith(prefijo)), None)


def megas(texto: str) -> float:
    valor, unidad = texto.split("/")[0].strip()[:-3], texto.split("/")[0].strip()[-3:]
    return float(valor) * {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024}.get(unidad, 1)


def main(destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    filas: list[dict[str, object]] = []
    seguir = True

    def parar(*_: object) -> None:
        nonlocal seguir
        seguir = False

    signal.signal(signal.SIGINT, parar)
    signal.signal(signal.SIGTERM, parar)
    inicio = time.time()
    while seguir:
        salida = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        t = round(time.time() - inicio, 1)
        for linea in salida.splitlines():
            d = json.loads(linea)
            g = grupo(d["Name"])
            if g:
                filas.append(
                    {
                        "t": t,
                        "contenedor": d["Name"],
                        "grupo": g,
                        "cpu_pct": float(d["CPUPerc"].rstrip("%")),
                        "mem_mib": round(megas(d["MemUsage"]), 1),
                    }
                )
        with destino.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["t", "contenedor", "grupo", "cpu_pct", "mem_mib"])
            w.writeheader()
            w.writerows(filas)
        time.sleep(2)

    resumen(filas)


def resumen(filas: list[dict[str, object]]) -> None:
    """Por grupo: CPU media y máxima (sumando réplicas en cada instante) y memoria máxima."""
    por_instante: dict[tuple[str, float], list[dict[str, object]]] = defaultdict(list)
    for f in filas:
        por_instante[(str(f["grupo"]), float(f["t"]))].append(f)  # type: ignore[arg-type]
    print(
        f"{'grupo':<16}{'CPU media %':>12}{'CPU máx %':>11}{'máx por contenedor %':>22}{'mem máx MiB':>13}"
    )
    for g in sorted({k[0] for k in por_instante}):
        sumas = [
            sum(float(x["cpu_pct"]) for x in v) for (gg, _), v in por_instante.items() if gg == g
        ]  # type: ignore[arg-type]
        individuales = [float(f["cpu_pct"]) for f in filas if f["grupo"] == g]  # type: ignore[arg-type]
        memoria = max(float(f["mem_mib"]) for f in filas if f["grupo"] == g)  # type: ignore[arg-type]
        print(
            f"{g:<16}{sum(sumas) / len(sumas):>12.0f}{max(sumas):>11.0f}"
            f"{max(individuales):>22.0f}{memoria:>13.0f}"
        )


def resumir(origen: Path) -> None:
    with origen.open(encoding="utf-8") as f:
        resumen(list(csv.DictReader(f)))


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "resumir":
        resumir(Path(sys.argv[2]))
    else:
        main(Path(sys.argv[1] if len(sys.argv) > 1 else "resultados/recursos.csv"))
