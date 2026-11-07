# syntax=docker/dockerfile:1
#
# Imagen del worker de IA. Mismo patron que services/api: dependencias en una
# capa aparte, runtime sin uv ni compiladores, usuario sin privilegios.
#
# faster-whisper funciona 100% en local como motor principal a traves del extra
# `asr-local`, con los pesos del modelo predescargados en `/app/models` para permitir
# ejecucion `offline=True` (imprescindible en Hugging Face Spaces o entornos aislados).
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

# `asr-local` trae faster-whisper para transcripcion offline 100% local.
# `similarity` trae sentence-transformers y torch para similitud semantica.
# `face` trae insightface y opencv para verificacion facial.
ARG EXTRAS="--extra asr-local --extra similarity --extra face"

COPY pyproject.toml uv.lock ./
# [tool.uv] package = false: aqui no hay proyecto que instalar, solo dependencias.
# --no-dev: ruff, mypy y pytest no pintan nada en produccion.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev ${EXTRAS}

# Pre-descarga de pesos del modelo faster-whisper (small) en el builder para permitir
# ejecucion offline en entornos sin conexion a internet externa (Hugging Face Spaces).
ARG DOWNLOAD_ASR_MODEL="true"
RUN if [ "$DOWNLOAD_ASR_MODEL" = "true" ]; then \
        /app/.venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8', download_root='/app/models', local_files_only=False)"; \
    else \
        mkdir -p /app/models; \
    fi

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
COPY --from=builder --chown=proctoring:proctoring /app/models /app/models

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
