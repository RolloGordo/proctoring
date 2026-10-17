"""Endpoint de subida de evidencia, de punta a punta."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import CONTRACT_STUDENT_ID, OTHER_STUDENT_TOKEN, STUDENT_TOKEN, TEACHER_TOKEN

pytestmark = pytest.mark.integration

SESSION = uuid4()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def a_body(
    student_id: UUID | None = None, kind: str = "image", extension: str = "jpg"
) -> dict[str, str]:
    return {
        "session_id": str(SESSION),
        "student_id": str(student_id or CONTRACT_STUDENT_ID),
        "kind": kind,
        "extension": extension,
    }


class TestWithoutAuth:
    def test_returns_a_signed_upload(self, client: TestClient) -> None:
        response = client.post("/api/v1/evidence/upload-url", json=a_body())

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["path"].startswith(f"{SESSION}/{CONTRACT_STUDENT_ID}/")
        assert body["path"].endswith(".jpg")
        assert body["url"]
        assert body["expires_in_seconds"] > 0

    def test_400_on_a_forbidden_extension(self, client: TestClient) -> None:
        response = client.post("/api/v1/evidence/upload-url", json=a_body(extension="exe"))

        assert response.status_code == 400
        assert "no permitida" in response.json()["detail"]

    def test_422_on_an_unknown_kind(self, client: TestClient) -> None:
        response = client.post("/api/v1/evidence/upload-url", json=a_body(kind="video"))

        assert response.status_code == 422

    def test_422_on_an_unknown_field(self, client: TestClient) -> None:
        body = a_body()
        body["bucket"] = "evidences"

        assert client.post("/api/v1/evidence/upload-url", json=body).status_code == 422


class TestWithAuth:
    def test_a_student_gets_a_url_for_themselves(self, authed_client: TestClient) -> None:
        response = authed_client.post(
            "/api/v1/evidence/upload-url", json=a_body(), headers=bearer(STUDENT_TOKEN)
        )

        assert response.status_code == 201

    def test_403_for_another_students_evidence(self, authed_client: TestClient) -> None:
        response = authed_client.post(
            "/api/v1/evidence/upload-url",
            json=a_body(),
            headers=bearer(OTHER_STUDENT_TOKEN),
        )

        assert response.status_code == 403

    def test_403_for_a_teacher(self, authed_client: TestClient) -> None:
        response = authed_client.post(
            "/api/v1/evidence/upload-url", json=a_body(), headers=bearer(TEACHER_TOKEN)
        )

        assert response.status_code == 403

    def test_401_without_a_token(self, authed_client: TestClient) -> None:
        response = authed_client.post("/api/v1/evidence/upload-url", json=a_body())

        assert response.status_code == 401


def test_the_returned_path_is_accepted_as_evidence_path(client: TestClient) -> None:
    """El `path` que devuelve este endpoint vale tal cual en el evento.

    Es el flujo completo del cliente: pedir la URL, subir, y mandar el evento.
    Si estos dos extremos no encajan, el cliente se queda a medias.
    """
    upload = client.post("/api/v1/evidence/upload-url", json=a_body()).json()

    event = {
        "session_id": str(SESSION),
        "student_id": str(CONTRACT_STUDENT_ID),
        "event_type": "face_absent",
        "started_at": "2026-10-03T14:25:10.500Z",
        "duration_ms": 6300,
        "evidence_path": upload["path"],
    }

    assert client.post("/api/v1/events", json=event).status_code == 201


def test_evidence_endpoint_is_published_in_openapi(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert "/api/v1/evidence/upload-url" in schema["paths"]
