"""Composicion de dependencias y aplicacion FastAPI.

Este es el unico archivo que conoce **todos** los adaptadores a la vez. Es el
precio de la arquitectura hexagonal y tambien su beneficio: el cableado esta en un
solo sitio y se lee de arriba abajo.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from proctoring_api import __version__
from proctoring_api.adapters.inbound.http.errors import register_error_handlers
from proctoring_api.adapters.inbound.http.routers import events, health
from proctoring_api.adapters.outbound.clock import SystemClock
from proctoring_api.adapters.outbound.memory.event_repository import InMemoryEventRepository
from proctoring_api.adapters.outbound.memory.job_queue import InMemoryJobQueue
from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.event_repository import EventRepository
from proctoring_api.application.ports.job_queue import JobQueue
from proctoring_api.application.use_cases.list_session_events import ListSessionEvents
from proctoring_api.application.use_cases.register_event import RegisterEvent
from proctoring_api.config import Settings

DESCRIPTION = """
API principal del sistema de proctoring para examenes remotos (UPAO, Taller Integrador 1).

Recibe las senales que detectan la app de escritorio del estudiante y la web, las
guarda como evidencia y encola el analisis de audio del servicio de IA.

**No recibe video.** Solo eventos, y la ruta en Storage de la captura o del
fragmento de audio, que el cliente sube directo con una URL firmada.

El sistema es un auditor, no un juez: calcula riesgo y entrega evidencia; la
decision final es del docente, con justificacion obligatoria.
"""


def _build_event_repository(settings: Settings) -> EventRepository:
    if settings.event_repository == "supabase":
        from supabase import create_client

        from proctoring_api.adapters.outbound.supabase.event_repository import (
            SupabaseEventRepository,
        )

        url, key = settings.require_supabase()
        return SupabaseEventRepository(create_client(url, key))

    return InMemoryEventRepository()


def _build_job_queue(settings: Settings) -> JobQueue:
    # El adaptador de Redis llega en la Fase 5 (ADR-0006). Hasta entonces la cola
    # en memoria deja el flujo completo funcionando y las pruebas verdes.
    if settings.job_queue == "redis":
        raise NotImplementedError(
            "JOB_QUEUE=redis todavia no esta implementado; usa JOB_QUEUE=memory"
        )
    return InMemoryJobQueue()


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    """Arma la aplicacion con los adaptadores que indique la configuracion.

    `clock` se puede sustituir para que las pruebas de integracion no dependan de
    la hora a la que se ejecuten.
    """
    settings = settings or Settings()

    app = FastAPI(
        title="Proctoring API",
        description=DESCRIPTION,
        version=__version__,
        openapi_tags=[
            {"name": "health", "description": "Estado del servicio"},
            {"name": "events", "description": "Senales detectadas durante un examen"},
        ],
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Cableado: adaptadores -> casos de uso ---
    event_repository = _build_event_repository(settings)
    job_queue = _build_job_queue(settings)
    clock = clock or SystemClock()

    app.state.settings = settings
    app.state.event_repository = event_repository
    app.state.job_queue = job_queue
    app.state.register_event = RegisterEvent(event_repository, job_queue, clock)
    app.state.list_session_events = ListSessionEvents(event_repository)

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(events.router)

    return app


# Se arranca con `--factory` (ver Dockerfile y README) en vez de dejar aqui un
# `app = create_app()`. Si la app se construyera al importar el modulo, importarlo
# para cualquier cosa (una prueba, un script) abriria la conexion a Supabase que
# diga el .env del momento.
