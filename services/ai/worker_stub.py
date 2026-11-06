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
from time import perf_counter
from typing import Any

from redis import Redis
from rq import Queue, SimpleWorker, Worker

from audio_runtime import (
    _get_local_asr,
    asr_provider,
    check_memory_budget,
    enforce_memory_budget,
    similarity_model,
)
from salud import avisos_configuracion_asr, servir_salud


def _usar_simple_worker() -> bool:
    if sys.platform == "win32":
        return True
    return os.environ.get("WORKER_USE_SIMPLE_WORKER", "false").strip().lower() in (
        "1",
        "true",
        "yes",
    )


WorkerClass = SimpleWorker if _usar_simple_worker() else Worker

#: Las mismas colas que usa la API (ver el adaptador `redis_queue/job_queue.py`).
#: `high` va primero: la verificacion facial tiene a alguien esperando en pantalla,
#: el analisis de audio no.
QUEUES = ["high", "audio"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)
logger = logging.getLogger("worker")


def precargar_modelos(*, fork_worker: bool | None = None) -> dict[str, Any]:
    """Precarga SimilarityModel (y ASR local si no hay fork) en el proceso padre.

    RQ en Linux usa `Worker` (`os.fork()` por trabajo) salvo que se active
    `WORKER_USE_SIMPLE_WORKER=true` (`SimpleWorker`).
    - `SimilarityModel` (PyTorch) con `OMP_NUM_THREADS=1` es seguro tras `os.fork()`:
      al precargarlo en el padre, los hijos heredan las páginas en Copy-on-Write y
      ahorran la recarga de ~1.1 GiB en cada trabajo.
    - `CTranslate2` (`faster-whisper`) crea un hilo C++ (`ctranslate2::ReplicaPool`)
      en su constructor que POSIX `os.fork()` no clona al proceso hijo; invocar una
      instancia creada antes de `os.fork()` bloquea indefinidamente al hijo. Por ello,
      el ASR local solo se precarga en el padre cuando el worker no hace `fork()`
      (`SimpleWorker`), y en modo `fork` se inicializa en el hijo (con salvaguarda
      `os.register_at_fork` en `audio_runtime.py`).
    """
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    usa_fork = (not _usar_simple_worker()) if fork_worker is None else fork_worker

    resultado: dict[str, Any] = {
        "fork_worker": usa_fork,
        "asr_preloaded": False,
        "similarity_preloaded": False,
        "asr_load_seconds": 0.0,
        "similarity_load_seconds": 0.0,
    }
    try:
        if asr_provider() == "faster-whisper" and not usa_fork:
            t0 = perf_counter()
            _get_local_asr()
            resultado["asr_preloaded"] = True
            resultado["asr_load_seconds"] = round(perf_counter() - t0, 4)
            logger.info(
                "Modelo ASR local precargado en el proceso padre (SimpleWorker) en %.3f s",
                resultado["asr_load_seconds"],
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo precargar el modelo ASR local al arrancar: %s", exc)

    try:
        t0 = perf_counter()
        similarity_model()
        resultado["similarity_preloaded"] = True
        resultado["similarity_load_seconds"] = round(perf_counter() - t0, 4)
        logger.info(
            "SimilarityModel precargado en el proceso padre en %.3f s",
            resultado["similarity_load_seconds"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo precargar SimilarityModel al arrancar: %s", exc)

    return resultado


def main() -> int:
    try:
        mem_status = enforce_memory_budget()
        if mem_status["memory_sufficient"]:
            logger.info(
                "Presupuesto de memoria verificado: modo=%s motor=%s sim=%s "
                "limite_mib=%s requerido_mib=%s",
                mem_status["asr_mode"],
                mem_status["asr_provider"],
                mem_status["similarity_backend"],
                mem_status["memory_limit_mib"],
                mem_status["required_memory_mib"],
            )
    except (RuntimeError, ValueError) as exc:
        logger.error("Fallo de comprobación previa al arranque: %s", exc)
        return 1

    for aviso in avisos_configuracion_asr():
        logger.warning("Aviso de configuración ASR: %s", aviso)

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    connection = Redis.from_url(redis_url)
    try:
        connection.ping()
    except Exception as exc:
        logger.error("No se pudo conectar a Redis en %s: %s", redis_url, exc)
        return 1

    if os.environ.get("WORKER_PRELOAD_MODELS", "true").strip().lower() not in (
        "0",
        "false",
        "no",
    ):
        precargar_modelos()

    logger.info("Conectado a Redis. Escuchando las colas: %s", ", ".join(QUEUES))
    logger.info("Esperando trabajos. Manda un evento speech_detected a la API.")

    # Prueba de vida para la plataforma. El worker no sirve peticiones, y tanto
    # los Spaces de Hugging Face como los Web Services de Render dan por caido
    # un contenedor sin puerto abierto y lo reinician en bucle.
    servir_salud(lambda: _estado(connection))

    worker = WorkerClass(
        [Queue(name, connection=connection) for name in QUEUES],
        connection=connection,
    )
    worker.work(with_scheduler=False)
    return 0


#: Lo que el worker necesita del entorno para hacer su trabajo.
#:
#: Sin estas no puede bajar de Storage ni devolverle el resultado a la API, asi
#: que un trabajo falla en cuanto lo coge. Antes eso solo se sabia provocando el
#: fallo y leyendo los registros, y «creo que las puse bien» no es una respuesta
#: que se pueda comprobar.
REQUERIDAS = (
    "REDIS_URL",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "PROCTORING_API_URL",
    "INTERNAL_API_TOKEN",
)


def _configuracion() -> dict[str, bool]:
    """Que variables estan puestas. **Solo si estan, nunca su valor.**

    El endpoint de salud es publico: lo sondea la plataforma. Devolver aqui el
    valor de una clave de servicio seria regalarla, asi que esto es un si o un
    no por nombre y nada mas.
    """
    return {nombre: bool(os.environ.get(nombre, "").strip()) for nombre in REQUERIDAS}


def _estado(connection: Redis) -> dict[str, object]:
    """Lo que responde el endpoint de salud.

    Pregunta por la cola de verdad en vez de contestar 200 a secas: un worker
    que perdio Redis esta inservible aunque el proceso siga vivo, y eso tiene
    que poder notarse desde fuera.

    Y dice que variables de entorno le faltan. La verificacion facial estuvo
    rota por una de ellas y no habia forma de comprobarlo desde fuera: la foto
    de referencia se subia, su embedding nunca se calculaba, y la unica senal
    era un RuntimeError enterrado en los registros.
    """
    try:
        viva = bool(connection.ping())
    except Exception:  # noqa: BLE001 - cualquier fallo aqui significa lo mismo
        viva = False
    configuracion = _configuracion()
    try:
        mem_info = check_memory_budget()
    except ValueError as exc:
        mem_info = {
            "asr_provider": "invalid",
            "asr_local_model": None,
            "asr_fallback_provider": "invalid",
            "asr_mode": f"invalid-config:{exc}",
            "similarity_backend": "invalid",
            "memory_enforce": False,
            "memory_limit_bytes": None,
            "memory_limit_mib": None,
            "required_memory_mib": None,
            "memory_sufficient": False,
        }
    return {
        "queue": viva,
        "queues": QUEUES,
        "config": configuracion,
        "missing": sorted(nombre for nombre, puesta in configuracion.items() if not puesta),
        "warnings": avisos_configuracion_asr(),
        "asr_mode": mem_info["asr_mode"],
        "asr_provider": mem_info["asr_provider"],
        "asr_local_model": mem_info["asr_local_model"],
        "asr_fallback_provider": mem_info["asr_fallback_provider"],
        "similarity_backend": mem_info["similarity_backend"],
        "memory_enforce": mem_info["memory_enforce"],
        "memory_limit_bytes": mem_info["memory_limit_bytes"],
        "memory_limit_mib": mem_info["memory_limit_mib"],
        "required_memory_mib": mem_info["required_memory_mib"],
        "memory_sufficient": mem_info["memory_sufficient"],
    }


if __name__ == "__main__":
    sys.exit(main())
