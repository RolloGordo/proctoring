"""Contrato de la cola contra Redis real (TA-064).

Lo que esta prueba SI demuestra, y es lo que nadie habia comprobado hasta ahora:

1. La API encola por nombre (`"tasks.analyze_audio"`), asi que el entorno de la
   API nunca importa las dependencias pesadas de IA.
2. Un worker real de RQ saca el trabajo de un Redis real y lo ejecuta.
3. El job llega a `finished` y su valor de retorno es el que devolvio la API.
4. La forma exacta del informe que el worker le manda a la API.

Lo que NO demuestra, y conviene no confundirlo: **el presupuesto de 10 s del
objetivo SMART**. El ASR, la similitud, el detector de voz sintetica, la
descarga de Storage y las dos llamadas HTTP estan simulados. Aqui se mide el
sobrecoste de encolar y consumir, que son decenas de milisegundos. El
presupuesto real pide audio, Deepgram y API de verdad; mientras eso no exista,
TA-064 cubre la cola, no la latencia.
"""

from __future__ import annotations

import os
import time
from unittest.mock import Mock
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from redis import Redis
from rq import Queue, SimpleWorker, Worker

import audio_runtime
import tasks

#: En Windows RQ no tiene `os.fork()`, asi que el worker corre en el mismo
#: proceso. En Docker, que es donde se despliega, se usa el `Worker` normal.
WorkerClass = SimpleWorker if os.name == "nt" else Worker


#: La base 15 se fuerza siempre. El fixture hace `flushdb()`, y el `REDIS_URL`
#: del `.env` apunta a `redis://redis:6379/0`, que es la cola de verdad: correr
#: esta prueba con esa variable exportada borraria los trabajos pendientes. Del
#: entorno se toma donde vive Redis, nunca que base usar.
def _url_de_prueba() -> str:
    partes = urlsplit(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    return f"{partes.scheme or 'redis'}://{partes.netloc or 'localhost:6379'}/15"


REDIS_URL = _url_de_prueba()


def is_redis_available() -> bool:
    try:
        r = Redis.from_url(REDIS_URL, socket_timeout=2)
        return bool(r.ping())
    except Exception:
        return False


requires_real_redis = pytest.mark.skipif(
    not is_redis_available(),
    reason="Redis no disponible en localhost:6379",
)


@requires_real_redis
class TestAudioWorkerRealRedisIntegration:
    @pytest.fixture(autouse=True)
    def clean_redis(self):
        r = Redis.from_url(REDIS_URL)
        r.flushdb()
        yield r
        r.flushdb()

    def test_enqueue_and_worker_consumption_end_to_end(self, clean_redis, monkeypatch, tmp_path):
        import spikes.synthetic_voice

        event_id = str(uuid4())
        audio_file = tmp_path / "segment.wav"
        import wave

        with wave.open(str(audio_file), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 16000)

        monkeypatch.setattr(spikes.synthetic_voice, "decode_audio", lambda _: [0.0] * 16000)

        # 1. Configurar cola RQ real en Redis
        queue = Queue("audio", connection=clean_redis)
        assert queue.count == 0

        # 2. Simular respuestas de la API interna para el worker
        api_results_received = []

        def mock_get(path: str, **params):
            assert f"/audio-jobs/{event_id}" in path
            return {
                "audio_bucket": "audio-segments",
                "audio_path": "test/segment.webm",
                "question_statement": "¿Qué garantiza Row Level Security en PostgreSQL?",
                "similarity_threshold": 0.60,
                "synthetic_threshold": 0.50,
            }

        def mock_post(path: str, payload: dict):
            assert f"/audio-jobs/{event_id}/result" in path
            api_results_received.append(payload)
            # Simular decisión de la API: dos condiciones cumplidas -> alerted: True
            return {"alerted": True, "event_id": event_id}

        monkeypatch.setattr(tasks, "INTERNAL_TOKEN", "test-secret-token-123")
        monkeypatch.setattr(tasks, "_get", mock_get)
        monkeypatch.setattr(tasks, "_post", mock_post)
        monkeypatch.setattr(
            tasks, "download_audio", lambda job, dest: dest.write_bytes(audio_file.read_bytes())
        )

        # Mocks para modelos en la medición rápida
        monkeypatch.setattr(
            audio_runtime,
            "asr_model",
            lambda: Mock(
                transcribe=lambda _: {"transcript": "Garantiza seguridad a nivel de filas"},
                version="deepgram-nova-3-es",
            ),
        )
        monkeypatch.setattr(
            audio_runtime,
            "similarity_model",
            lambda: Mock(score=lambda a, b: 0.88),
        )
        monkeypatch.setattr(
            audio_runtime,
            "synthetic_model",
            lambda: Mock(score=lambda p: 0.94),
        )

        # 3. Encolar el job en Redis exactamente como lo hace la API
        t0 = time.monotonic()
        job = queue.enqueue("tasks.analyze_audio", event_id)
        assert queue.count == 1
        assert job.get_status() == "queued"
        assert job.args == (event_id,)

        # 4. Levantar worker real de RQ escuchando la cola real
        worker = WorkerClass([queue], connection=clean_redis)
        # Ejecuta un ciclo de procesamiento (burst=True se detiene cuando no hay más jobs)
        result = worker.work(burst=True)
        t_total_ms = int((time.monotonic() - t0) * 1000)

        # 5. Verificaciones de Redis y Worker
        assert result is True, "El worker debió procesar el trabajo exitosamente"
        assert queue.count == 0, "La cola debe quedar vacía tras el consumo"

        # Refrescar estado del job desde Redis
        job.refresh()
        assert job.get_status() == "finished", f"El job terminó en estado {job.get_status()}"
        assert job.result == {"alerted": True, "event_id": event_id}

        # 6. Verificaciones del contrato de datos recibido por la API
        assert len(api_results_received) == 1
        report = api_results_received[0]
        assert report["transcript"] == "Garantiza seguridad a nivel de filas"
        assert report["similarity"] == 0.88
        assert report["synthetic_voice_score"] == 0.94
        assert "processing_ms" in report
        assert report["model_versions"]["asr"] == "deepgram-nova-3-es"
        assert report["model_versions"]["session_similarity_threshold"] == "0.6"
        assert report["model_versions"]["session_synthetic_threshold"] == "0.5"

        # 7. Sobrecoste de la cola, que es lo unico que esta prueba puede medir:
        #    todo lo caro esta simulado. No es el presupuesto de 10 s del SMART.
        assert t_total_ms < 10000, (
            f"Encolar y consumir tardo {t_total_ms} ms. No es la latencia del "
            "analisis: con todo simulado esto deberian ser decenas de ms, asi "
            "que un numero alto apunta a Redis o al worker, no a los modelos."
        )
        print()
        print(f"[TA-064] Cola: encolar y consumir en {t_total_ms} ms.")
