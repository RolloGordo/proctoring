"""El flujo docente de Rider (5/11/2026): cursos, bancos y selección por examen.

Llegó sin pruebas; estas cubren cada endpoint nuevo, quién puede usarlo y lo
que promete: borrar solo un curso vacío, editar un banco sin tocar sus
preguntas, y escoger preguntas y puntos por examen sin cambiar los bancos.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import OTHER_TEACHER_TOKEN, STUDENT_TOKEN, TEACHER_TOKEN
from tests.integration.http.test_banks import (
    bearer,
    crear_banco,
    crear_examen,
    llenar,
    matricular,
)

pytestmark = pytest.mark.integration

A = bearer(TEACHER_TOKEN)
B = bearer(OTHER_TEACHER_TOKEN)
ESTUDIANTE = bearer(STUDENT_TOKEN)


def crear_curso(client: TestClient, nombre: str = "Bases de datos") -> str:
    respuesta = client.post("/api/v1/courses", json={"name": nombre}, headers=A)
    assert respuesta.status_code == 201, respuesta.text
    course_id: str = respuesta.json()["id"]
    return course_id


def examen_con_dos_bancos(client: TestClient) -> dict[str, Any]:
    uno = crear_banco(client, TEACHER_TOKEN, "Banco uno")
    dos = crear_banco(client, TEACHER_TOKEN, "Banco dos")
    llenar(client, uno, TEACHER_TOKEN, 3)
    llenar(client, dos, TEACHER_TOKEN, 2)
    session_id = crear_examen(client)
    for bank_id in (uno, dos):
        atado = client.post(
            f"/api/v1/sessions/{session_id}/banks", json={"bank_id": bank_id}, headers=A
        )
        assert atado.status_code == 200, atado.text
    return {"sesion": session_id, "uno": uno, "dos": dos}


def seleccion(client: TestClient, session_id: str, headers: dict[str, str] = A) -> Any:
    return client.get(f"/api/v1/sessions/{session_id}/bank-questions", headers=headers)


def guardar(client: TestClient, session_id: str, cuerpo: dict[str, Any], **kw: Any) -> Any:
    return client.put(
        f"/api/v1/sessions/{session_id}/bank-question-selection",
        json=cuerpo,
        headers=kw.get("headers", A),
    )


class TestBorrarCurso:
    def test_un_curso_vacio_se_borra(self, authed_client: TestClient) -> None:
        course_id = crear_curso(authed_client)

        respuesta = authed_client.delete(f"/api/v1/courses/{course_id}", headers=A)

        assert respuesta.status_code == 204
        assert authed_client.get(f"/api/v1/courses/{course_id}", headers=A).status_code in (
            403,
            404,
        )

    def test_con_un_examen_no(self, authed_client: TestClient) -> None:
        course_id = crear_curso(authed_client)
        authed_client.post(
            "/api/v1/sessions",
            json={
                "title": "Parcial",
                "starts_at": "2026-12-01T10:00:00Z",
                "duration_minutes": 60,
                "course_id": course_id,
            },
            headers=A,
        )

        respuesta = authed_client.delete(f"/api/v1/courses/{course_id}", headers=A)

        assert respuesta.status_code == 400
        assert "exámenes" in respuesta.json()["detail"]

    def test_con_un_banco_no(self, authed_client: TestClient) -> None:
        course_id = crear_curso(authed_client)
        authed_client.post(
            "/api/v1/question-banks", json={"name": "Banco", "course_id": course_id}, headers=A
        )

        respuesta = authed_client.delete(f"/api/v1/courses/{course_id}", headers=A)

        assert respuesta.status_code == 400
        assert "bancos" in respuesta.json()["detail"]

    @pytest.mark.parametrize("quien", [B, ESTUDIANTE])
    def test_nadie_mas_lo_borra(self, authed_client: TestClient, quien: dict[str, str]) -> None:
        course_id = crear_curso(authed_client)

        respuesta = authed_client.delete(f"/api/v1/courses/{course_id}", headers=quien)

        assert respuesta.status_code == 403
        assert authed_client.get(f"/api/v1/courses/{course_id}", headers=A).status_code == 200


class TestEditarBanco:
    def test_cambia_nombre_descripcion_y_curso_sin_tocar_preguntas(
        self, authed_client: TestClient
    ) -> None:
        bank_id = crear_banco(authed_client, TEACHER_TOKEN)
        llenar(authed_client, bank_id, TEACHER_TOKEN, 3)
        course_id = crear_curso(authed_client)

        respuesta = authed_client.patch(
            f"/api/v1/question-banks/{bank_id}",
            json={"name": "SQL avanzado", "description": "Unidad 3", "course_id": course_id},
            headers=A,
        )

        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        assert (cuerpo["name"], cuerpo["description"], cuerpo["course_id"]) == (
            "SQL avanzado",
            "Unidad 3",
            course_id,
        )
        preguntas = authed_client.get(f"/api/v1/question-banks/{bank_id}/questions", headers=A)
        assert len(preguntas.json()) == 3

    def test_se_puede_soltar_el_curso_y_la_descripcion(self, authed_client: TestClient) -> None:
        course_id = crear_curso(authed_client)
        creado = authed_client.post(
            "/api/v1/question-banks",
            json={"name": "Banco", "course_id": course_id, "description": "nota"},
            headers=A,
        ).json()

        respuesta = authed_client.patch(
            f"/api/v1/question-banks/{creado['id']}",
            json={"clear_course": True, "clear_description": True},
            headers=A,
        )

        assert respuesta.json()["course_id"] is None
        assert respuesta.json()["description"] is None

    def test_no_se_cuelga_del_curso_de_otro_docente(self, authed_client: TestClient) -> None:
        ajeno = authed_client.post("/api/v1/courses", json={"name": "Ajeno"}, headers=B).json()
        bank_id = crear_banco(authed_client, TEACHER_TOKEN)

        respuesta = authed_client.patch(
            f"/api/v1/question-banks/{bank_id}", json={"course_id": ajeno["id"]}, headers=A
        )

        assert respuesta.status_code == 403

    @pytest.mark.parametrize("quien", [B, ESTUDIANTE])
    def test_nadie_mas_lo_edita(self, authed_client: TestClient, quien: dict[str, str]) -> None:
        bank_id = crear_banco(authed_client, TEACHER_TOKEN)

        respuesta = authed_client.patch(
            f"/api/v1/question-banks/{bank_id}", json={"name": "Robado"}, headers=quien
        )

        assert respuesta.status_code == 403


class TestSeleccionPorExamen:
    def test_junta_las_preguntas_de_todos_los_bancos_con_su_origen(
        self, authed_client: TestClient
    ) -> None:
        datos = examen_con_dos_bancos(authed_client)

        cuerpo = seleccion(authed_client, datos["sesion"]).json()

        assert len(cuerpo) == 5
        assert {item["bank_name"] for item in cuerpo} == {"Banco uno", "Banco dos"}
        assert all(item["included"] for item in cuerpo)

    def test_excluir_y_puntuar_no_cambia_los_bancos(self, authed_client: TestClient) -> None:
        datos = examen_con_dos_bancos(authed_client)
        todas = seleccion(authed_client, datos["sesion"]).json()
        fuera = todas[0]["question"]["id"]
        puntuada = todas[1]["question"]["id"]

        respuesta = guardar(
            authed_client,
            datos["sesion"],
            {
                "excluded_question_ids": [fuera],
                "question_points": [{"question_id": puntuada, "points": "1.25"}],
            },
        )

        assert respuesta.status_code == 200, respuesta.text
        por_id = {item["question"]["id"]: item for item in respuesta.json()}
        assert por_id[fuera]["included"] is False
        assert float(por_id[puntuada]["question"]["points"]) == 1.25
        # El banco sigue con sus preguntas y sus puntos originales.
        del_banco = authed_client.get(
            f"/api/v1/question-banks/{datos['uno']}/questions", headers=A
        ).json()
        assert len(del_banco) == 3
        assert all(float(q["points"]) == 1 for q in del_banco)

    def test_el_estudiante_recibe_la_seleccion_y_los_puntos(self, authed_app: FastAPI) -> None:
        with TestClient(authed_app) as client:
            datos = examen_con_dos_bancos(client)
            todas = seleccion(client, datos["sesion"]).json()
            fuera = todas[0]["question"]["id"]
            puntuada = todas[1]["question"]
            guardar(
                client,
                datos["sesion"],
                {
                    "excluded_question_ids": [fuera],
                    "question_points": [{"question_id": puntuada["id"], "points": "2.50"}],
                },
            )
        matricular(authed_app, datos["sesion"])

        with TestClient(authed_app) as client:
            recibidas = client.get(
                f"/api/v1/exam/{datos['sesion']}/questions", headers=ESTUDIANTE
            ).json()

        ids = {q["id"] for q in recibidas}
        assert fuera not in ids
        assert len(recibidas) == 4
        assert float(next(q for q in recibidas if q["id"] == puntuada["id"])["points"]) == 2.5

    def test_no_se_dejan_todas_fuera(self, authed_client: TestClient) -> None:
        datos = examen_con_dos_bancos(authed_client)
        todas = [i["question"]["id"] for i in seleccion(authed_client, datos["sesion"]).json()]

        respuesta = guardar(authed_client, datos["sesion"], {"excluded_question_ids": todas})

        assert respuesta.status_code == 400

    def test_no_se_excluye_una_pregunta_que_no_es_del_examen(
        self, authed_client: TestClient
    ) -> None:
        datos = examen_con_dos_bancos(authed_client)

        respuesta = guardar(
            authed_client, datos["sesion"], {"excluded_question_ids": [str(uuid4())]}
        )

        assert respuesta.status_code == 400

    @pytest.mark.parametrize("puntos", ["-1", "100.01", "1.234"])
    def test_los_puntos_van_de_0_a_100_con_dos_decimales(
        self, authed_client: TestClient, puntos: str
    ) -> None:
        datos = examen_con_dos_bancos(authed_client)
        una = seleccion(authed_client, datos["sesion"]).json()[0]["question"]["id"]

        respuesta = guardar(
            authed_client,
            datos["sesion"],
            {"question_points": [{"question_id": una, "points": puntos}]},
        )

        assert respuesta.status_code in (400, 422)

    def test_con_estudiantes_dentro_no_se_cambia(self, authed_app: FastAPI) -> None:
        with TestClient(authed_app) as client:
            datos = examen_con_dos_bancos(client)
        matricular(authed_app, datos["sesion"])

        with TestClient(authed_app) as client:
            una = seleccion(client, datos["sesion"]).json()[0]["question"]["id"]
            respuesta = guardar(client, datos["sesion"], {"excluded_question_ids": [una]})

        # Un examen en uso es un `DomainError`: 400 con el motivo, como en el resto
        # de la API.
        assert respuesta.status_code == 400
        assert "participantes" in respuesta.json()["detail"]

    @pytest.mark.parametrize("quien", [B, ESTUDIANTE])
    def test_nadie_mas_la_ve_ni_la_cambia(
        self, authed_client: TestClient, quien: dict[str, str]
    ) -> None:
        datos = examen_con_dos_bancos(authed_client)

        # La revisión trae las respuestas correctas: solo el docente del examen.
        assert seleccion(authed_client, datos["sesion"], headers=quien).status_code == 403
        assert (
            guardar(
                authed_client, datos["sesion"], {"excluded_question_ids": []}, headers=quien
            ).status_code
            == 403
        )
