"""Cola de trabajos con Redis + RQ.

Desacopla la API del servicio de IA. Transcribir audio y clasificar voz sintetica
tarda segundos; dentro de la peticion HTTP eso dejaria al estudiante esperando y
un pico de eventos tumbaria la API. Ver ADR-0006.

En la cola **solo viaja el `event_id`**. El fragmento de audio se lee desde
Storage con la ruta que guarda el evento en `evidence_path`: meter el audio en
Redis llenaria la memoria del plan gratuito en una sola sesion de examen.
"""

from __future__ import annotations

import logging
import threading
from uuid import UUID

import httpx
from redis import Redis
from rq import Queue, Retry

logger = logging.getLogger(__name__)

#: Ruta de la funcion que ejecuta el worker de `services/ai`.
#:
#: Se encola **por nombre**, no importando la funcion: asi la API no necesita
#: tener instalado el codigo del servicio de IA ni sus modelos. Es el acoplamiento
#: minimo entre los dos servicios, y el motivo de que el nombre viva aqui como
#: constante y no disperso.
AUDIO_ANALYSIS_TASK = "tasks.analyze_audio"

#: Ruta de la funcion que compara dos caras. Misma idea: se encola por nombre.
FACE_VERIFICATION_TASK = "tasks.verify_face"

#: Analisis de audio: tarda segundos y nadie espera el resultado en pantalla.
AUDIO_QUEUE = "audio"
#: Verificacion facial: si hay un estudiante esperando en la sala de espera, con
#: un presupuesto de P90 < 500 ms. Por eso va en su propia cola y no detras de la
#: de audio.
HIGH_PRIORITY_QUEUE = "high"

#: Reintentos ante fallo. Tres es suficiente para un corte de red o un reinicio
#: del worker; mas seria insistir con un trabajo que esta roto de verdad.
MAX_RETRIES = 3

#: Cuanto puede tardar un trabajo antes de darlo por colgado.
AUDIO_JOB_TIMEOUT = "5m"

#: Lo que se espera al despertar al worker. Corto a proposito: no se espera a
#: que arranque, solo a que la plataforma reciba la peticion.
WAKE_TIMEOUT_SECONDS = 3.0
#: La verificacion facial tiene a alguien esperando en pantalla.
FACE_JOB_TIMEOUT = "60s"


class RedisJobQueue:
    """Implementacion de `JobQueue` sobre RQ."""

    def __init__(self, redis_url: str, worker_url: str | None = None) -> None:
        self._connection = Redis.from_url(redis_url)
        self._audio = Queue(AUDIO_QUEUE, connection=self._connection)
        self._high = Queue(HIGH_PRIORITY_QUEUE, connection=self._connection)
        self._worker_url = (worker_url or "").rstrip("/") or None

    def _wake_worker(self) -> None:
        """Toca el endpoint de salud del worker para que la plataforma lo arranque.

        En un plan gratuito el worker se apaga tras un rato sin peticiones, y un
        consumidor de cola **no recibe ninguna**: se dormiria para siempre y los
        trabajos se acumularian sin que nadie los mire. Nadie se enteraria hasta
        revisar un examen y encontrar el audio sin analizar.

        Encolar es lo unico que ocurre justo antes de necesitarlo, asi que es
        donde se avisa. Va en un hilo y sin mirar la respuesta: el trabajo ya
        esta en la cola y se procesara cuando el worker despierte; hacer esperar
        al estudiante a que arranque un contenedor seria absurdo.
        """
        if self._worker_url is None:
            return

        def tocar() -> None:
            try:
                httpx.get(f"{self._worker_url}/health", timeout=WAKE_TIMEOUT_SECONDS)
            except Exception as fallo:  # cualquier fallo aqui da igual
                logger.debug("No se pudo despertar al worker: %s", fallo)

        threading.Thread(target=tocar, name="despertar-worker", daemon=True).start()

    def enqueue_audio_analysis(self, event_id: UUID) -> None:
        self._audio.enqueue(
            AUDIO_ANALYSIS_TASK,
            str(event_id),
            retry=Retry(max=MAX_RETRIES),
            job_timeout=AUDIO_JOB_TIMEOUT,
        )
        self._wake_worker()

    def enqueue_face_verification(self, participant_id: UUID, capture_path: str) -> None:
        self._high.enqueue(
            FACE_VERIFICATION_TASK,
            str(participant_id),
            capture_path,
            retry=Retry(max=MAX_RETRIES),
            job_timeout=FACE_JOB_TIMEOUT,
        )
        self._wake_worker()

    def ping(self) -> bool:
        """Si Redis responde. Lo usan el healthcheck y las pruebas."""
        try:
            return bool(self._connection.ping())
        except Exception:
            return False
