"""Endpoints de sesiones de examen."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import STUDENT_TOKEN, TEACHER_TOKEN

pytestmark = pytest.mark.integration


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def a_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": "Examen parcial de Taller Integrador",
        "starts_at": "2026-10-10T14:00:00Z",
        "duration_minutes": 90,
    }
    body.update(overrides)
    return body


class TestCreate:
    def test_creates_a_session_with_an_access_code(self, client: TestClient) -> None:
        response = client.post("/api/v1/sessions", json=a_body())

        assert response.status_code == 201, response.text
        body = response.json()
        assert len(body["access_code"]) == 6
        assert body["status"] == "scheduled"
        assert body["ends_at"] == "2026-10-10T15:30:00Z"

    def test_the_preset_decides_the_modules(self, client: TestClient) -> None:
        body = client.post("/api/v1/sessions", json=a_body(preset="strict")).json()

        # El diferencial del proyecto tiene que estar en el nivel mas alto, con
        # sus umbrales, que es lo que la app y el spike de vision necesitan.
        assert "ai_voice" in body["modules"]
        assert body["modules"]["gaze"] == {"yaw_degrees": 25, "min_duration_ms": 3000}

    def test_basic_is_lighter_than_strict(self, client: TestClient) -> None:
        basic = client.post("/api/v1/sessions", json=a_body(preset="basic")).json()
        strict = client.post("/api/v1/sessions", json=a_body(preset="strict")).json()

        assert set(basic["modules"]) < set(strict["modules"])

    def test_custom_takes_the_modules_sent(self, client: TestClient) -> None:
        body = client.post(
            "/api/v1/sessions",
            json=a_body(preset="custom", modules={"gaze": {"yaw_degrees": 30}}),
        ).json()

        assert body["modules"] == {"gaze": {"yaw_degrees": 30}}

    def test_400_on_custom_without_modules(self, client: TestClient) -> None:
        response = client.post("/api/v1/sessions", json=a_body(preset="custom"))

        assert response.status_code == 400
        assert "custom" in response.json()["detail"]

    def test_422_on_a_blank_title(self, client: TestClient) -> None:
        assert client.post("/api/v1/sessions", json=a_body(title="")).status_code == 422

    def test_422_on_a_non_positive_duration(self, client: TestClient) -> None:
        response = client.post("/api/v1/sessions", json=a_body(duration_minutes=0))

        assert response.status_code == 422

    def test_422_on_an_unknown_field(self, client: TestClient) -> None:
        response = client.post("/api/v1/sessions", json=a_body(profesor="Walter"))

        assert response.status_code == 422

    def test_400_on_a_naive_start(self, client: TestClient) -> None:
        response = client.post("/api/v1/sessions", json=a_body(starts_at="2026-10-10T14:00:00"))

        assert response.status_code == 400
        assert "zona horaria" in response.json()["detail"]

    def test_access_codes_do_not_repeat(self, client: TestClient) -> None:
        codes = {
            client.post("/api/v1/sessions", json=a_body()).json()["access_code"] for _ in range(10)
        }

        assert len(codes) == 10


class TestListAndGet:
    def test_lists_what_was_created(self, client: TestClient) -> None:
        created = client.post("/api/v1/sessions", json=a_body()).json()

        body = client.get("/api/v1/sessions").json()

        assert [session["id"] for session in body] == [created["id"]]

    def test_newest_first(self, client: TestClient) -> None:
        client.post("/api/v1/sessions", json=a_body(starts_at="2026-10-05T14:00:00Z"))
        client.post("/api/v1/sessions", json=a_body(starts_at="2026-10-20T14:00:00Z"))

        starts = [session["starts_at"] for session in client.get("/api/v1/sessions").json()]

        assert starts == sorted(starts, reverse=True)

    def test_detail_includes_the_modules(self, client: TestClient) -> None:
        created = client.post("/api/v1/sessions", json=a_body(preset="strict")).json()

        detail = client.get(f"/api/v1/sessions/{created['id']}").json()

        assert detail["modules"] == created["modules"]
        assert detail["access_code"] == created["access_code"]


class TestAuthorization:
    def test_a_teacher_creates_and_lists_their_own(self, authed_client: TestClient) -> None:
        created = authed_client.post(
            "/api/v1/sessions", json=a_body(), headers=bearer(TEACHER_TOKEN)
        )
        assert created.status_code == 201

        listed = authed_client.get("/api/v1/sessions", headers=bearer(TEACHER_TOKEN))
        assert created.json()["id"] in [s["id"] for s in listed.json()]

    def test_403_when_a_student_creates(self, authed_client: TestClient) -> None:
        response = authed_client.post(
            "/api/v1/sessions", json=a_body(), headers=bearer(STUDENT_TOKEN)
        )

        assert response.status_code == 403

    def test_403_when_a_student_lists(self, authed_client: TestClient) -> None:
        response = authed_client.get("/api/v1/sessions", headers=bearer(STUDENT_TOKEN))

        assert response.status_code == 403

    def test_401_without_a_token(self, authed_client: TestClient) -> None:
        assert authed_client.get("/api/v1/sessions").status_code == 401

    def test_403_reading_an_unknown_session(self, authed_client: TestClient) -> None:
        # Una sesion ajena y una inexistente responden lo mismo, para no permitir
        # averiguar que sesiones existen.
        response = authed_client.get(f"/api/v1/sessions/{uuid4()}", headers=bearer(TEACHER_TOKEN))

        assert response.status_code == 403


def test_sessions_are_published_in_openapi(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/sessions" in paths
    assert "/api/v1/sessions/{session_id}" in paths
