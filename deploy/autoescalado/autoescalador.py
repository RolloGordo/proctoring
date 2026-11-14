"""Autoescalador horizontal de la API (pedido del profesor: «levantar servicios según la carga»).

Cada `--intervalo` segundos mide la CPU de las réplicas de la API y, según la
media, añade o quita una réplica entre `--min` y `--max`:

- **Sube** si la CPU media por réplica pasa de `--subir` (70 %) en las últimas
  `VENTANA_SUBIR` mediciones (45 s): una ráfaga corta no basta.
- **Baja** si se queda por debajo de `--bajar` (25 %) durante `VENTANA_BAJAR`
  mediciones (3 min): bajar con prisa y volver a subir es peor que sobrar un rato.
- Tras cada cambio espera (`ENFRIAR_*`) a que la réplica nueva arranque y el
  balanceador la incluya, para no decidir sobre una medida que todavía no la ve.

100 % es un núcleo, igual que en `docker stats`; cada réplica tiene un tope de
un núcleo, así que la media por réplica va de 0 a 100.

Funciona con cualquier orquestador: `--patron` dice qué contenedores son
réplicas y `--comando` cómo escalar (`{n}` es el número nuevo). En producción,
`docker service scale api-m4kgbc={n}` (Swarm, de Dokploy); en la prueba de
carga, `docker compose -p carga up -d --scale api={n} --no-recreate`.

Cada decisión queda en `--registro` (CSV), que es la evidencia del informe.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

VENTANA_SUBIR = 3
VENTANA_BAJAR = 12
ENFRIAR_TRAS_SUBIR_S = 45
ENFRIAR_TRAS_BAJAR_S = 120


@dataclass
class Politica:
    minimo: int = 2
    maximo: int = 5
    subir: float = 70.0
    bajar: float = 25.0


@dataclass
class Estado:
    """Lo que recuerda entre mediciones. Puro: la hora y la CPU vienen de fuera."""

    politica: Politica
    historial: deque[float] = field(default_factory=lambda: deque(maxlen=VENTANA_BAJAR))
    ultimo_cambio: float = float("-inf")

    def decidir(self, ahora: float, replicas: int, cpu_media: float) -> int:
        """Devuelve cuántas réplicas debe haber: `replicas`, una más o una menos."""
        self.historial.append(cpu_media)
        p = self.politica
        if replicas < p.minimo:
            return p.minimo
        if replicas > p.maximo:
            return p.maximo
        desde_cambio = ahora - self.ultimo_cambio
        recientes = list(self.historial)[-VENTANA_SUBIR:]
        if (
            replicas < p.maximo
            and len(recientes) == VENTANA_SUBIR
            and sum(recientes) / VENTANA_SUBIR > p.subir
            and desde_cambio >= ENFRIAR_TRAS_SUBIR_S
        ):
            return replicas + 1
        if (
            replicas > p.minimo
            and len(self.historial) == VENTANA_BAJAR
            and max(self.historial) < p.bajar
            and desde_cambio >= ENFRIAR_TRAS_BAJAR_S
        ):
            return replicas - 1
        return replicas

    def aplicado(self, ahora: float) -> None:
        """Tras escalar: empieza la espera y se olvida lo medido con el número anterior."""
        self.ultimo_cambio = ahora
        self.historial.clear()


def medir(patron: str) -> list[float]:
    """CPU de cada réplica en marcha (en % de un núcleo), según `docker stats`."""
    salida = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{.Name}} {{.CPUPerc}}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    cpus = []
    for linea in salida.splitlines():
        nombre, _, cpu = linea.partition(" ")
        if patron in nombre and cpu.endswith("%"):
            cpus.append(float(cpu.rstrip("%")))
    return cpus


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--patron", required=True, help="parte del nombre de los contenedores réplica")
    a.add_argument("--comando", required=True, help="cómo escalar; {n} es el número nuevo")
    a.add_argument("--min", type=int, default=2)
    a.add_argument("--max", type=int, default=5)
    a.add_argument("--subir", type=float, default=70.0)
    a.add_argument("--bajar", type=float, default=25.0)
    a.add_argument("--intervalo", type=float, default=15.0)
    a.add_argument("--registro", type=Path, default=Path("/var/log/proctoring-autoescalado.csv"))
    args = a.parse_args()

    estado = Estado(Politica(args.min, args.max, args.subir, args.bajar))
    nuevo = not args.registro.exists()
    with args.registro.open("a", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        if nuevo:
            escritor.writerow(["hora", "replicas", "cpu_media", "cpu_max", "decision"])
        while True:
            try:
                cpus = medir(args.patron)
            except subprocess.CalledProcessError as fallo:
                print(f"no se pudo medir: {fallo}", file=sys.stderr, flush=True)
                time.sleep(args.intervalo)
                continue
            replicas = len(cpus)
            media = sum(cpus) / replicas if replicas else 0.0
            ahora = time.monotonic()
            objetivo = estado.decidir(ahora, replicas, media) if replicas else args.min
            decision = "igual" if objetivo == replicas else f"{replicas}->{objetivo}"
            escritor.writerow([datetime.now(UTC).isoformat(timespec="seconds"), replicas, round(media, 1), round(max(cpus, default=0), 1), decision])
            f.flush()
            if objetivo != replicas:
                print(f"escalando {replicas} -> {objetivo} (CPU media {media:.0f} %)", flush=True)
                subprocess.run(args.comando.format(n=objetivo), shell=True, check=False)
                estado.aplicado(ahora)
            time.sleep(args.intervalo)


if __name__ == "__main__":
    sys.exit(main())
