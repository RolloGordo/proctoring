"""Cola de trabajos con Redis + RQ.

Desacopla la API del servicio de IA. Transcribir audio y clasificar voz sintetica
tarda segundos; dentro de la peticion HTTP eso dejaria al estudiante esperando y
un pico de eventos tumbaria la API. Ver ADR-0006.

En la cola **solo viaja el `event_id`**. El fragmento de audio se lee desde
Storage con la ruta que guarda el evento en `evidence_path`: meter el audio en
Redis llenaria la memoria del plan gratuito en una sola sesion de examen.
"""

from __future__ import annotations

from uuid import UUID

from redis import Redis
from rq import Queue, Retry

#: Ruta de la funcion que ejecuta el worker de `services/ai`.
#:
#: Se encola **por nombre**, no importando la funcion: asi la API no necesita
#: tener instalado el codigo del servicio de IA ni sus modelos. Es el acoplamiento
#: minimo entre los dos servicios, y el motivo de que el nombre viva aqui como
#: constante y no disperso.
AUDIO_ANALYSIS_TASK = "tasks.analyze_audio"

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


class RedisJobQueue:
    """Implementacion de `JobQueue` sobre RQ."""

    def __init__(self, redis_url: str) -> None:
        self._connection = Redis.from_url(redis_url)
        self._audio = Queue(AUDIO_QUEUE, connection=self._connection)
        self._high = Queue(HIGH_PRIORITY_QUEUE, connection=self._connection)

    def enqueue_audio_analysis(self, event_id: UUID) -> None:
        self._audio.enqueue(
            AUDIO_ANALYSIS_TASK,
            str(event_id),
            retry=Retry(max=MAX_RETRIES),
            job_timeout=AUDIO_JOB_TIMEOUT,
        )

    def ping(self) -> bool:
        """Si Redis responde. Lo usan el healthcheck y las pruebas."""
        try:
            return bool(self._connection.ping())
        except Exception:
            return False
