"""Endpoints de preguntas, con el foco en que la respuesta correcta no se filtre."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from proctoring_api.application.use_cases.manage_enrollment import DEFAULT_DEV_STUDENT_ID
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.participant import SessionParticipant

from tests.conftest import NOW, STUDENT_TOKEN, TEACHER_ID, TEACHER_TOKEN

pytestmark = pytest.mark.integration


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


UNA_PREGUNTA: dict[str, Any] = {
    "question_type": "multiple_choice",
    "statement": "¿Qué hace RLS en PostgreSQL?",
    "points": "2",
    "options": [
        {"option_text": "Filtra filas por usuario", "is_correct": True},
        {"option_text": "Comprime la base", "is_correct": False},
        {"option_text": "Cifra el disco", "is_correct": False},
    ],
}


def matricular_verificado(app: Any, session_id: str, student_id: Any = None) -> None:
    """Matricula al estudiante y le da la identidad por verificada.

    Pedir el examen exige estar matriculado: es la regla que impide que conocer
    un `session_id` ajeno de acceso a sus preguntas.
    """
    from uuid import UUID

    participante = SessionParticipant.enroll(
        session_id=UUID(session_id),
        student_id=student_id or DEFAULT_DEV_STUDENT_ID,
        consented_at=NOW,
    ).verified(NOW)
    app.state.participant_repository.save(participante)


def sesion_abierta(app: Any, *, teacher_id: Any = None) -> str:
    """Crea una sesion en curso y devuelve su id."""
    sesion = ExamSession.create(
        teacher_id=teacher_id or TEACHER_ID,
        title="Parcial",
        starts_at=NOW - timedelta(minutes=10),
        duration_minutes=90,
    )
    app.state.session_repository.save(sesion)
    return str(sesion.id)


class TestCrear:
    def test_crea_preguntas_y_las_numera(self, client: TestClient, app: Any) -> None:
        sid = sesion_abierta(app)

        respuesta = client.post(
            f"/api/v1/sessions/{sid}/questions",
            json={"questions": [UNA_PREGUNTA, {**UNA_PREGUNTA, "statement": "¿Y RQ?"}]},
        )

        assert respuesta.status_code == 201, respuesta.text
        cuerpo = respuesta.json()
        assert [p["position"] for p in cuerpo] == [1, 2]
        assert [o["position"] for o in cuerpo[0]["options"]] == [1, 2, 3]

    def test_400_si_ninguna_opcion_es_correcta(self, client: TestClient, app: Any) -> None:
        sid = sesion_abierta(app)
        mala = {**UNA_PREGUNTA, "options": [{"option_text": "A"}, {"option_text": "B"}]}

        respuesta = client.post(f"/api/v1/sessions/{sid}/questions", json={"questions": [mala]})

        assert respuesta.status_code == 400
        assert "correcta" in respuesta.json()["detail"]

    def test_no_guarda_nada_si_una_del_lote_es_invalida(self, client: TestClient, app: Any) -> None:
        # Si la segunda esta mal, el docente no se queda con una suelta.
        sid = sesion_abierta(app)
        mala = {**UNA_PREGUNTA, "statement": "   "}

        client.post(f"/api/v1/sessions/{sid}/questions", json={"questions": [UNA_PREGUNTA, mala]})

        assert client.get(f"/api/v1/sessions/{sid}/questions").json() == []

    def test_422_si_el_cuerpo_trae_una_clave_de_mas(self, client: TestClient, app: Any) -> None:
        sid = sesion_abierta(app)
        mala = {**UNA_PREGUNTA, "respuesta": "la primera"}

        respuesta = client.post(f"/api/v1/sessions/{sid}/questions", json={"questions": [mala]})

        assert respuesta.status_code == 422


class TestLaRespuestaNoLlegaAlEstudiante:
    """El punto que define SPEC-003."""

    def test_el_examen_no_trae_is_correct_en_ninguna_parte(
        self, client: TestClient, app: Any
    ) -> None:
        sid = sesion_abierta(app)
        client.post(f"/api/v1/sessions/{sid}/questions", json={"questions": [UNA_PREGUNTA]})
        matricular_verificado(app, sid)

        respuesta = client.get(f"/api/v1/exam/{sid}/questions")

        assert respuesta.status_code == 200
        # Se inspecciona el JSON crudo, no el objeto: lo que importa es lo que
        # viaja por el cable.
        crudo = respuesta.text
        assert "is_correct" not in crudo
        assert "correct_numeric_answer" not in crudo
        assert "correct_text_answer" not in crudo

    def test_el_examen_si_trae_las_opciones_para_poder_responder(
        self, client: TestClient, app: Any
    ) -> None:
        sid = sesion_abierta(app)
        client.post(f"/api/v1/sessions/{sid}/questions", json={"questions": [UNA_PREGUNTA]})
        matricular_verificado(app, sid)

        cuerpo = client.get(f"/api/v1/exam/{sid}/questions").json()

        assert len(cuerpo[0]["options"]) == 3
        assert cuerpo[0]["statement"] == UNA_PREGUNTA["statement"]

    def test_una_numerica_no_filtra_su_respuesta(self, client: TestClient, app: Any) -> None:
        sid = sesion_abierta(app)
        client.post(
            f"/api/v1/sessions/{sid}/questions",
            json={
                "questions": [
                    {
                        "question_type": "numeric",
                        "statement": "¿Cuántos monitores permite el preset estricto?",
                        "correct_numeric_answer": "1",
                    }
                ]
            },
        )

        matricular_verificado(app, sid)

        assert "correct" not in client.get(f"/api/v1/exam/{sid}/questions").text

    def test_el_docente_si_las_ve(self, client: TestClient, app: Any) -> None:
        sid = sesion_abierta(app)
        client.post(f"/api/v1/sessions/{sid}/questions", json={"questions": [UNA_PREGUNTA]})

        cuerpo = client.get(f"/api/v1/sessions/{sid}/questions").json()

        assert [o["is_correct"] for o in cuerpo[0]["options"]] == [True, False, False]

    def test_sin_matricula_no_hay_examen(self, client: TestClient, app: Any) -> None:
        # Conocer el session_id de un examen ajeno no da acceso a sus preguntas.
        sid = sesion_abierta(app)
        client.post(f"/api/v1/sessions/{sid}/questions", json={"questions": [UNA_PREGUNTA]})

        respuesta = client.get(f"/api/v1/exam/{sid}/questions")

        assert respuesta.status_code == 403
        assert "No estas matriculado" in respuesta.json()["detail"]


class TestVentanaDelExamen:
    def test_no_se_puede_descargar_antes_de_que_empiece(self, client: TestClient, app: Any) -> None:
        # Sin esto, el estudiante baja el examen la noche anterior.
        sesion = ExamSession.create(
            teacher_id=TEACHER_ID,
            title="Parcial de mañana",
            starts_at=NOW + timedelta(days=1),
            duration_minutes=90,
        )
        app.state.session_repository.save(sesion)

        respuesta = client.get(f"/api/v1/exam/{sesion.id}/questions")

        assert respuesta.status_code == 403
        assert "no esta abierto" in respuesta.json()["detail"]

    def test_tampoco_despues_de_que_termine(self, client: TestClient, app: Any) -> None:
        sesion = ExamSession.create(
            teacher_id=TEACHER_ID,
            title="Parcial de ayer",
            starts_at=NOW - timedelta(days=1),
            duration_minutes=90,
        )
        app.state.session_repository.save(sesion)

        assert client.get(f"/api/v1/exam/{sesion.id}/questions").status_code == 403

    def test_una_sesion_inexistente_responde_igual(self, client: TestClient) -> None:
        # Mismo 403 que una ajena: distinguirlos revelaria que sesiones existen.
        assert client.get(f"/api/v1/exam/{uuid4()}/questions").status_code == 403


class TestAutorizacion:
    def test_un_estudiante_no_ve_el_banco_con_respuestas(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sid = sesion_abierta(authed_app)
        authed_client.post(
            f"/api/v1/sessions/{sid}/questions",
            json={"questions": [UNA_PREGUNTA]},
            headers=bearer(TEACHER_TOKEN),
        )

        respuesta = authed_client.get(
            f"/api/v1/sessions/{sid}/questions", headers=bearer(STUDENT_TOKEN)
        )

        assert respuesta.status_code == 403
        assert "is_correct" not in respuesta.text

    def test_un_estudiante_no_puede_crear_preguntas(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sid = sesion_abierta(authed_app)

        respuesta = authed_client.post(
            f"/api/v1/sessions/{sid}/questions",
            json={"questions": [UNA_PREGUNTA]},
            headers=bearer(STUDENT_TOKEN),
        )

        assert respuesta.status_code == 403

    def test_un_docente_no_crea_preguntas_en_sesion_ajena(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        # IDOR: conocer el session_id de un colega no basta.
        ajena = sesion_abierta(authed_app, teacher_id=uuid4())

        respuesta = authed_client.post(
            f"/api/v1/sessions/{ajena}/questions",
            json={"questions": [UNA_PREGUNTA]},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 403

    def test_un_docente_no_lee_el_banco_de_sesion_ajena(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        ajena = sesion_abierta(authed_app, teacher_id=uuid4())

        assert (
            authed_client.get(
                f"/api/v1/sessions/{ajena}/questions", headers=bearer(TEACHER_TOKEN)
            ).status_code
            == 403
        )

    def test_401_sin_token(self, authed_client: TestClient, authed_app: Any) -> None:
        sid = sesion_abierta(authed_app)

        assert authed_client.get(f"/api/v1/exam/{sid}/questions").status_code == 401


def test_los_endpoints_estan_publicados(client: TestClient) -> None:
    rutas = json.loads(client.get("/openapi.json").text)["paths"]

    assert "/api/v1/sessions/{session_id}/questions" in rutas
    assert "/api/v1/exam/{session_id}/questions" in rutas
