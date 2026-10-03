#!/usr/bin/env python3
"""Worker minimo que consume la cola de trabajos.

Existe para **demostrar el flujo completo** antes de que haya modelos: la app del
estudiante manda un `speech_detected`, la API lo guarda y lo encola, y este
proceso lo recibe y lo imprime. Si esto funciona, el unico trabajo que queda en
`services/ai` es el analisis en si.

Lo levanta `docker compose up` como servicio `ai-worker`. A mano:

    REDIS_URL=redis://localhost:6379/0 python worker_stub.py

Pierreluiggi: sustituye esto por el worker real cuando `tasks.analyze_audio`
haga el trabajo de verdad. La estructura (colas, reintentos) no deberia cambiar.
"""

from __future__ import annotations

import logging
import os
import sys

from redis import Redis
from rq import Queue, Worker

#: Las mismas colas que usa la API (ver el adaptador `redis_queue/job_queue.py`).
#: `high` va primero: la verificacion facial tiene a alguien esperando en pantalla,
#: el analisis de audio no.
QUEUES = ["high", "audio"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)
logger = logging.getLogger("worker")


def main() -> int:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    connection = Redis.from_url(redis_url)
    try:
        connection.ping()
    except Exception as exc:
        logger.error("No se pudo conectar a Redis en %s: %s", redis_url, exc)
        return 1

    logger.info("Conectado a Redis. Escuchando las colas: %s", ", ".join(QUEUES))
    logger.info("Esperando trabajos. Manda un evento speech_detected a la API.")

    worker = Worker(
        [Queue(name, connection=connection) for name in QUEUES],
        connection=connection,
    )
    worker.work(with_scheduler=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
