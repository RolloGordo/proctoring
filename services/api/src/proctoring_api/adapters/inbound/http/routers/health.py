"""Endpoint de salud.

Lo usan el healthcheck de `docker-compose.yml`, Render y el CI.
"""

from __future__ import annotations

from fastapi import APIRouter

from proctoring_api import __version__
from proctoring_api.adapters.inbound.http.dependencies import SettingsDep
from proctoring_api.adapters.inbound.http.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Estado del servicio")
def health(settings: SettingsDep) -> HealthResponse:
    return HealthResponse(status="ok", env=settings.env, version=__version__)
