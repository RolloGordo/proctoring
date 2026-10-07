"""Editar, cancelar y borrar un examen por HTTP.

Lo que más importa aquí es lo que ve el **estudiante** cuando su docente cancela:
tiene que entender qué pasó, no leer "no hay ningún examen con ese código" y
revisar diez veces un código que está bien.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from proctoring_api.domain.participant import SessionParticipant

from tests.conftest import (
    CONTRACT_STUDENT_ID,
    NOW,
    OTHER_TEACHER_TOKEN,
    STUDENT_TOKEN,
    TEACHER_TOKEN,
)

pytestmark = pytest.mark.integration


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def crear_examen(client: TestClient, **extra: Any) -> dict[str, Any]:
    cuerpo: dict[str, Any] = {
        "title": "Examen editable",
        "starts_at": NOW.isoformat(),
        "duration_minutes": 60,
        **extra,
    }
    respuesta = client.post("/api/v1/sessions", json=cuerpo, headers=bearer(TEACHER_TOKEN))
    assert respuesta.status_code == 201, respuesta.text
    datos: dict[str, Any] = respuesta.json()
    return datos


class TestEscalaDeNota:
    def test_un_examen_nuevo_se_califica_sobre_veinte(self, authed_client: TestClient) -> None:
        """La escala peruana, sin tener que pedirla."""
        assert float(crear_examen(authed_client)["max_score"]) == 20.0

    def test_el_docente_puede_poner_otra_escala(self, authed_client: TestClient) -> None:
        assert float(crear_examen(authed_client, max_score="10")["max_score"]) == 10.0

    def test_una_escala_de_cero_se_rechaza(self, authed_client: TestClient) -> None:
        respuesta = authed_client.post(
            "/api/v1/sessions",
            json={
                "title": "Imposible",
                "starts_at": NOW.isoformat(),
                "duration_minutes": 60,
                "max_score": "0",
            },
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 422


class TestEditar:
    def test_se_corrige_la_fecha(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)
        nueva = (NOW + timedelta(days=2)).isoformat()

        respuesta = authed_client.patch(
            f"/api/v1/sessions/{examen['id']}",
            json={"starts_at": nueva},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["starts_at"].startswith(nueva[:16])
        assert respuesta.json()["title"] == examen["title"]

    def test_se_corrige_la_escala(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)

        respuesta = authed_client.patch(
            f"/api/v1/sessions/{examen['id']}",
            json={"max_score": "20"},
            headers=bearer(TEACHER_TOKEN),
        )

        assert float(respuesta.json()["max_score"]) == 20.0

    def test_el_codigo_de_acceso_sobrevive(self, authed_client: TestClient) -> None:
        """Si cambiara, los estudiantes que lo tienen apuntado se quedan fuera."""
        examen = crear_examen(authed_client)

        respuesta = authed_client.patch(
            f"/api/v1/sessions/{examen['id']}",
            json={"title": "Otro titulo", "duration_minutes": 120},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.json()["access_code"] == examen["access_code"]
        assert respuesta.json()["id"] == examen["id"]

    def test_un_cuerpo_vacio_no_cambia_nada(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)

        respuesta = authed_client.patch(
            f"/api/v1/sessions/{examen['id']}", json={}, headers=bearer(TEACHER_TOKEN)
        )

        assert respuesta.status_code == 200
        assert respuesta.json()["title"] == examen["title"]
        assert respuesta.json()["duration_minutes"] == examen["duration_minutes"]

    def test_un_examen_ajeno_no_se_edita(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)

        respuesta = authed_client.patch(
            f"/api/v1/sessions/{examen['id']}",
            json={"title": "Secuestrado"},
            headers=bearer(OTHER_TEACHER_TOKEN),
        )

        assert respuesta.status_code == 403

    def test_uno_inexistente_responde_igual_que_uno_ajeno(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)

        ajeno = authed_client.patch(
            f"/api/v1/sessions/{examen['id']}",
            json={"title": "x"},
            headers=bearer(OTHER_TEACHER_TOKEN),
        )
        no_existe = authed_client.patch(
            f"/api/v1/sessions/{uuid4()}",
            json={"title": "x"},
            headers=bearer(OTHER_TEACHER_TOKEN),
        )

        assert ajeno.status_code == no_existe.status_code == 403
        assert ajeno.json() == no_existe.json()

    def test_un_estudiante_no_edita(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)

        respuesta = authed_client.patch(
            f"/api/v1/sessions/{examen['id']}",
            json={"title": "Mio"},
            headers=bearer(STUDENT_TOKEN),
        )

        assert respuesta.status_code == 403

    def test_un_campo_desconocido_se_rechaza(self, authed_client: TestClient) -> None:
        """`extra="forbid"`: un typo en el nombre de un campo no puede pasar
        inadvertido y dejar al docente creyendo que cambió algo."""
        examen = crear_examen(authed_client)

        respuesta = authed_client.patch(
            f"/api/v1/sessions/{examen['id']}",
            json={"titulo": "En espanol"},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 422


class TestBorrar:
    def test_se_borra_un_examen_recien_creado(self, authed_client: TestClient) -> None:
        """El caso real: lo creó con la fecha mal hace un minuto."""
        examen = crear_examen(authed_client)

        borrado = authed_client.delete(
            f"/api/v1/sessions/{examen['id']}", headers=bearer(TEACHER_TOKEN)
        )

        assert borrado.status_code == 204
        assert (
            authed_client.get(
                f"/api/v1/sessions/{examen['id']}", headers=bearer(TEACHER_TOKEN)
            ).status_code
            == 403
        )

    def test_no_se_borra_el_examen_de_otro(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)

        borrado = authed_client.delete(
            f"/api/v1/sessions/{examen['id']}", headers=bearer(OTHER_TEACHER_TOKEN)
        )

        assert borrado.status_code == 403
        assert (
            authed_client.get(
                f"/api/v1/sessions/{examen['id']}", headers=bearer(TEACHER_TOKEN)
            ).status_code
            == 200
        )

    def test_con_estudiantes_dentro_no_se_borra(self, authed_app: FastAPI) -> None:
        """Se llevaría sus eventos, alertas y respuestas: la evidencia."""
        with TestClient(authed_app) as client:
            examen = crear_examen(client)
        matricular(authed_app, examen["id"])

        with TestClient(authed_app) as client:
            borrado = client.delete(
                f"/api/v1/sessions/{examen['id']}", headers=bearer(TEACHER_TOKEN)
            )

        assert borrado.status_code == 400
        assert "cancelalo" in borrado.json()["detail"]


def matricular(app: FastAPI, session_id: str) -> None:
    app.state.participant_repository.save(
        SessionParticipant.enroll(
            session_id=UUID(session_id),
            student_id=CONTRACT_STUDENT_ID,
            consented_at=NOW,
        ).verified(NOW)
    )


class TestCancelar:
    def test_el_examen_queda_cancelado(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)

        respuesta = authed_client.post(
            f"/api/v1/sessions/{examen['id']}/cancel", headers=bearer(TEACHER_TOKEN)
        )

        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["status"] == "cancelled"
        assert respuesta.json()["cancelled_at"] is not None

    def test_sigue_estando_para_el_docente(self, authed_client: TestClient) -> None:
        """Cancelar no es borrar: el docente conserva lo que pasó."""
        examen = crear_examen(authed_client)
        authed_client.post(f"/api/v1/sessions/{examen['id']}/cancel", headers=bearer(TEACHER_TOKEN))

        vista = authed_client.get(f"/api/v1/sessions/{examen['id']}", headers=bearer(TEACHER_TOKEN))

        assert vista.status_code == 200
        assert vista.json()["status"] == "cancelled"

    def test_al_estudiante_se_le_dice_que_fue_cancelado(self, authed_client: TestClient) -> None:
        """Lo que pidió el caso: no un error genérico sobre el código."""
        examen = crear_examen(authed_client)
        authed_client.post(f"/api/v1/sessions/{examen['id']}/cancel", headers=bearer(TEACHER_TOKEN))

        entrada = authed_client.post(
            "/api/v1/sessions/join",
            json={"access_code": examen["access_code"]},
            headers=bearer(STUDENT_TOKEN),
        )

        assert entrada.status_code == 400
        detalle = entrada.json()["detail"]
        assert "cancel" in detalle.lower()
        # Y no el mensaje de "ese código no existe", que lo mandaría a revisar
        # un código que está bien.
        assert "Revísalo" not in detalle

    def test_un_codigo_inventado_sigue_diciendo_que_no_existe(
        self, authed_client: TestClient
    ) -> None:
        """El mensaje de cancelado solo aparece con un código que de verdad
        existió: si no, serviría para tantear códigos."""
        entrada = authed_client.post(
            "/api/v1/sessions/join",
            json={"access_code": "ZZZZZZ"},
            headers=bearer(STUDENT_TOKEN),
        )

        assert "cancel" not in entrada.json()["detail"].lower()

    def test_quien_ya_estaba_dentro_tambien_se_entera(self, authed_app: FastAPI) -> None:
        with TestClient(authed_app) as client:
            examen = crear_examen(client)
            client.post(
                f"/api/v1/sessions/{examen['id']}/questions",
                json={
                    "questions": [
                        {
                            "question_type": "essay",
                            "statement": "Explica RLS",
                            "points": "5",
                        }
                    ]
                },
                headers=bearer(TEACHER_TOKEN),
            )
        matricular(authed_app, examen["id"])

        with TestClient(authed_app) as client:
            antes = client.get(
                f"/api/v1/exam/{examen['id']}/questions", headers=bearer(STUDENT_TOKEN)
            )
            assert antes.status_code == 200, antes.text

            client.post(f"/api/v1/sessions/{examen['id']}/cancel", headers=bearer(TEACHER_TOKEN))
            despues = client.get(
                f"/api/v1/exam/{examen['id']}/questions", headers=bearer(STUDENT_TOKEN)
            )

        assert despues.status_code == 400
        assert "cancelo" in despues.json()["detail"].lower()

    def test_cancelar_dos_veces_se_rechaza(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)
        authed_client.post(f"/api/v1/sessions/{examen['id']}/cancel", headers=bearer(TEACHER_TOKEN))

        segunda = authed_client.post(
            f"/api/v1/sessions/{examen['id']}/cancel", headers=bearer(TEACHER_TOKEN)
        )

        assert segunda.status_code == 400

    def test_no_se_cancela_el_examen_de_otro(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)

        respuesta = authed_client.post(
            f"/api/v1/sessions/{examen['id']}/cancel", headers=bearer(OTHER_TEACHER_TOKEN)
        )

        assert respuesta.status_code == 403


class TestEditarPreguntas:
    def crear_pregunta(self, client: TestClient, session_id: str) -> dict[str, Any]:
        respuesta = client.post(
            f"/api/v1/sessions/{session_id}/questions",
            json={
                "questions": [
                    {
                        "question_type": "multiple_choice",
                        "statement": "¿Qué hace RLS?",
                        "points": "2",
                        "options": [
                            {"option_text": "Filtra filas", "is_correct": True},
                            {"option_text": "Comprime", "is_correct": False},
                        ],
                    }
                ]
            },
            headers=bearer(TEACHER_TOKEN),
        )
        assert respuesta.status_code == 201, respuesta.text
        creada: dict[str, Any] = respuesta.json()[0]
        return creada

    def test_se_cambian_los_puntos(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)
        pregunta = self.crear_pregunta(authed_client, examen["id"])

        respuesta = authed_client.patch(
            f"/api/v1/questions/{pregunta['id']}",
            json={"points": "5"},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 200, respuesta.text
        assert float(respuesta.json()["points"]) == 5.0
        assert respuesta.json()["statement"] == pregunta["statement"]

    def test_se_corrige_una_errata(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)
        pregunta = self.crear_pregunta(authed_client, examen["id"])

        respuesta = authed_client.patch(
            f"/api/v1/questions/{pregunta['id']}",
            json={"statement": "¿Qué garantiza Row Level Security?"},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.json()["statement"] == "¿Qué garantiza Row Level Security?"
        assert len(respuesta.json()["options"]) == 2

    def test_se_borra_una_pregunta(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)
        pregunta = self.crear_pregunta(authed_client, examen["id"])

        borrada = authed_client.delete(
            f"/api/v1/questions/{pregunta['id']}", headers=bearer(TEACHER_TOKEN)
        )

        assert borrada.status_code == 204
        quedan = authed_client.get(
            f"/api/v1/sessions/{examen['id']}/questions", headers=bearer(TEACHER_TOKEN)
        )
        assert quedan.json() == []

    def test_una_pregunta_ajena_no_se_toca(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)
        pregunta = self.crear_pregunta(authed_client, examen["id"])

        editar = authed_client.patch(
            f"/api/v1/questions/{pregunta['id']}",
            json={"points": "99"},
            headers=bearer(OTHER_TEACHER_TOKEN),
        )
        borrar = authed_client.delete(
            f"/api/v1/questions/{pregunta['id']}", headers=bearer(OTHER_TEACHER_TOKEN)
        )

        assert editar.status_code == borrar.status_code == 403

    def test_un_estudiante_no_edita_preguntas(self, authed_client: TestClient) -> None:
        examen = crear_examen(authed_client)
        pregunta = self.crear_pregunta(authed_client, examen["id"])

        respuesta = authed_client.patch(
            f"/api/v1/questions/{pregunta['id']}",
            json={"statement": "La respuesta es la A"},
            headers=bearer(STUDENT_TOKEN),
        )

        assert respuesta.status_code == 403


class TestPanelDelEstudiante:
    def test_un_examen_cancelado_se_marca_en_el_panel(self, authed_app: FastAPI) -> None:
        """Sin esto el panel diría "empieza en 3 horas" de un examen que no va a
        ocurrir."""
        with TestClient(authed_app) as client:
            examen = crear_examen(client)
        matricular(authed_app, examen["id"])

        with TestClient(authed_app) as client:
            antes = client.get("/api/v1/me/exams", headers=bearer(STUDENT_TOKEN)).json()
            assert [e["cancelled"] for e in antes] == [False]

            client.post(
                f"/api/v1/sessions/{examen['id']}/cancel", headers=bearer(TEACHER_TOKEN)
            )
            despues = client.get("/api/v1/me/exams", headers=bearer(STUDENT_TOKEN)).json()

        assert [e["cancelled"] for e in despues] == [True]
        # Sigue apareciendo: el estudiante tiene que poder verlo, no que
        # desaparezca sin explicación.
        assert despues[0]["title"] == examen["title"]

    def test_la_nota_se_informa_sobre_la_escala_del_examen(self, authed_app: FastAPI) -> None:
        with TestClient(authed_app) as client:
            examen = crear_examen(client, max_score="20")
        matricular(authed_app, examen["id"])

        with TestClient(authed_app) as client:
            [mio] = client.get("/api/v1/me/exams", headers=bearer(STUDENT_TOKEN)).json()

        assert mio["max_score"] == 20.0
