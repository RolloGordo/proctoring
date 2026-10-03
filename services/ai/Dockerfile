# syntax=docker/dockerfile:1
#
# Imagen del worker de IA. **Provisional**: solo lleva lo necesario para el
# esqueleto (`worker_stub.py`). Cuando Pierreluiggi anada faster-whisper,
# sentence-transformers e InsightFace, esto pasa a multi-stage con uv, como el
# Dockerfile de services/api.
#
# Los modelos NO van en la imagen: se descargan en tiempo de ejecucion a un
# volumen, porque pesan cientos de megabytes y el plan gratuito del registro no
# los aguanta.

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --system --gid 1001 proctoring \
    && useradd --system --uid 1001 --gid proctoring --create-home proctoring

WORKDIR /app

RUN pip install --no-cache-dir "rq>=2.0" "redis>=5.0"

COPY --chown=proctoring:proctoring tasks.py worker_stub.py ./

USER proctoring

CMD ["python", "worker_stub.py"]
