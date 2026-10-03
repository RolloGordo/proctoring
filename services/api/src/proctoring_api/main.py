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
from proctoring_api.adapters.outbound.memory.alert_repository import InMemoryAlertRepository
from proctoring_api.adapters.outbound.memory.event_repository import InMemoryEventRepository
from proctoring_api.adapters.outbound.memory.job_queue import InMemoryJobQueue
from proctoring_api.adapters.outbound.memory.profile_repository import InMemoryProfileRepository
from proctoring_api.application.ports.alert_repository import AlertRepository
from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.event_repository import EventRepository
from proctoring_api.application.ports.job_queue import JobQueue
from proctoring_api.application.ports.profile_repository import ProfileRepository
from proctoring_api.application.ports.question_repository import QuestionRepository
from proctoring_api.application.use_cases.identify_user import IdentifyUser
from proctoring_api.application.use_cases.list_session_alerts import ListSessionAlerts
from proctoring_api.application.use_cases.list_session_events import ListSessionEvents
from proctoring_api.application.use_cases.register_event import RegisterEvent
from proctoring_api.config import ENVS_WITHOUT_AUTH, Settings

DESCRIPTION = """
API principal del sistema de proctoring para examenes remotos (UPAO, Taller Integrador 1).

Recibe las senales que detectan la app de escritorio del estudiante y la web, las
guarda como evidencia y encola el analisis de audio del servicio de IA.

**No recibe video.** Solo eventos, y la ruta en Storage de la captura o del
fragmento de audio, que el cliente sube directo con una URL firmada.

El sistema es un auditor, no un juez: calcula riesgo y entrega evidencia; la
decision final es del docente, con justificacion obligatoria.

## Autenticacion

Token de Supabase Auth en `Authorization: Bearer <token>`. Un estudiante solo
puede registrar eventos sobre si mismo y solo puede leer los suyos.
"""


def _build_supabase_client(settings: Settings) -> object:
    from supabase import create_client

    url, key = settings.require_supabase()
    return create_client(url, key)


def _build_event_repository(settings: Settings, client: object | None) -> EventRepository:
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.event_repository import (
            SupabaseEventRepository,
        )

        assert isinstance(client, Client)
        return SupabaseEventRepository(client)

    return InMemoryEventRepository()


def _build_alert_repository(settings: Settings, client: object | None) -> AlertRepository:
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.alert_repository import (
            SupabaseAlertRepository,
        )

        assert isinstance(client, Client)
        return SupabaseAlertRepository(client)

    return InMemoryAlertRepository()


def _build_profile_repository(settings: Settings, client: object | None) -> ProfileRepository:
    # Los perfiles viven en la misma base que los eventos, asi que siguen el mismo
    # adaptador: no tiene sentido leer eventos de Supabase y perfiles de memoria.
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.profile_repository import (
            SupabaseProfileRepository,
        )

        assert isinstance(client, Client)
        return SupabaseProfileRepository(client)

    return InMemoryProfileRepository()


def _build_question_repository(
    settings: Settings, client: object | None
) -> QuestionRepository | None:
    """`None` en modo memoria: no hay banco de preguntas contra el que comprobar.

    Rechazar todo evento con `question_id` dejaria a Rider y a Jesus sin poder
    mandar `gaze_away` ni `speech_detected` mientras desarrollan. Con Supabase la
    comprobacion si se hace.
    """
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.question_repository import (
            SupabaseQuestionRepository,
        )

        assert isinstance(client, Client)
        return SupabaseQuestionRepository(client)

    return None


def _build_job_queue(settings: Settings) -> JobQueue:
    # El adaptador de Redis llega en la Fase 5 (ADR-0006). Hasta entonces la cola
    # en memoria deja el flujo completo funcionando y las pruebas verdes.
    if settings.job_queue == "redis":
        raise NotImplementedError(
            "JOB_QUEUE=redis todavia no esta implementado; usa JOB_QUEUE=memory"
        )
    return InMemoryJobQueue()


def _build_identify_user(settings: Settings, profiles: ProfileRepository) -> IdentifyUser | None:
    """`None` significa autenticacion desactivada.

    Solo se permite en desarrollo local. En cualquier otro entorno el servicio se
    niega a arrancar: es preferible un despliegue que falla a uno que acepta
    evidencia de cualquiera.
    """
    if not settings.auth_enabled:
        if settings.env not in ENVS_WITHOUT_AUTH:
            raise ValueError(
                f"AUTH_ENABLED=false solo se permite con ENV en "
                f"{sorted(ENVS_WITHOUT_AUTH)} (ENV={settings.env!r}). "
                "Desplegar la API sin autenticacion dejaria que cualquiera "
                "fabricara evidencia contra cualquier estudiante."
            )
        return None

    from proctoring_api.adapters.outbound.supabase.token_verifier import (
        SupabaseTokenVerifier,
    )

    return IdentifyUser(SupabaseTokenVerifier(settings.require_supabase_url()), profiles)


def create_app(
    settings: Settings | None = None,
    clock: Clock | None = None,
    identify_user: IdentifyUser | None = None,
) -> FastAPI:
    """Arma la aplicacion con los adaptadores que indique la configuracion.

    `clock` e `identify_user` se pueden sustituir para que las pruebas de
    integracion no dependan de la hora a la que se ejecuten ni de un proyecto de
    Supabase real. Si se pasa `identify_user`, manda sobre `AUTH_ENABLED`.
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
    client = _build_supabase_client(settings) if settings.event_repository == "supabase" else None

    event_repository = _build_event_repository(settings, client)
    alert_repository = _build_alert_repository(settings, client)
    question_repository = _build_question_repository(settings, client)
    profile_repository = _build_profile_repository(settings, client)
    job_queue = _build_job_queue(settings)
    clock = clock or SystemClock()

    app.state.settings = settings
    app.state.event_repository = event_repository
    app.state.alert_repository = alert_repository
    app.state.profile_repository = profile_repository
    app.state.job_queue = job_queue
    app.state.identify_user = identify_user or _build_identify_user(settings, profile_repository)
    app.state.register_event = RegisterEvent(
        event_repository, job_queue, clock, alert_repository, question_repository
    )
    app.state.list_session_events = ListSessionEvents(event_repository)
    app.state.list_session_alerts = ListSessionAlerts(alert_repository)

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(events.router)

    return app


# Se arranca con `--factory` (ver Dockerfile y README) en vez de dejar aqui un
# `app = create_app()`. Si la app se construyera al importar el modulo, importarlo
# para cualquier cosa (una prueba, un script) abriria la conexion a Supabase que
# diga el .env del momento.
