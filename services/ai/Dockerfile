# syntax=docker/dockerfile:1
#
# Imagen del worker de IA. Mismo patron que services/api: dependencias en una
# capa aparte, runtime sin uv ni compiladores, usuario sin privilegios.
#
# Los modelos NO van en la imagen. Se montan en un volumen, porque pesan
# cientos de megabytes y porque `similarity_model()` carga en modo `offline=True`
# a proposito: un trabajo de audio nunca descarga nada mientras un estudiante
# rinde.
#
# La transcripcion va por API (Deepgram, TA-070), asi que aqui no entra
# faster-whisper: vive en el extra `asr-local`, para comparar en local.
# ---------------------------------------------------------------------------
# Etapa 1 — dependencias
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Compilador solo en esta etapa. `insightface` no publica rueda para Python 3.12
# y se construye desde fuente, asi que sin g++ la imagen fallaba con
# `error: [Errno 2] No such file or directory: 'g++'`. La etapa de runtime copia
# el `.venv` ya construido y sigue sin compiladores, que es como tiene que ser.
RUN apt-get update     && apt-get install -y --no-install-recommends build-essential     && rm -rf /var/lib/apt/lists/*

# `similarity` trae sentence-transformers, y con el torch. Es el diferencial del
# proyecto —comparar lo que se dijo con el enunciado— asi que va por defecto;
# queda como argumento para poder construir una imagen minima y medir la
# diferencia.
#
# `face` va tambien por defecto desde que se descubrio por que la verificacion
# facial no habia terminado nunca: sus dependencias vivian solo en
# `requirements-face.txt`, con la nota de instalarlas "a mano en el worker".
# En Render no hay instalacion a mano, asi que no estaban en la imagen y cada
# trabajo moria con `ModuleNotFoundError: No module named 'cv2'`. Lo que el
# despliegue necesita tiene que estar en el Dockerfile, no en un documento.
ARG EXTRAS="--extra similarity --extra face"

COPY pyproject.toml uv.lock ./
# [tool.uv] package = false: aqui no hay proyecto que instalar, solo dependencias.
# --no-dev: ruff, mypy y pytest no pintan nada en produccion.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev ${EXTRAS}

# ---------------------------------------------------------------------------
# Etapa 2 — runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app

RUN groupadd --system --gid 1001 proctoring \
    && useradd --system --uid 1001 --gid proctoring --create-home proctoring

WORKDIR /app

COPY --from=builder --chown=proctoring:proctoring /app/.venv /app/.venv

# Solo lo que el worker ejecuta. Los demas spikes se quedan fuera: son
# experimentos, no codigo de produccion.
#   tasks.py              los trabajos que consume la cola
#   worker_stub.py        el proceso que escucha
#   salud.py              prueba de vida HTTP, que la plataforma exige
#   audio_runtime.py      descarga, decodifica y mide el audio
#   deepgram_transcriber  el proveedor de transcripcion
#   face_pipeline.py      verificacion facial
#   spikes/metrics.py     lo usa deepgram_transcriber
#   spikes/network.py     descarga de pesos a traves del proxy TLS del sistema
#   spikes/similarity.py  similitud con el enunciado
#   spikes/synthetic_voice.py  de aqui sale `decode_audio`
#   spikes/transcribe.py  save_json, y el ASR local si se pide
COPY --chown=proctoring:proctoring \
    tasks.py worker_stub.py salud.py audio_runtime.py deepgram_transcriber.py face_pipeline.py ./
COPY --chown=proctoring:proctoring spikes/__init__.py spikes/metrics.py spikes/network.py \
    spikes/similarity.py spikes/synthetic_voice.py spikes/transcribe.py ./spikes/

# Donde insightface descarga su modelo, con dueno.
#
# `FaceAnalysis` hace `os.makedirs` sobre `FACE_MODEL_ROOT`, que por defecto
# resuelve a `/app/models`. `/app` es de root y el proceso corre como
# `proctoring`, asi que cada verificacion moria con
# `PermissionError: [Errno 13] Permission denied: '/app/models'` **despues** de
# haber bajado la captura: el trabajo llegaba hasta el ultimo paso y se caia.
#
# El disco es efimero, asi que buffalo_sc (unos 16 MB) se vuelve a descargar en
# cada arranque en frio. Cabe en el presupuesto; montar un volumen seria mejor,
# pero el plan gratuito no los da.
RUN mkdir -p /app/models && chown -R proctoring:proctoring /app/models
ENV FACE_MODEL_ROOT=/app/models

USER proctoring

# Comprueba que el proceso sigue vivo y que la cola responde. Un worker que
# perdio Redis esta inservible aunque el contenedor siga en pie.
# El worker no sirve peticiones, pero abre un puerto de salud: Hugging Face
# Spaces y los Web Services de Render dan por caido un contenedor sin puerto
# abierto, y el plan gratuito de Render no incluye Background Workers.
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import os,redis,sys; sys.exit(0 if redis.Redis.from_url(os.environ.get('REDIS_URL','redis://localhost:6379/0')).ping() else 1)"

CMD ["python", "worker_stub.py"]
