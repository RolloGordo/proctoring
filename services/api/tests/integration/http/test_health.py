"""Endpoint de salud y documentacion OpenAPI."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from proctoring_api import __version__

pytestmark = pytest.mark.integration


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "env": "test",
        "version": __version__,
        "auth": "disabled",
    }


def test_openapi_is_published(client: TestClient) -> None:
    # Swagger en /docs es la evidencia visible del avance: si el esquema se rompe,
    # la demo al docente se cae.
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Proctoring API"
    assert "/api/v1/events" in schema["paths"]
    assert "/api/v1/sessions/{session_id}/events" in schema["paths"]


def test_docs_page_is_served(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200


def test_health_reports_auth_enabled(authed_client: TestClient) -> None:
    """Si alguna vez apareciera "disabled" en un entorno real, se ve de un vistazo."""
    assert authed_client.get("/health").json()["auth"] == "enabled"
