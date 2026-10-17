"""Endpoints de eventos, de punta a punta con `TestClient`.

Los cuerpos validos salen de `packages/contracts/examples`, la misma fuente que
usan la app de escritorio y el spike de vision. Si alguien cambia el contrato sin
tocar la API, estas pruebas se ponen rojas.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

EVENT_TYPES = [
    "focus_lost",
    "gaze_away",
    "face_absent",
    "extra_person",
    "extra_display",
    "suspicious_process",
    "screen_share",
    "speech_detected",
    "identity_check",
]

pytestmark = pytest.mark.integration


class TestPostEvent:
    @pytest.mark.parametrize("event_type", EVENT_TYPES)
    def test_every_contract_example_is_accepted(
        self, client: TestClient, contract_example: Any, event_type: str
    ) -> None:
        response = client.post("/api/v1/events", json=contract_example(event_type))

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["severity"] in {"low", "medium", "high"}
        assert body["id"]

    def test_returns_the_expected_severity(self, client: TestClient, contract_example: Any) -> None:
        # El ejemplo de extra_person es una senal inequivoca.
        response = client.post("/api/v1/events", json=contract_example("extra_person"))
        assert response.json()["severity"] == "high"

        # Y el de speech_detected no acusa a nadie hasta que la IA lo confirme.
        response = client.post("/api/v1/events", json=contract_example("speech_detected"))
        assert response.json()["severity"] == "low"


class TestValidationErrors:
    """422 = el cuerpo no cumple el contrato. 400 = viola una regla de negocio."""

    def test_422_when_a_required_field_is_missing(self, client: TestClient) -> None:
        response = client.post("/api/v1/events", json={"session_id": str(uuid4())})
        assert response.status_code == 422

    def test_422_on_unknown_event_type(self, client: TestClient, contract_example: Any) -> None:
        payload = contract_example("focus_lost")
        payload["event_type"] = "mind_reading"

        assert client.post("/api/v1/events", json=payload).status_code == 422

    def test_422_on_negative_duration(self, client: TestClient, contract_example: Any) -> None:
        payload = contract_example("focus_lost")
        payload["duration_ms"] = -1

        assert client.post("/api/v1/events", json=payload).status_code == 422

    def test_422_on_unknown_field(self, client: TestClient, contract_example: Any) -> None:
        # additionalProperties: false en el contrato. Una clave mal escrita en el
        # cliente falla aqui en vez de perderse en silencio.
        payload = contract_example("focus_lost")
        payload["duracion_ms"] = 500

        assert client.post("/api/v1/events", json=payload).status_code == 422

    def test_422_on_malformed_uuid(self, client: TestClient, contract_example: Any) -> None:
        payload = contract_example("focus_lost")
        payload["session_id"] = "no-soy-un-uuid"

        assert client.post("/api/v1/events", json=payload).status_code == 422

    @pytest.mark.parametrize("event_type", ["speech_detected", "gaze_away"])
    def test_400_when_question_id_is_missing(
        self, client: TestClient, contract_example: Any, event_type: str
    ) -> None:
        payload = contract_example(event_type)
        payload["question_id"] = None

        response = client.post("/api/v1/events", json=payload)

        assert response.status_code == 400
        assert "question_id" in response.json()["detail"]

    def test_400_on_naive_started_at(self, client: TestClient, contract_example: Any) -> None:
        payload = contract_example("focus_lost")
        payload["started_at"] = "2026-10-03T14:21:05"

        response = client.post("/api/v1/events", json=payload)

        assert response.status_code == 400
        assert "zona horaria" in response.json()["detail"]

    def test_400_on_a_timestamp_from_the_future(
        self, client: TestClient, contract_example: Any
    ) -> None:
        payload = contract_example("focus_lost")
        payload["started_at"] = "2099-01-01T00:00:00Z"

        response = client.post("/api/v1/events", json=payload)

        assert response.status_code == 400
        assert "futuro" in response.json()["detail"]


class TestListSessionEvents:
    def test_returns_what_was_registered(self, client: TestClient, contract_example: Any) -> None:
        payload = contract_example("focus_lost")
        client.post("/api/v1/events", json=payload)

        response = client.get(f"/api/v1/sessions/{payload['session_id']}/events")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["event_type"] == "focus_lost"
        assert body[0]["severity"] == "medium"
        assert body[0]["started_at"].startswith("2026-10-03T14:21:05")

    def test_filters_by_student(self, client: TestClient, contract_example: Any) -> None:
        payload = contract_example("focus_lost")
        client.post("/api/v1/events", json=payload)

        session_id = payload["session_id"]
        mine = client.get(
            f"/api/v1/sessions/{session_id}/events",
            params={"student_id": payload["student_id"]},
        )
        other = client.get(
            f"/api/v1/sessions/{session_id}/events",
            params={"student_id": str(uuid4())},
        )

        assert len(mine.json()) == 1
        assert other.json() == []

    def test_is_ordered_chronologically(self, client: TestClient, contract_example: Any) -> None:
        later = contract_example("extra_person")
        earlier = contract_example("extra_display")
        client.post("/api/v1/events", json=later)
        client.post("/api/v1/events", json=earlier)

        response = client.get(f"/api/v1/sessions/{later['session_id']}/events")

        timestamps = [event["started_at"] for event in response.json()]
        assert timestamps == sorted(timestamps)

    def test_empty_for_an_unknown_session(self, client: TestClient) -> None:
        response = client.get(f"/api/v1/sessions/{uuid4()}/events")

        assert response.status_code == 200
        assert response.json() == []

    def test_422_on_malformed_session_id(self, client: TestClient) -> None:
        assert client.get("/api/v1/sessions/no-soy-un-uuid/events").status_code == 422
