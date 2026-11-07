"""Una corrida completa y repetible: escala, siembra, mide y carga.

    uv run python correr.py --nombre mil-4r --examenes 17 --por-examen 60 --replicas 4

1. Deja la API con `--replicas` copias detrás del balanceador.
2. Siembra un escenario nuevo (cada estudiante rinde una sola vez, así que no
   se reutiliza el de la corrida anterior).
3. Mide CPU y memoria de cada contenedor mientras dura la carga.
4. Corre Locust sin interfaz y guarda CSV y HTML en `resultados/`.

Sale con el código de Locust: 1 si se rompió un presupuesto.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RESULTADOS = AQUI / "resultados"
COMPOSE = ["docker", "compose", "-f", str(AQUI / "docker-compose.carga.yml"), "-p", "carga"]


def sh(*args: str, **kw: object) -> None:
    subprocess.run(list(args), check=True, cwd=AQUI, **kw)  # type: ignore[arg-type]


def esperar_api(replicas: int) -> None:
    """Hasta que las réplicas respondan por el balanceador (y nginx las haya visto)."""
    limite = time.time() + 90
    while time.time() < limite:
        try:
            with urllib.request.urlopen("http://localhost:8080/health", timeout=3) as r:
                if r.status == 200:
                    # nginx vuelve a resolver el nombre cada 5 s: margen para
                    # que entren todas las réplicas nuevas.
                    time.sleep(8)
                    return
        except OSError:
            pass
        time.sleep(2)
    sys.exit(f"La API con {replicas} réplicas no respondió en 90 s")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--nombre", required=True)
    p.add_argument("--examenes", type=int, default=17)
    p.add_argument("--por-examen", type=int, default=60)
    p.add_argument("--docentes", type=int, default=0, help="0: uno por examen")
    p.add_argument("--replicas", type=int, default=1)
    p.add_argument("--duracion-examen", type=int, default=240, help="segundos rindiendo")
    p.add_argument("--margen-entrega", type=int, default=60)
    p.add_argument("--ingreso-por-segundo", type=int, default=50)
    a = p.parse_args()

    RESULTADOS.mkdir(exist_ok=True)
    sh(*COMPOSE, "up", "-d", "--scale", f"api={a.replicas}")
    esperar_api(a.replicas)

    sh(
        "uv",
        "run",
        "python",
        "preparar.py",
        "datos",
        "--examenes",
        str(a.examenes),
        "--por-examen",
        str(a.por_examen),
        "--docentes",
        str(a.docentes or a.examenes),
    )

    usuarios = a.examenes * a.por_examen + a.examenes
    # Ingreso + sala de espera + examen + entrega + margen para que acaben todos.
    segundos = usuarios // a.ingreso_por_segundo + 40 + a.duracion_examen + a.margen_entrega + 30
    entorno = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "EXAMEN_SEGUNDOS": str(a.duracion_examen),
        "MARGEN_ENTREGA_SEGUNDOS": str(a.margen_entrega),
    }
    csv_recursos = RESULTADOS / f"{a.nombre}-recursos.csv"
    muestreo = subprocess.Popen(
        [sys.executable, "recursos.py", str(csv_recursos)], cwd=AQUI, env=entorno
    )
    try:
        codigo = subprocess.run(
            [
                "uv",
                "run",
                "locust",
                "-f",
                "locustfile.py",
                "--headless",
                "-H",
                "http://localhost:8080",
                "-u",
                str(usuarios),
                "-r",
                str(a.ingreso_por_segundo),
                "-t",
                f"{segundos}s",
                "--only-summary",
                "--csv",
                str(RESULTADOS / a.nombre),
                "--html",
                str(RESULTADOS / f"{a.nombre}.html"),
            ],
            cwd=AQUI,
            env=entorno,
            check=False,
        ).returncode
    finally:
        muestreo.terminate()
        muestreo.wait(timeout=10)

    print(f"\n== Recursos durante «{a.nombre}» ({a.replicas} réplica(s)) ==")
    subprocess.run(
        ["uv", "run", "python", "recursos.py", "resumir", str(csv_recursos)],
        cwd=AQUI,
        env=entorno,
        check=False,
    )
    return codigo


if __name__ == "__main__":
    sys.exit(main())
