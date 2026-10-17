# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Etapa 1 — dependencias
# Se instalan en una capa aparte, antes de copiar el codigo: cambiar un archivo
# de src no invalida la cache de las dependencias.
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./
# --no-install-project: aqui solo van las dependencias, el proyecto va despues.
# --no-dev: ruff, mypy y pytest no pintan nada en la imagen de produccion.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY src/ ./src/
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# ---------------------------------------------------------------------------
# Etapa 2 — runtime
# Sin uv, sin compiladores y sin herramientas de desarrollo.
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Usuario sin privilegios: si alguien escapa del proceso, no es root.
RUN groupadd --system --gid 1001 proctoring \
    && useradd --system --uid 1001 --gid proctoring --create-home proctoring

WORKDIR /app

COPY --from=builder --chown=proctoring:proctoring /app/.venv /app/.venv
COPY --from=builder --chown=proctoring:proctoring /app/src /app/src

USER proctoring

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# --factory: la app se construye al arrancar, no al importar el modulo, para que
# los adaptadores se elijan con las variables de entorno del contenedor.
CMD ["uvicorn", "proctoring_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
