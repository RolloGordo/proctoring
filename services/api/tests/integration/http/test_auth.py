"""Autenticacion y autorizacion sobre HTTP."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from proctoring_api.config import Settings
from proctoring_api.main import create_app

from tests.conftest import (
    CONTRACT_STUDENT_ID,
    OTHER_STUDENT_TOKEN,
    STUDENT_TOKEN,
    TEACHER_TOKEN,
)

pytestmark = pytest.mark.integration


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestAuthentication:
    def test_401_without_a_token(self, authed_client: TestClient, contract_example: Any) -> None:
        response = authed_client.post("/api/v1/events", json=contract_example("focus_lost"))

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"

    def test_401_with_an_invalid_token(
        self, authed_client: TestClient, contract_example: Any
    ) -> None:
        response = authed_client.post(
            "/api/v1/events",
            json=contract_example("focus_lost"),
            headers=bearer("token-falso"),
        )

        assert response.status_code == 401

    def test_401_on_listing_without_a_token(self, authed_client: TestClient) -> None:
        response = authed_client.get(f"/api/v1/sessions/{CONTRACT_STUDENT_ID}/events")

        assert response.status_code == 401

    def test_health_stays_public(self, authed_client: TestClient) -> None:
        # El healthcheck del contenedor y de Render no tienen token.
        assert authed_client.get("/health").status_code == 200


class TestAuthorization:
    def test_a_student_can_report_about_themselves(
        self, authed_client: TestClient, contract_example: Any
    ) -> None:
        response = authed_client.post(
            "/api/v1/events",
            json=contract_example("focus_lost"),
            headers=bearer(STUDENT_TOKEN),
        )

        assert response.status_code == 201, response.text

    def test_403_reporting_about_another_student(
        self, authed_client: TestClient, contract_example: Any
    ) -> None:
        # Mismo cuerpo, token de otro estudiante.
        response = authed_client.post(
            "/api/v1/events",
            json=contract_example("focus_lost"),
            headers=bearer(OTHER_STUDENT_TOKEN),
        )

        assert response.status_code == 403
        assert "otro estudiante" in response.json()["detail"]

    def test_403_when_a_teacher_registers_an_event(
        self, authed_client: TestClient, contract_example: Any
    ) -> None:
        response = authed_client.post(
            "/api/v1/events",
            json=contract_example("focus_lost"),
            headers=bearer(TEACHER_TOKEN),
        )

        assert response.status_code == 403

    def test_a_student_only_lists_their_own_events(
        self, authed_client: TestClient, contract_example: Any
    ) -> None:
        payload = contract_example("focus_lost")
        authed_client.post("/api/v1/events", json=payload, headers=bearer(STUDENT_TOKEN))

        session_id = payload["session_id"]
        # Pide explicitamente los de otro estudiante.
        response = authed_client.get(
            f"/api/v1/sessions/{session_id}/events",
            params={"student_id": "11111111-2222-4333-8444-555555555555"},
            headers=bearer(STUDENT_TOKEN),
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["student_id"] == str(CONTRACT_STUDENT_ID)

    def test_a_teacher_lists_the_whole_session(
        self, authed_client: TestClient, contract_example: Any
    ) -> None:
        payload = contract_example("focus_lost")
        authed_client.post("/api/v1/events", json=payload, headers=bearer(STUDENT_TOKEN))

        response = authed_client.get(
            f"/api/v1/sessions/{payload['session_id']}/events",
            headers=bearer(TEACHER_TOKEN),
        )

        assert response.status_code == 200
        assert len(response.json()) == 1


class TestAuthCannotBeDisabledOutsideLocal:
    """El seguro que impide desplegar la API abierta."""

    def test_refuses_to_start_with_auth_disabled_in_production(self) -> None:
        with pytest.raises(ValueError, match="AUTH_ENABLED"):
            create_app(
                Settings(
                    env="production",
                    auth_enabled=False,
                    event_repository="memory",
                    job_queue="memory",
                )
            )

    def test_allowed_in_local(self) -> None:
        app = create_app(
            Settings(
                env="local",
                auth_enabled=False,
                event_repository="memory",
                job_queue="memory",
            )
        )
        assert app.state.identify_user is None

    def test_auth_is_enabled_by_default(self) -> None:
        # Si la variable no existe en el entorno, se protege. Es el caso de un
        # despliegue donde alguien olvido configurarla.
        assert Settings(_env_file=None).auth_enabled is True  # type: ignore[call-arg]
