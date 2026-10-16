"""Cola real con Redis + RQ.

Se salta sola si no hay Redis a mano, para que `uv run pytest` siga funcionando
en la maquina de cualquiera sin levantar nada. En CI y con `docker compose up`,
Redis esta y la prueba corre.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from redis import Redis
from rq import Queue

from proctoring_api.adapters.outbound.redis_queue.job_queue import (
    AUDIO_ANALYSIS_TASK,
    AUDIO_QUEUE,
    MAX_RETRIES,
    RedisJobQueue,
)

pytestmark = pytest.mark.integration

REDIS_URL = "redis://localhost:6379/15"  # base 15: separada de la de desarrollo


def redis_is_available() -> bool:
    try:
        return RedisJobQueue(REDIS_URL).ping()
    except Exception:
        return False


requires_redis = pytest.mark.skipif(
    not redis_is_available(),
    reason="No hay Redis en localhost:6379. Levantalo con `docker compose up redis`.",
)


def audio_queue() -> Queue:
    return Queue(AUDIO_QUEUE, connection=Redis.from_url(REDIS_URL))


@pytest.fixture
def queue() -> RedisJobQueue:
    # RQ no publica tipos para `empty`.
    audio_queue().empty()  # type: ignore[no-untyped-call]
    return RedisJobQueue(REDIS_URL)


@requires_redis
class TestRedisJobQueue:
    def test_enqueues_in_the_audio_queue(self, queue: RedisJobQueue) -> None:
        event_id = uuid4()
        queue.enqueue_audio_analysis(event_id)

        rq_queue = audio_queue()
        assert rq_queue.count == 1

        job = rq_queue.jobs[0]
        # Se encola por NOMBRE, no importando la funcion: la API no tiene (ni
        # debe tener) instalado el codigo del servicio de IA.
        assert job.func_name == AUDIO_ANALYSIS_TASK
        # Y solo viaja el id: meter el audio en Redis llenaria la memoria del
        # plan gratuito en una sola sesion de examen.
        assert job.args == (str(event_id),)

    def test_configures_retries(self, queue: RedisJobQueue) -> None:
        queue.enqueue_audio_analysis(uuid4())

        assert audio_queue().jobs[0].retries_left == MAX_RETRIES

    def test_ping_answers_true(self, queue: RedisJobQueue) -> None:
        assert queue.ping() is True


def test_ping_answers_false_without_redis() -> None:
    # Puerto cerrado a proposito: el adaptador no debe reventar, solo decir que no.
    assert RedisJobQueue("redis://localhost:6399/0").ping() is False


@requires_redis
class TestDespertarAlWorker:
    """El aviso al worker cuando se encola (TA-078).

    En un plan gratuito el worker se apaga tras un rato sin peticiones, y un
    consumidor de cola no recibe ninguna: se dormiria para siempre y los
    trabajos se acumularian sin que nadie los mire. Encolar es lo unico que
    pasa justo antes de necesitarlo, asi que es donde se avisa.
    """

    def espera_al_hilo(self) -> None:
        """Da su turno al hilo que toca al worker, que es `daemon`."""
        import threading
        import time

        for _ in range(100):
            if not any(h.name == "despertar-worker" for h in threading.enumerate()):
                return
            time.sleep(0.02)

    def test_toca_el_worker_al_encolar_audio(self, monkeypatch) -> None:
        tocados: list[str] = []
        import proctoring_api.adapters.outbound.redis_queue.job_queue as modulo

        monkeypatch.setattr(modulo.httpx, "get", lambda url, **_: tocados.append(url))
        cola = RedisJobQueue(REDIS_URL, "https://worker.onrender.com")

        cola.enqueue_audio_analysis(uuid4())
        self.espera_al_hilo()

        assert tocados == ["https://worker.onrender.com/health"]

    def test_tambien_al_encolar_verificacion_facial(self, monkeypatch) -> None:
        # La cola `high` tiene a alguien esperando en pantalla: si el worker
        # duerme, esa espera no termina nunca.
        tocados: list[str] = []
        import proctoring_api.adapters.outbound.redis_queue.job_queue as modulo

        monkeypatch.setattr(modulo.httpx, "get", lambda url, **_: tocados.append(url))
        cola = RedisJobQueue(REDIS_URL, "https://worker.onrender.com/")

        cola.enqueue_face_verification(uuid4(), "capturas/una.jpg")
        self.espera_al_hilo()

        # La barra final no se duplica.
        assert tocados == ["https://worker.onrender.com/health"]

    def test_si_el_worker_no_responde_el_trabajo_igual_se_encola(self, monkeypatch) -> None:
        # Lo decisivo: el trabajo ya esta en Redis y se procesara cuando el
        # worker despierte. Que el aviso falle no puede tumbar la peticion del
        # estudiante.
        import proctoring_api.adapters.outbound.redis_queue.job_queue as modulo

        def revienta(*_args, **_kwargs):
            raise OSError("sin red")

        monkeypatch.setattr(modulo.httpx, "get", revienta)
        cola = RedisJobQueue(REDIS_URL, "https://worker.onrender.com")

        cola.enqueue_audio_analysis(uuid4())
        self.espera_al_hilo()

        assert cola._audio.count >= 1

    def test_sin_url_configurada_no_toca_nada(self, monkeypatch) -> None:
        # En local el worker esta siempre despierto; tocarlo seria ruido.
        tocados: list[str] = []
        import proctoring_api.adapters.outbound.redis_queue.job_queue as modulo

        monkeypatch.setattr(modulo.httpx, "get", lambda url, **_: tocados.append(url))
        cola = RedisJobQueue(REDIS_URL, "")

        cola.enqueue_audio_analysis(uuid4())
        self.espera_al_hilo()

        assert tocados == []
