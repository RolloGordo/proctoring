"""GET /api/v1/me/exams: el panel del estudiante."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.participant import SessionParticipant

from tests.conftest import (
    CONTRACT_STUDENT_ID,
    NOW,
    OTHER_STUDENT_ID,
    OTHER_STUDENT_TOKEN,
    STUDENT_TOKEN,
    TEACHER_ID,
    TEACHER_TOKEN,
)

pytestmark = pytest.mark.integration


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def matricular(app: Any, titulo: str, student_id: UUID, *, entregado: bool = False) -> str:
    sesion = ExamSession.create(
        teacher_id=TEACHER_ID,
        title=titulo,
        starts_at=NOW - timedelta(minutes=5),
        duration_minutes=60,
    )
    app.state.session_repository.save(sesion)
    participante = SessionParticipant.enroll(
        session_id=sesion.id, student_id=student_id, consented_at=NOW
    ).verified(NOW)
    if entregado:
        participante = participante.submitted(NOW)
    app.state.participant_repository.save(participante)
    return str(sesion.id)


def test_devuelve_mis_examenes(authed_client: TestClient, authed_app: Any) -> None:
    sid = matricular(authed_app, "Parcial", CONTRACT_STUDENT_ID)

    respuesta = authed_client.get("/api/v1/me/exams", headers=bearer(STUDENT_TOKEN))

    assert respuesta.status_code == 200, respuesta.text
    [examen] = respuesta.json()
    assert examen["session_id"] == sid
    assert examen["title"] == "Parcial"
    assert examen["can_enter_now"] is True
    assert examen["submitted_at"] is None


def test_la_nota_no_se_inventa(authed_client: TestClient, authed_app: Any) -> None:
    # Sin calificacion automatica todavia, la nota es nula. Un cero inventado
    # seria peor que decir que falta.
    matricular(authed_app, "Hecho", CONTRACT_STUDENT_ID, entregado=True)

    [examen] = authed_client.get("/api/v1/me/exams", headers=bearer(STUDENT_TOKEN)).json()

    assert examen["score"] is None
    assert examen["submitted_at"] is not None
    assert examen["can_enter_now"] is False


def test_no_filtra_los_examenes_de_otro_estudiante(
    authed_client: TestClient, authed_app: Any
) -> None:
    matricular(authed_app, "De otro", OTHER_STUDENT_ID)

    mios = authed_client.get("/api/v1/me/exams", headers=bearer(STUDENT_TOKEN)).json()
    suyos = authed_client.get("/api/v1/me/exams", headers=bearer(OTHER_STUDENT_TOKEN)).json()

    assert mios == []
    assert [e["title"] for e in suyos] == ["De otro"]


def test_la_respuesta_no_lleva_el_codigo_de_acceso(
    authed_client: TestClient, authed_app: Any
) -> None:
    matricular(authed_app, "Parcial", CONTRACT_STUDENT_ID)

    texto = authed_client.get("/api/v1/me/exams", headers=bearer(STUDENT_TOKEN)).text

    assert "access_code" not in texto


def test_trae_lo_que_la_sala_de_espera_necesita(authed_client: TestClient, authed_app: Any) -> None:
    # Desde el panel el estudiante vuelve a la sala sin haber tecleado el codigo,
    # asi que el listado tiene que traer que se supervisa y las indicaciones.
    matricular(authed_app, "Parcial", CONTRACT_STUDENT_ID)

    [examen] = authed_client.get("/api/v1/me/exams", headers=bearer(STUDENT_TOKEN)).json()

    assert examen["modules"]
    assert "entry_tolerance_minutes" in examen
    assert "description" in examen


def test_un_docente_recibe_403(authed_client: TestClient) -> None:
    respuesta = authed_client.get("/api/v1/me/exams", headers=bearer(TEACHER_TOKEN))

    assert respuesta.status_code == 403


def test_sin_token_recibe_401(authed_client: TestClient) -> None:
    assert authed_client.get("/api/v1/me/exams").status_code == 401
