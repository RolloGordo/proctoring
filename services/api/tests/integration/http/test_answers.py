"""Endpoints de respuestas, con el foco en que nadie responda un examen ajeno."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from proctoring_api.application.use_cases.manage_enrollment import DEFAULT_DEV_STUDENT_ID
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.participant import SessionParticipant

from tests.conftest import NOW, STUDENT_TOKEN, TEACHER_ID, TEACHER_TOKEN

pytestmark = pytest.mark.integration


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def examen_listo(app: Any, *, student_id: Any = None) -> tuple[str, dict[str, Any]]:
    """Sesión abierta + una pregunta + estudiante matriculado y verificado."""
    sesion = ExamSession.create(
        teacher_id=TEACHER_ID,
        title="Parcial",
        starts_at=NOW - timedelta(minutes=10),
        duration_minutes=90,
    )
    app.state.session_repository.save(sesion)
    sid = str(sesion.id)

    app.state.participant_repository.save(
        SessionParticipant.enroll(
            session_id=sesion.id,
            student_id=student_id or DEFAULT_DEV_STUDENT_ID,
            consented_at=NOW,
        ).verified(NOW)
    )

    pregunta = app.state.add_questions.execute(
        sesion.id,
        [
            _nueva_opcion_multiple(),
        ],
    )[0]
    return sid, {
        "id": str(pregunta.id),
        "options": [str(o.id) for o in pregunta.options],
    }


def _nueva_opcion_multiple() -> Any:
    from decimal import Decimal

    from proctoring_api.application.use_cases.manage_questions import NewQuestion
    from proctoring_api.domain.question import QuestionType

    return NewQuestion(
        question_type=QuestionType.MULTIPLE_CHOICE,
        statement="¿Qué hace RLS en PostgreSQL?",
        points=Decimal(2),
        options=[("Filtra filas por usuario", True), ("Comprime la base", False)],
    )


class TestGuardar:
    def test_guarda_y_devuelve_lo_guardado(self, client: TestClient, app: Any) -> None:
        sid, pregunta = examen_listo(app)

        respuesta = client.put(
            f"/api/v1/exam/{sid}/answers",
            json={
                "answers": [
                    {"question_id": pregunta["id"], "selected_option_id": pregunta["options"][0]}
                ]
            },
        )

        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo[0]["selected_option_id"] == pregunta["options"][0]

    def test_la_respuesta_guardada_no_dice_si_acerto(self, client: TestClient, app: Any) -> None:
        # Devolver `is_correct` al guardar le diría al estudiante si acertó
        # mientras rinde, que es justo lo que no puede saber.
        sid, pregunta = examen_listo(app)

        respuesta = client.put(
            f"/api/v1/exam/{sid}/answers",
            json={
                "answers": [
                    {"question_id": pregunta["id"], "selected_option_id": pregunta["options"][0]}
                ]
            },
        )

        texto = respuesta.text
        assert "is_correct" not in texto
        assert "points_awarded" not in texto

    def test_400_si_la_opcion_no_es_de_la_pregunta(self, client: TestClient, app: Any) -> None:
        sid, pregunta = examen_listo(app)

        respuesta = client.put(
            f"/api/v1/exam/{sid}/answers",
            json={"answers": [{"question_id": pregunta["id"], "selected_option_id": str(uuid4())}]},
        )

        assert respuesta.status_code == 400
        assert "pertenece" in respuesta.json()["detail"]

    def test_400_si_la_pregunta_es_de_otro_examen(self, client: TestClient, app: Any) -> None:
        sid, _ = examen_listo(app)

        respuesta = client.put(
            f"/api/v1/exam/{sid}/answers",
            json={"answers": [{"question_id": str(uuid4()), "selected_option_id": str(uuid4())}]},
        )

        assert respuesta.status_code == 400
        assert "no es de este examen" in respuesta.json()["detail"]

    def test_422_si_sobra_una_clave(self, client: TestClient, app: Any) -> None:
        sid, pregunta = examen_listo(app)

        respuesta = client.put(
            f"/api/v1/exam/{sid}/answers",
            json={"answers": [{"question_id": pregunta["id"], "is_correct": True}]},
        )

        assert respuesta.status_code == 422

    def test_responder_otra_vez_reemplaza(self, client: TestClient, app: Any) -> None:
        sid, pregunta = examen_listo(app)
        url = f"/api/v1/exam/{sid}/answers"

        client.put(
            url,
            json={
                "answers": [
                    {"question_id": pregunta["id"], "selected_option_id": pregunta["options"][0]}
                ]
            },
        )
        client.put(
            url,
            json={
                "answers": [
                    {"question_id": pregunta["id"], "selected_option_id": pregunta["options"][1]}
                ]
            },
        )

        mias = client.get(url).json()
        assert len(mias) == 1
        assert mias[0]["selected_option_id"] == pregunta["options"][1]


class TestRetomar:
    def test_devuelve_lo_ya_respondido(self, client: TestClient, app: Any) -> None:
        # Si el equipo se reinicia a mitad del examen, lo respondido sigue ahí.
        sid, pregunta = examen_listo(app)
        client.put(
            f"/api/v1/exam/{sid}/answers",
            json={
                "answers": [
                    {"question_id": pregunta["id"], "selected_option_id": pregunta["options"][0]}
                ]
            },
        )

        respuesta = client.get(f"/api/v1/exam/{sid}/answers")

        assert respuesta.status_code == 200
        assert [r["question_id"] for r in respuesta.json()] == [pregunta["id"]]

    def test_sin_matricula_responde_403(self, client: TestClient, app: Any) -> None:
        sesion = ExamSession.create(
            teacher_id=TEACHER_ID,
            title="Ajeno",
            starts_at=NOW - timedelta(minutes=5),
            duration_minutes=60,
        )
        app.state.session_repository.save(sesion)

        respuesta = client.get(f"/api/v1/exam/{sesion.id}/answers")

        assert respuesta.status_code == 403


class TestAutorizacion:
    def test_un_docente_no_responde(self, authed_client: TestClient, authed_app: Any) -> None:
        sid, pregunta = examen_listo(authed_app)

        respuesta = authed_client.put(
            f"/api/v1/exam/{sid}/answers",
            json={
                "answers": [
                    {"question_id": pregunta["id"], "selected_option_id": pregunta["options"][0]}
                ]
            },
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 403

    def test_un_estudiante_no_matriculado_no_responde(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        # El agujero que cerró SPEC-004, ahora también al escribir: conocer el
        # session_id no alcanza para dejar rastro en un examen ajeno.
        sid, pregunta = examen_listo(authed_app, student_id=UUID(int=9))

        respuesta = authed_client.put(
            f"/api/v1/exam/{sid}/answers",
            json={
                "answers": [
                    {"question_id": pregunta["id"], "selected_option_id": pregunta["options"][0]}
                ]
            },
            headers=bearer(STUDENT_TOKEN),
        )

        assert respuesta.status_code == 403
        assert "matriculado" in respuesta.json()["detail"]

    def test_sin_token_responde_401(self, authed_client: TestClient, authed_app: Any) -> None:
        sid, _ = examen_listo(authed_app)

        assert authed_client.get(f"/api/v1/exam/{sid}/answers").status_code == 401
        assert (
            authed_client.put(
                f"/api/v1/exam/{sid}/answers",
                json={"answers": [{"question_id": str(uuid4())}]},
            ).status_code
            == 401
        )


class TestVariasRespuestasCorrectas:
    """`multiple_select` de punta a punta por HTTP.

    El dominio ya prueba como se califica; lo que falta cubrir es que el campo
    sobreviva el viaje entero —esquema, caso de uso, repositorio y respuesta—,
    que es donde un campo nuevo se pierde sin que nada se ponga rojo.
    """

    def examen(self, app: Any) -> tuple[str, dict[str, Any]]:
        from decimal import Decimal

        from proctoring_api.application.use_cases.manage_questions import NewQuestion
        from proctoring_api.domain.question import QuestionType

        sesion = ExamSession.create(
            teacher_id=TEACHER_ID,
            title="Parcial",
            starts_at=NOW - timedelta(minutes=10),
            duration_minutes=90,
        )
        app.state.session_repository.save(sesion)
        app.state.participant_repository.save(
            SessionParticipant.enroll(
                session_id=sesion.id,
                student_id=DEFAULT_DEV_STUDENT_ID,
                consented_at=NOW,
            ).verified(NOW)
        )
        pregunta = app.state.add_questions.execute(
            sesion.id,
            [
                NewQuestion(
                    question_type=QuestionType.MULTIPLE_SELECT,
                    statement="¿Cuales de estas las garantiza RLS?",
                    points=Decimal(2),
                    options=[
                        ("Filtrar filas por usuario", True),
                        ("Aplicarse tambien a la API", True),
                        ("Cifrar el disco", False),
                    ],
                )
            ],
        )[0]
        return str(sesion.id), {
            "id": str(pregunta.id),
            "options": [str(o.id) for o in pregunta.options],
        }

    def test_se_guardan_y_se_devuelven_varias_opciones(self, client: TestClient, app: Any) -> None:
        sid, pregunta = self.examen(app)

        respuesta = client.put(
            f"/api/v1/exam/{sid}/answers",
            json={
                "answers": [
                    {
                        "question_id": pregunta["id"],
                        "selected_option_ids": pregunta["options"][:2],
                    }
                ]
            },
        )

        assert respuesta.status_code == 200, respuesta.text
        guardada = respuesta.json()[0]
        assert guardada["selected_option_ids"] == pregunta["options"][:2]
        assert guardada["selected_option_id"] is None

    def test_no_se_cuela_la_opcion_de_otra_pregunta(self, client: TestClient, app: Any) -> None:
        # La columna es un `uuid[]`, que no puede tener clave ajena: esta
        # comprobacion es lo unico que lo impide.
        sid, pregunta = self.examen(app)

        respuesta = client.put(
            f"/api/v1/exam/{sid}/answers",
            json={
                "answers": [{"question_id": pregunta["id"], "selected_option_ids": [str(uuid4())]}]
            },
        )

        assert respuesta.status_code == 400

    def test_no_admite_las_dos_formas_a_la_vez(self, client: TestClient, app: Any) -> None:
        # Con las dos puestas no se sabria cual califica.
        sid, pregunta = self.examen(app)

        respuesta = client.put(
            f"/api/v1/exam/{sid}/answers",
            json={
                "answers": [
                    {
                        "question_id": pregunta["id"],
                        "selected_option_id": pregunta["options"][0],
                        "selected_option_ids": [pregunta["options"][1]],
                    }
                ]
            },
        )

        assert respuesta.status_code == 400

    def test_el_examen_no_revela_cuales_son_las_correctas(
        self, client: TestClient, app: Any
    ) -> None:
        sid, _ = self.examen(app)

        crudo = json.dumps(client.get(f"/api/v1/exam/{sid}/questions").json())

        assert "is_correct" not in crudo
