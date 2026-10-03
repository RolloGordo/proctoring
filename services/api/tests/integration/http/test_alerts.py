"""Endpoint de alertas, de punta a punta."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import STUDENT_TOKEN, TEACHER_TOKEN

pytestmark = pytest.mark.integration


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestWithoutAuth:
    def test_a_high_severity_event_produces_an_alert(
        self, client: TestClient, contract_example: Any
    ) -> None:
        payload = contract_example("extra_person")
        client.post("/api/v1/events", json=payload)

        response = client.get(f"/api/v1/sessions/{payload['session_id']}/alerts")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["severity"] == "high"
        assert body[0]["reason"] == "Se detecto a otra persona en camara"
        assert body[0]["student_id"] == payload["student_id"]

    def test_a_low_severity_event_produces_none(
        self, client: TestClient, contract_example: Any
    ) -> None:
        payload = contract_example("speech_detected")
        client.post("/api/v1/events", json=payload)

        response = client.get(f"/api/v1/sessions/{payload['session_id']}/alerts")

        assert response.json() == []

    def test_empty_for_an_unknown_session(self, client: TestClient) -> None:
        response = client.get(f"/api/v1/sessions/{uuid4()}/alerts")

        assert response.status_code == 200
        assert response.json() == []


class TestWithAuth:
    def test_a_teacher_can_read_them(
        self, authed_client: TestClient, contract_example: Any
    ) -> None:
        payload = contract_example("extra_person")
        authed_client.post("/api/v1/events", json=payload, headers=bearer(STUDENT_TOKEN))

        response = authed_client.get(
            f"/api/v1/sessions/{payload['session_id']}/alerts",
            headers=bearer(TEACHER_TOKEN),
        )

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_a_student_cannot(self, authed_client: TestClient, contract_example: Any) -> None:
        # Ver las alertas sobre si mismo le ensenaria que detecciones esquivar.
        payload = contract_example("extra_person")
        authed_client.post("/api/v1/events", json=payload, headers=bearer(STUDENT_TOKEN))

        response = authed_client.get(
            f"/api/v1/sessions/{payload['session_id']}/alerts",
            headers=bearer(STUDENT_TOKEN),
        )

        assert response.status_code == 403

    def test_401_without_a_token(self, authed_client: TestClient) -> None:
        assert authed_client.get(f"/api/v1/sessions/{uuid4()}/alerts").status_code == 401


def test_alerts_are_published_in_openapi(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert "/api/v1/sessions/{session_id}/alerts" in schema["paths"]
