"""Sin navegacion hacia atras, una respuesta enviada ya no se cambia.

Se prueba contra la API y no contra la pantalla: esconder el boton "Anterior"
no impide repetir la peticion, y lo que decide la nota es lo que la API acepta.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from proctoring_api.domain.participant import SessionParticipant

from tests.conftest import CONTRACT_STUDENT_ID, NOW, STUDENT_TOKEN, TEACHER_TOKEN

pytestmark = pytest.mark.integration


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def pregunta(numero: int) -> dict[str, Any]:
    return {
        "question_type": "multiple_choice",
        "statement": f"Pregunta numero {numero}",
        "points": "1",
        "options": [
            {"option_text": "Correcta", "is_correct": True},
            {"option_text": "Incorrecta", "is_correct": False},
        ],
    }


def examen(app: FastAPI, *, volver_atras: bool) -> tuple[str, list[dict[str, Any]]]:
    """Un examen en curso, con dos preguntas y el estudiante dentro."""
    with TestClient(app) as client:
        creado = client.post(
            "/api/v1/sessions",
            json={
                "title": "Examen de una sola pasada",
                "starts_at": NOW.isoformat(),
                "duration_minutes": 60,
                "allow_back_navigation": volver_atras,
            },
            headers=bearer(TEACHER_TOKEN),
        )
        assert creado.status_code == 201, creado.text
        session_id: str = creado.json()["id"]

        puestas = client.post(
            f"/api/v1/sessions/{session_id}/questions",
            json={"questions": [pregunta(1), pregunta(2)]},
            headers=bearer(TEACHER_TOKEN),
        )
        assert puestas.status_code == 201, puestas.text

    app.state.participant_repository.save(
        SessionParticipant.enroll(
            session_id=UUID(session_id), student_id=CONTRACT_STUDENT_ID, consented_at=NOW
        ).verified(NOW)
    )

    with TestClient(app) as client:
        suyas = client.get(f"/api/v1/exam/{session_id}/questions", headers=bearer(STUDENT_TOKEN))
    assert suyas.status_code == 200, suyas.text
    preguntas: list[dict[str, Any]] = suyas.json()
    return session_id, preguntas


def responder(client: TestClient, session_id: str, pregunta_: dict[str, Any], opcion: int) -> Any:
    return client.put(
        f"/api/v1/exam/{session_id}/answers",
        json={
            "answers": [
                {
                    "question_id": pregunta_["id"],
                    "selected_option_id": pregunta_["options"][opcion]["id"],
                }
            ]
        },
        headers=bearer(STUDENT_TOKEN),
    )


class TestSinVolverAtras:
    def test_la_primera_respuesta_entra(self, authed_app: FastAPI) -> None:
        session_id, preguntas = examen(authed_app, volver_atras=False)

        with TestClient(authed_app) as client:
            assert responder(client, session_id, preguntas[0], 0).status_code == 200

    def test_cambiarla_se_rechaza(self, authed_app: FastAPI) -> None:
        session_id, preguntas = examen(authed_app, volver_atras=False)

        with TestClient(authed_app) as client:
            assert responder(client, session_id, preguntas[0], 0).status_code == 200
            segunda = responder(client, session_id, preguntas[0], 1)

        assert segunda.status_code == 400
        assert "no permite volver atras" in segunda.json()["detail"]

    def test_repetir_la_misma_respuesta_tambien_se_rechaza(self, authed_app: FastAPI) -> None:
        """No se mira si cambio: se mira si ya estaba. Aceptar la repetida
        obligaria a comparar respuestas, y "igual" no significa lo mismo para
        una opcion que para un texto o un numero con tolerancia."""
        session_id, preguntas = examen(authed_app, volver_atras=False)

        with TestClient(authed_app) as client:
            assert responder(client, session_id, preguntas[0], 0).status_code == 200
            otra_vez = responder(client, session_id, preguntas[0], 0)

        assert otra_vez.status_code == 400

    def test_la_otra_pregunta_sigue_abierta(self, authed_app: FastAPI) -> None:
        """Se bloquea la pregunta respondida, no el examen."""
        session_id, preguntas = examen(authed_app, volver_atras=False)

        with TestClient(authed_app) as client:
            assert responder(client, session_id, preguntas[0], 0).status_code == 200
            assert responder(client, session_id, preguntas[1], 0).status_code == 200

    def test_un_lote_con_una_ya_respondida_no_guarda_nada(self, authed_app: FastAPI) -> None:
        """La pantalla guarda de a una, pero al retomar manda un lote. Si se
        guardara la mitad, el estudiante veria un error con parte de lo suyo
        dentro y parte fuera."""
        session_id, preguntas = examen(authed_app, volver_atras=False)

        with TestClient(authed_app) as client:
            assert responder(client, session_id, preguntas[0], 0).status_code == 200
            lote = client.put(
                f"/api/v1/exam/{session_id}/answers",
                json={
                    "answers": [
                        {
                            "question_id": preguntas[1]["id"],
                            "selected_option_id": preguntas[1]["options"][0]["id"],
                        },
                        {
                            "question_id": preguntas[0]["id"],
                            "selected_option_id": preguntas[0]["options"][1]["id"],
                        },
                    ]
                },
                headers=bearer(STUDENT_TOKEN),
            )
            assert lote.status_code == 400, lote.text

            guardadas = client.get(
                f"/api/v1/exam/{session_id}/answers", headers=bearer(STUDENT_TOKEN)
            ).json()

        # Solo la primera, la del principio: la segunda pregunta no se guardo.
        assert [a["question_id"] for a in guardadas] == [preguntas[0]["id"]]


class TestConVolverAtras:
    def test_se_puede_corregir_cuantas_veces_haga_falta(self, authed_app: FastAPI) -> None:
        """Es el comportamiento por defecto y el de los examenes ya creados:
        guardar es continuo y la ultima respuesta gana."""
        session_id, preguntas = examen(authed_app, volver_atras=True)

        with TestClient(authed_app) as client:
            assert responder(client, session_id, preguntas[0], 0).status_code == 200
            assert responder(client, session_id, preguntas[0], 1).status_code == 200
            assert responder(client, session_id, preguntas[0], 0).status_code == 200

            guardadas = client.get(
                f"/api/v1/exam/{session_id}/answers", headers=bearer(STUDENT_TOKEN)
            ).json()

        assert len(guardadas) == 1
        assert guardadas[0]["selected_option_id"] == preguntas[0]["options"][0]["id"]
