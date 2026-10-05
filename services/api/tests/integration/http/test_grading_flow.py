"""Entregar un examen y ver la nota en el panel: el recorrido completo."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from proctoring_api.application.use_cases.manage_enrollment import DEFAULT_DEV_STUDENT_ID
from proctoring_api.application.use_cases.manage_questions import NewQuestion
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.participant import SessionParticipant
from proctoring_api.domain.question import QuestionType

from tests.conftest import NOW, TEACHER_ID

pytestmark = pytest.mark.integration


def examen_con_tres_preguntas(app: Any) -> tuple[str, list[Any]]:
    sesion = ExamSession.create(
        teacher_id=TEACHER_ID,
        title="Parcial",
        starts_at=NOW - timedelta(minutes=5),
        duration_minutes=60,
    )
    app.state.session_repository.save(sesion)
    app.state.participant_repository.save(
        SessionParticipant.enroll(
            session_id=sesion.id, student_id=DEFAULT_DEV_STUDENT_ID, consented_at=NOW
        ).verified(NOW)
    )
    preguntas = app.state.add_questions.execute(
        sesion.id,
        [
            NewQuestion(
                question_type=QuestionType.MULTIPLE_CHOICE,
                statement="Opcion multiple",
                points=Decimal(2),
                options=[("Correcta", True), ("Incorrecta", False)],
            ),
            NewQuestion(
                question_type=QuestionType.NUMERIC,
                statement="Numerica",
                points=Decimal(3),
                correct_numeric_answer=Decimal(10),
            ),
            NewQuestion(
                question_type=QuestionType.ESSAY, statement="Desarrollo", points=Decimal(5)
            ),
        ],
    )
    return str(sesion.id), list(preguntas)


def responder(client: TestClient, sid: str, preguntas: list[Any], *, acertar: bool) -> None:
    opcion = preguntas[0].options[0 if acertar else 1].id
    cuerpo = {
        "answers": [
            {"question_id": str(preguntas[0].id), "selected_option_id": str(opcion)},
            {"question_id": str(preguntas[1].id), "numeric_answer": "10" if acertar else "99"},
            {"question_id": str(preguntas[2].id), "text_answer": "Mi desarrollo"},
        ]
    }
    assert client.put(f"/api/v1/exam/{sid}/answers", json=cuerpo).status_code == 200


def test_al_entregar_se_califica_lo_que_se_corrige_solo(client: TestClient, app: Any) -> None:
    sid, preguntas = examen_con_tres_preguntas(app)
    responder(client, sid, preguntas, acertar=True)

    entrega = client.post(f"/api/v1/exam/{sid}/submit")

    assert entrega.status_code == 200, entrega.text
    # 2 + 3 ganados; el desarrollo de 5 espera al docente.
    assert entrega.json()["score"] == 5.0


def test_quien_falla_todo_gana_cero_no_nulo(client: TestClient, app: Any) -> None:
    sid, preguntas = examen_con_tres_preguntas(app)
    responder(client, sid, preguntas, acertar=False)

    entrega = client.post(f"/api/v1/exam/{sid}/submit")

    # Cero es una nota; "sin nota" es otra cosa.
    assert entrega.json()["score"] == 0.0


def test_el_panel_muestra_la_nota_el_maximo_y_que_falta_un_desarrollo(
    client: TestClient, app: Any
) -> None:
    sid, preguntas = examen_con_tres_preguntas(app)
    responder(client, sid, preguntas, acertar=True)
    client.post(f"/api/v1/exam/{sid}/submit")

    [examen] = client.get("/api/v1/me/exams").json()

    assert examen["score"] == 5.0
    assert examen["max_score"] == 10.0
    assert examen["pending_manual_review"] is True


def test_la_correccion_queda_en_cada_respuesta(client: TestClient, app: Any) -> None:
    sid, preguntas = examen_con_tres_preguntas(app)
    responder(client, sid, preguntas, acertar=True)
    client.post(f"/api/v1/exam/{sid}/submit")

    participante = app.state.participant_repository.find(
        preguntas[0].session_id, DEFAULT_DEV_STUDENT_ID
    )
    guardadas = {
        a.question_id: a for a in app.state.answer_repository.list_by_participant(participante.id)
    }

    assert guardadas[preguntas[0].id].is_correct is True
    assert guardadas[preguntas[0].id].points_awarded == Decimal(2)
    # El desarrollo queda sin corregir: ni acierto ni error, sin puntos.
    assert guardadas[preguntas[2].id].is_correct is None
    assert guardadas[preguntas[2].id].points_awarded is None


def test_el_estudiante_no_ve_el_acierto_hasta_entregar(client: TestClient, app: Any) -> None:
    # Mientras rinde, guardar una respuesta no revela si acerto.
    sid, preguntas = examen_con_tres_preguntas(app)

    respuesta = client.put(
        f"/api/v1/exam/{sid}/answers",
        json={
            "answers": [
                {
                    "question_id": str(preguntas[0].id),
                    "selected_option_id": str(preguntas[0].options[0].id),
                }
            ]
        },
    )

    assert "is_correct" not in respuesta.text
    assert "score" not in respuesta.text
