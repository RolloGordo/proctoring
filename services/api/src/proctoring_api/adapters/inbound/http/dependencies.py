"""Inyeccion de dependencias para los routers.

Los casos de uso se arman una sola vez en `main.create_app()` y se guardan en
`app.state`. Los routers los piden con `Depends`, asi que nunca construyen un
adaptador ni saben cual esta configurado: eso es lo que permite cambiar memoria
por Supabase con una variable de entorno.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from proctoring_api.application.use_cases.list_session_events import ListSessionEvents
from proctoring_api.application.use_cases.register_event import RegisterEvent
from proctoring_api.config import Settings


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_register_event(request: Request) -> RegisterEvent:
    use_case: RegisterEvent = request.app.state.register_event
    return use_case


def get_list_session_events(request: Request) -> ListSessionEvents:
    use_case: ListSessionEvents = request.app.state.list_session_events
    return use_case


SettingsDep = Annotated[Settings, Depends(get_settings)]
RegisterEventDep = Annotated[RegisterEvent, Depends(get_register_event)]
ListSessionEventsDep = Annotated[ListSessionEvents, Depends(get_list_session_events)]
