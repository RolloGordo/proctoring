"""Los endpoints de la portada de un curso, de punta a punta con adaptadores en memoria."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import OTHER_TEACHER_TOKEN, STUDENT_TOKEN, TEACHER_TOKEN

pytestmark = pytest.mark.integration


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


A = bearer(TEACHER_TOKEN)


def crear_curso(client: TestClient) -> str:
    respuesta = client.post("/api/v1/courses", json={"name": "Taller Integrador 1"}, headers=A)
    assert respuesta.status_code == 201, respuesta.text
    course_id: str = respuesta.json()["id"]
    return course_id


def pedir_subida(client: TestClient, course_id: str, **kw: Any) -> Any:
    return client.post(
        f"/api/v1/courses/{course_id}/cover/upload-url",
        json={"content_type": kw.get("formato", "image/webp")},
        headers=kw.get("headers", A),
    )


def test_subir_fijar_ver_y_quitar(authed_client: TestClient) -> None:
    course_id = crear_curso(authed_client)
    assert authed_client.get(f"/api/v1/courses/{course_id}", headers=A).json()["cover_url"] is None

    firma = pedir_subida(authed_client, course_id)
    assert firma.status_code == 200, firma.text
    ruta = firma.json()["path"]
    assert ruta.startswith(f"{course_id}/")

    fijada = authed_client.put(f"/api/v1/courses/{course_id}/cover", json={"path": ruta}, headers=A)
    assert fijada.status_code == 200, fijada.text
    assert ruta in fijada.json()["cover_url"]

    lista = authed_client.get("/api/v1/courses", headers=A).json()
    assert ruta in next(c for c in lista if c["id"] == course_id)["cover_url"]

    quitada = authed_client.delete(f"/api/v1/courses/{course_id}/cover", headers=A)
    assert quitada.status_code == 200
    assert quitada.json()["cover_url"] is None


@pytest.mark.parametrize("formato", ["image/gif", "image/svg+xml", "text/html"])
def test_solo_imagenes_admitidas(authed_client: TestClient, formato: str) -> None:
    course_id = crear_curso(authed_client)

    assert pedir_subida(authed_client, course_id, formato=formato).status_code == 422


def test_no_se_fija_una_ruta_cualquiera(authed_client: TestClient) -> None:
    course_id = crear_curso(authed_client)

    respuesta = authed_client.put(
        f"/api/v1/courses/{course_id}/cover",
        json={"path": "evidences/otra-cosa.jpg"},
        headers=A,
    )

    assert respuesta.status_code == 400


@pytest.mark.parametrize("token", [OTHER_TEACHER_TOKEN, STUDENT_TOKEN])
def test_nadie_mas_toca_la_portada(authed_client: TestClient, token: str) -> None:
    course_id = crear_curso(authed_client)
    ruta = pedir_subida(authed_client, course_id).json()["path"]
    ajeno = bearer(token)

    assert pedir_subida(authed_client, course_id, headers=ajeno).status_code == 403
    assert (
        authed_client.put(
            f"/api/v1/courses/{course_id}/cover", json={"path": ruta}, headers=ajeno
        ).status_code
        == 403
    )
    assert (
        authed_client.delete(f"/api/v1/courses/{course_id}/cover", headers=ajeno).status_code == 403
    )


def test_el_estudiante_matriculado_ve_la_portada(authed_app: Any) -> None:
    from tests.integration.http.test_courses import CORREO_ESTUDIANTE, registrar_perfiles

    registrar_perfiles(authed_app)
    with TestClient(authed_app) as client:
        course_id = crear_curso(client)
        ruta = pedir_subida(client, course_id).json()["path"]
        client.put(f"/api/v1/courses/{course_id}/cover", json={"path": ruta}, headers=A)
        client.post(
            f"/api/v1/courses/{course_id}/students", json={"email": CORREO_ESTUDIANTE}, headers=A
        )

        [clase] = client.get("/api/v1/me/courses", headers=bearer(STUDENT_TOKEN)).json()

    assert clase["id"] == course_id
    assert ruta in clase["cover_url"]


def test_el_estudiante_sin_portada_recibe_null(authed_app: Any) -> None:
    from tests.integration.http.test_courses import CORREO_ESTUDIANTE, registrar_perfiles

    registrar_perfiles(authed_app)
    with TestClient(authed_app) as client:
        course_id = crear_curso(client)
        client.post(
            f"/api/v1/courses/{course_id}/students", json={"email": CORREO_ESTUDIANTE}, headers=A
        )

        [clase] = client.get("/api/v1/me/courses", headers=bearer(STUDENT_TOKEN)).json()

    assert clase["cover_url"] is None
