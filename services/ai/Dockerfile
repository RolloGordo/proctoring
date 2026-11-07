# syntax=docker/dockerfile:1
#
# Imagen del worker de IA. Mismo patron que services/api: dependencias en una
# capa aparte, runtime sin uv ni compiladores, usuario sin privilegios.
#
# Dos perfiles, elegidos con el argumento PERFIL:
#
#   completo  faster-whisper `small` + similitud con torch + insightface.
#             Necesita unos 1,7 GB de RAM. Para una maquina con memoria (Oracle,
#             local con docker compose).
#   ligero    faster-whisper `tiny` + similitud ONNX int8 (vocabulario es/en) +
#             motor facial OpenCV (YuNet + SFace). Sin torch ni insightface en la
#             imagen: unos 435 MiB medidos por Pierreluiggi, lo que cabe en los
#             512 MB del plan gratuito de Render. Es el de produccion.
#
# Render pasa sus variables de entorno como argumentos de construccion, asi que
# en el panel basta con `PERFIL=ligero`. Las demas variables del perfil ligero
# (ASR_LOCAL_MODEL, SIMILARITY_BACKEND, FACE_ENGINE) vienen puestas en la imagen.
#
# Los dos funcionan 100% en local: los pesos de los modelos van dentro de la
# imagen y el worker los carga con `offline=True`, sin descargar nada al arrancar.
ARG PERFIL=completo

# ---------------------------------------------------------------------------
# Base de construccion: uv y nada mas
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS base-uv

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock ./

# ---------------------------------------------------------------------------
# Dependencias del perfil completo (y del exportador de ONNX)
# ---------------------------------------------------------------------------
FROM base-uv AS deps-completo

# Compilador solo en esta etapa. `insightface` no publica rueda para Python 3.12
# y se construye desde fuente, asi que sin g++ la imagen fallaba con
# `error: [Errno 2] No such file or directory: 'g++'`. La etapa de runtime copia
# el `.venv` ya construido y sigue sin compiladores, que es como tiene que ser.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# `asr-local` trae faster-whisper para transcripcion offline 100% local.
# `similarity` trae sentence-transformers y torch para similitud semantica.
# `face` trae insightface y opencv para verificacion facial.
# [tool.uv] package = false: aqui no hay proyecto que instalar, solo dependencias.
# --no-dev: ruff, mypy y pytest no pintan nada en produccion.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra asr-local --extra similarity --extra face

FROM deps-completo AS builder-completo
RUN /app/.venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8', download_root='/app/models', local_files_only=False)"

# ---------------------------------------------------------------------------
# Exportador: genera el MiniLM ONNX int8 con vocabulario es/en
# ---------------------------------------------------------------------------
# El modelo no se versiona en el repositorio (CLAUDE.md: nada de modelos en git),
# asi que se genera aqui con el script reproducible de Pierreluiggi, desde la
# revision fijada en Hugging Face. torch solo existe en esta etapa: la imagen
# ligera se lleva el .onnx y el tokenizer, nada mas.
FROM deps-completo AS exportador
COPY spikes/__init__.py spikes/network.py spikes/export_onnx.py ./spikes/
RUN /app/.venv/bin/python spikes/export_onnx.py --source hf --int8-only \
        --out-dir /app/models/onnx_minilm_experiment \
    && rm -f /app/models/onnx_minilm_experiment/model_fp32_es_en.onnx

# ---------------------------------------------------------------------------
# Dependencias y modelos del perfil ligero
# ---------------------------------------------------------------------------
FROM base-uv AS builder-ligero
# faster-whisper ya trae onnxruntime y tokenizers, que es todo lo que usa la
# similitud ONNX; `face-opencv` solo anade opencv. No hace falta compilador.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra asr-local --extra face-opencv
RUN /app/.venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('tiny', device='cpu', compute_type='int8', download_root='/app/models', local_files_only=False)"
COPY --from=exportador /app/models/onnx_minilm_experiment /app/models/onnx_minilm_experiment

# Solo se construye la cadena del perfil pedido: BuildKit salta las demas.
FROM builder-${PERFIL} AS elegido

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app

RUN groupadd --system --gid 1001 proctoring \
    && useradd --system --uid 1001 --gid proctoring --create-home proctoring

WORKDIR /app

COPY --from=elegido --chown=proctoring:proctoring /app/.venv /app/.venv
COPY --from=elegido --chown=proctoring:proctoring /app/models /app/models

# Solo lo que el worker ejecuta. Los demas spikes se quedan fuera: son
# experimentos, no codigo de produccion.
#   tasks.py              los trabajos que consume la cola
#   worker_stub.py        el proceso que escucha
#   salud.py              prueba de vida HTTP, que la plataforma exige
#   audio_runtime.py      descarga, decodifica y mide el audio
#   deepgram_transcriber  el proveedor de transcripcion remoto (opcional)
#   face_pipeline.py      verificacion facial
#   spikes/metrics.py     lo usa deepgram_transcriber
#   spikes/network.py     descarga de pesos a traves del proxy TLS del sistema
#   spikes/similarity.py  similitud con el enunciado
#   spikes/synthetic_voice.py  de aqui sale `decode_audio`
#   spikes/transcribe.py  save_json, y el ASR local
COPY --chown=proctoring:proctoring \
    tasks.py worker_stub.py salud.py audio_runtime.py deepgram_transcriber.py face_pipeline.py ./
COPY --chown=proctoring:proctoring spikes/__init__.py spikes/metrics.py spikes/network.py \
    spikes/similarity.py spikes/synthetic_voice.py spikes/transcribe.py ./spikes/

# API de imagen propia (Jesus, atributo de Disponibilidad): YuNet + SFace int8,
# unos 10 MB, versionados en `vision/modelos/` con su sha256. Van DENTRO de la
# imagen a proposito: con `FACE_ENGINE=opencv` el worker no descarga nada al
# arrancar, y un arranque en frio sin red no deja la verificacion caida.
COPY --chown=proctoring:proctoring vision/ ./vision/

# Donde insightface descarga su modelo, con dueno.
#
# `FaceAnalysis` hace `os.makedirs` sobre `FACE_MODEL_ROOT`, que por defecto
# resuelve a `/app/models`. `/app` es de root y el proceso corre como
# `proctoring`, asi que cada verificacion moria con
# `PermissionError: [Errno 13] Permission denied: '/app/models'` **despues** de
# haber bajado la captura: el trabajo llegaba hasta el ultimo paso y se caia.
RUN mkdir -p /app/models && chown -R proctoring:proctoring /app/models
ENV FACE_MODEL_ROOT=/app/models

USER proctoring

# El worker no sirve peticiones, pero abre un puerto de salud: Hugging Face
# Spaces y los Web Services de Render dan por caido un contenedor sin puerto
# abierto, y el plan gratuito de Render no incluye Background Workers.
EXPOSE 7860

# Comprueba que el proceso sigue vivo y que la cola responde. Un worker que
# perdio Redis esta inservible aunque el contenedor siga en pie.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import os,redis,sys; sys.exit(0 if redis.Redis.from_url(os.environ.get('REDIS_URL','redis://localhost:6379/0')).ping() else 1)"

CMD ["python", "worker_stub.py"]

# ---------------------------------------------------------------------------
# Imagen final de cada perfil
# ---------------------------------------------------------------------------
FROM runtime AS final-completo
ENV ASR_PROVIDER=faster-whisper \
    ASR_LOCAL_MODEL=small \
    SIMILARITY_BACKEND=torch \
    FACE_ENGINE=insightface

FROM runtime AS final-ligero
# Valores por defecto, no imposiciones: una variable del panel los sigue
# pisando. Un solo proceso sin fork (SimpleWorker) para que los modelos se
# carguen una vez y no se dupliquen en memoria por cada trabajo.
ENV ASR_PROVIDER=faster-whisper \
    ASR_LOCAL_MODEL=tiny \
    ASR_FALLBACK_PROVIDER=none \
    SIMILARITY_BACKEND=onnx-int8 \
    SIMILARITY_ONNX_VOCAB=es_en \
    FACE_ENGINE=opencv \
    WORKER_USE_SIMPLE_WORKER=true \
    OMP_NUM_THREADS=1 \
    MALLOC_ARENA_MAX=2

FROM final-${PERFIL}
