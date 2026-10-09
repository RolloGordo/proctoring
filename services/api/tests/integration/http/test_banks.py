"""Bancos de preguntas: aislamiento entre docentes y sorteo determinista.

Dos cosas se prueban aquí y no en las unitarias, porque solo aparecen al pasar
por HTTP: que un docente no alcance el banco de otro por ningún camino, y que un
estudiante que recarga la página a mitad del examen reciba **las mismas**
preguntas.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.participant import SessionParticipant

from tests.conftest import (
    CONTRACT_STUDENT_ID,
    NOW,
    OTHER_TEACHER_TOKEN,
    STUDENT_TOKEN,
    TEACHER_ID,
    TEACHER_TOKEN,
)

pytestmark = pytest.mark.integration


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def pregunta(numero: int) -> dict[str, Any]:
    """Una pregunta válida, distinguible por su enunciado."""
    return {
        "question_type": "multiple_choice",
        "statement": f"Pregunta numero {numero}",
        "points": "1",
        "options": [
            {"option_text": "Correcta", "is_correct": True},
            {"option_text": "Incorrecta", "is_correct": False},
        ],
    }


def crear_banco(client: TestClient, token: str, nombre: str = "Banco de SQL") -> str:
    respuesta = client.post("/api/v1/question-banks", json={"name": nombre}, headers=bearer(token))
    assert respuesta.status_code == 201, respuesta.text
    bank_id: str = respuesta.json()["id"]
    return bank_id


def llenar(client: TestClient, bank_id: str, token: str, cuantas: int) -> None:
    respuesta = client.post(
        f"/api/v1/question-banks/{bank_id}/questions",
        json={"questions": [pregunta(n) for n in range(1, cuantas + 1)]},
        headers=bearer(token),
    )
    assert respuesta.status_code == 201, respuesta.text


def crear_examen(client: TestClient, *, pool_size: int | None = None) -> str:
    cuerpo: dict[str, Any] = {
        "title": "Examen con banco",
        "starts_at": NOW.isoformat(),
        "duration_minutes": 60,
    }
    if pool_size is not None:
        cuerpo["question_pool_size"] = pool_size
    respuesta = client.post("/api/v1/sessions", json=cuerpo, headers=bearer(TEACHER_TOKEN))
    assert respuesta.status_code == 201, respuesta.text
    session_id: str = respuesta.json()["id"]
    return session_id


# ---------------------------------------------------------------------------
# Crear y listar
# ---------------------------------------------------------------------------


def test_el_docente_crea_un_banco_y_lo_ve_en_su_lista(authed_client: TestClient) -> None:
    bank_id = crear_banco(authed_client, TEACHER_TOKEN)

    lista = authed_client.get("/api/v1/question-banks", headers=bearer(TEACHER_TOKEN))

    assert lista.status_code == 200
    assert [b["id"] for b in lista.json()] == [bank_id]
    assert lista.json()[0]["question_count"] == 0


def test_la_lista_cuenta_las_preguntas_de_cada_banco(authed_client: TestClient) -> None:
    bank_id = crear_banco(authed_client, TEACHER_TOKEN)
    llenar(authed_client, bank_id, TEACHER_TOKEN, 7)

    lista = authed_client.get("/api/v1/question-banks", headers=bearer(TEACHER_TOKEN))

    assert lista.json()[0]["question_count"] == 7


def test_un_estudiante_no_crea_bancos(authed_client: TestClient) -> None:
    respuesta = authed_client.post(
        "/api/v1/question-banks", json={"name": "Mio"}, headers=bearer(STUDENT_TOKEN)
    )
    assert respuesta.status_code == 403


def test_sin_token_no_se_llega_a_los_bancos(authed_client: TestClient) -> None:
    assert authed_client.get("/api/v1/question-banks").status_code == 401


# ---------------------------------------------------------------------------
# Aislamiento entre docentes
# ---------------------------------------------------------------------------


def test_cada_docente_ve_solo_sus_bancos(authed_client: TestClient) -> None:
    """La lista sale del token: no hay parámetro con el que pedir los de otro."""
    mio = crear_banco(authed_client, TEACHER_TOKEN, "Mio")
    ajeno = crear_banco(authed_client, OTHER_TEACHER_TOKEN, "Ajeno")

    lista = authed_client.get("/api/v1/question-banks", headers=bearer(TEACHER_TOKEN))

    ids = [b["id"] for b in lista.json()]
    assert ids == [mio]
    assert ajeno not in ids


def test_un_banco_ajeno_y_uno_inexistente_responden_igual(authed_client: TestClient) -> None:
    """Si el ajeno diera 403 y el inexistente 404, probando ids se sabría cuáles existen."""
    ajeno = crear_banco(authed_client, OTHER_TEACHER_TOKEN, "Ajeno")
    inexistente = uuid4()

    primera = authed_client.get(
        f"/api/v1/question-banks/{ajeno}/questions", headers=bearer(TEACHER_TOKEN)
    )
    segunda = authed_client.get(
        f"/api/v1/question-banks/{inexistente}/questions", headers=bearer(TEACHER_TOKEN)
    )

    assert primera.status_code == segunda.status_code == 403
    assert primera.json() == segunda.json()


def test_no_se_anaden_preguntas_a_un_banco_ajeno(authed_client: TestClient) -> None:
    ajeno = crear_banco(authed_client, OTHER_TEACHER_TOKEN, "Ajeno")

    respuesta = authed_client.post(
        f"/api/v1/question-banks/{ajeno}/questions",
        json={"questions": [pregunta(1)]},
        headers=bearer(TEACHER_TOKEN),
    )

    assert respuesta.status_code == 403


def test_atar_el_banco_de_otro_no_sirve_para_leerlo(authed_client: TestClient) -> None:
    """La puerta de atrás: atar el banco ajeno al examen propio y pedir las
    preguntas. Se exige ser dueño **del examen y del banco**.
    """
    ajeno = crear_banco(authed_client, OTHER_TEACHER_TOKEN, "Ajeno")
    llenar(authed_client, ajeno, OTHER_TEACHER_TOKEN, 3)
    mio = crear_examen(authed_client)

    respuesta = authed_client.post(
        f"/api/v1/sessions/{mio}/banks",
        json={"bank_id": ajeno},
        headers=bearer(TEACHER_TOKEN),
    )

    assert respuesta.status_code == 403


def test_no_se_ata_un_banco_propio_a_un_examen_ajeno(authed_app: FastAPI) -> None:
    ajeno = ExamSession.create(
        teacher_id=uuid4(),
        title="Examen de otro",
        starts_at=NOW,
        duration_minutes=60,
    )
    authed_app.state.session_repository.save(ajeno)

    with TestClient(authed_app) as client:
        mio = crear_banco(client, TEACHER_TOKEN)
        respuesta = client.post(
            f"/api/v1/sessions/{ajeno.id}/banks",
            json={"bank_id": mio},
            headers=bearer(TEACHER_TOKEN),
        )

    assert respuesta.status_code == 403


# ---------------------------------------------------------------------------
# Atar y desatar
# ---------------------------------------------------------------------------


def test_atar_dos_veces_no_es_un_error(authed_client: TestClient) -> None:
    bank_id = crear_banco(authed_client, TEACHER_TOKEN)
    session_id = crear_examen(authed_client)
    url = f"/api/v1/sessions/{session_id}/banks"

    primera = authed_client.post(url, json={"bank_id": bank_id}, headers=bearer(TEACHER_TOKEN))
    segunda = authed_client.post(url, json={"bank_id": bank_id}, headers=bearer(TEACHER_TOKEN))

    assert primera.json() == {"bank_id": bank_id, "already_attached": False}
    assert segunda.json() == {"bank_id": bank_id, "already_attached": True}

    atados = authed_client.get(url, headers=bearer(TEACHER_TOKEN))
    assert [b["id"] for b in atados.json()] == [bank_id]


def test_desatar_deja_las_preguntas_del_banco(authed_client: TestClient) -> None:
    """Quitar el banco del examen no puede borrar el trabajo de años."""
    bank_id = crear_banco(authed_client, TEACHER_TOKEN)
    llenar(authed_client, bank_id, TEACHER_TOKEN, 4)
    session_id = crear_examen(authed_client)
    authed_client.post(
        f"/api/v1/sessions/{session_id}/banks",
        json={"bank_id": bank_id},
        headers=bearer(TEACHER_TOKEN),
    )

    quitar = authed_client.delete(
        f"/api/v1/sessions/{session_id}/banks/{bank_id}", headers=bearer(TEACHER_TOKEN)
    )

    assert quitar.status_code == 204
    atados = authed_client.get(
        f"/api/v1/sessions/{session_id}/banks", headers=bearer(TEACHER_TOKEN)
    )
    assert atados.json() == []
    quedan = authed_client.get(
        f"/api/v1/question-banks/{bank_id}/questions", headers=bearer(TEACHER_TOKEN)
    )
    assert len(quedan.json()) == 4


# ---------------------------------------------------------------------------
# El estudiante recibe el sorteo
# ---------------------------------------------------------------------------


def matricular(app: FastAPI, session_id: str) -> None:
    participante = SessionParticipant.enroll(
        session_id=UUID(session_id),
        student_id=CONTRACT_STUDENT_ID,
        consented_at=NOW,
    ).verified(NOW)
    app.state.participant_repository.save(participante)


def examen_con_banco(app: FastAPI, *, cuantas: int, pool_size: int | None) -> str:
    """Un examen en curso que extrae de un banco lleno, con el alumno dentro."""
    with TestClient(app) as client:
        bank_id = crear_banco(client, TEACHER_TOKEN)
        llenar(client, bank_id, TEACHER_TOKEN, cuantas)
        session_id = crear_examen(client, pool_size=pool_size)
        atado = client.post(
            f"/api/v1/sessions/{session_id}/banks",
            json={"bank_id": bank_id},
            headers=bearer(TEACHER_TOKEN),
        )
        assert atado.status_code == 200, atado.text
    matricular(app, session_id)
    return session_id


def preguntas_del_estudiante(app: FastAPI, session_id: str) -> list[str]:
    with TestClient(app) as client:
        respuesta = client.get(
            f"/api/v1/exam/{session_id}/questions", headers=bearer(STUDENT_TOKEN)
        )
    assert respuesta.status_code == 200, respuesta.text
    return [q["statement"] for q in respuesta.json()]


def test_el_estudiante_recibe_el_subconjunto_sorteado(authed_app: FastAPI) -> None:
    session_id = examen_con_banco(authed_app, cuantas=20, pool_size=5)

    recibidas = preguntas_del_estudiante(authed_app, session_id)

    assert len(recibidas) == 5
    assert len(set(recibidas)) == 5


def test_recargar_devuelve_exactamente_las_mismas_preguntas(authed_app: FastAPI) -> None:
    """Si el sorteo no fuera determinista, recargar a mitad del examen traería
    preguntas nuevas y el estudiante perdería lo respondido.
    """
    session_id = examen_con_banco(authed_app, cuantas=20, pool_size=5)

    primera = preguntas_del_estudiante(authed_app, session_id)
    segunda = preguntas_del_estudiante(authed_app, session_id)
    tercera = preguntas_del_estudiante(authed_app, session_id)

    assert primera == segunda == tercera


def test_sin_pool_size_llegan_todas_las_del_banco(authed_app: FastAPI) -> None:
    session_id = examen_con_banco(authed_app, cuantas=6, pool_size=None)

    recibidas = preguntas_del_estudiante(authed_app, session_id)

    assert len(recibidas) == 6


def test_las_preguntas_del_banco_llegan_sin_la_respuesta_correcta(authed_app: FastAPI) -> None:
    """La regla de siempre, ahora por el camino del banco."""
    session_id = examen_con_banco(authed_app, cuantas=3, pool_size=None)

    with TestClient(authed_app) as client:
        respuesta = client.get(
            f"/api/v1/exam/{session_id}/questions", headers=bearer(STUDENT_TOKEN)
        )

    assert "is_correct" not in respuesta.text
    assert "correct_text_answer" not in respuesta.text
    for pregunta_recibida in respuesta.json():
        for opcion in pregunta_recibida["options"]:
            assert set(opcion) == {"id", "option_text", "position"}


def test_un_examen_sin_bancos_sigue_usando_sus_propias_preguntas(authed_app: FastAPI) -> None:
    """Los exámenes ya creados no cambian de comportamiento."""
    with TestClient(authed_app) as client:
        session_id = crear_examen(client)
        creadas = client.post(
            f"/api/v1/sessions/{session_id}/questions",
            json={"questions": [pregunta(1), pregunta(2)]},
            headers=bearer(TEACHER_TOKEN),
        )
        assert creadas.status_code == 201, creadas.text
    matricular(authed_app, session_id)

    recibidas = preguntas_del_estudiante(authed_app, session_id)

    assert recibidas == ["Pregunta numero 1", "Pregunta numero 2"]


def test_el_estudiante_no_llega_a_los_bancos_del_examen(authed_app: FastAPI) -> None:
    """Ver de qué bancos extrae el examen revelaría su tamaño real."""
    session_id = examen_con_banco(authed_app, cuantas=10, pool_size=3)

    with TestClient(authed_app) as client:
        respuesta = client.get(
            f"/api/v1/sessions/{session_id}/banks", headers=bearer(STUDENT_TOKEN)
        )

    assert respuesta.status_code == 403


def test_fuera_de_la_ventana_no_se_sortea_nada(authed_app: FastAPI) -> None:
    """La ventana se comprueba antes del sorteo: si no, bastaría pedirlo la noche
    anterior para saber qué preguntas tocan.
    """
    session_id = examen_con_banco(authed_app, cuantas=10, pool_size=3)
    sesion = authed_app.state.session_repository.find_by_id(UUID(session_id))
    assert sesion is not None
    authed_app.state.session_repository.save(
        ExamSession.create(
            teacher_id=TEACHER_ID,
            title=sesion.title,
            starts_at=NOW + timedelta(days=1),
            duration_minutes=60,
            session_id=sesion.id,
        )
    )

    with TestClient(authed_app) as client:
        respuesta = client.get(
            f"/api/v1/exam/{session_id}/questions", headers=bearer(STUDENT_TOKEN)
        )

    assert respuesta.status_code == 403
    assert "no esta abierto" in respuesta.json()["detail"]


def test_el_estudiante_puede_responder_una_pregunta_del_banco(authed_app: FastAPI) -> None:
    """Un examen con banco tiene que poder **responderse**.

    Las preguntas de un banco no son del examen: tienen `session_id` nulo y
    cuelgan del banco. Si al guardar se valida contra las preguntas del examen
    en vez de contra las que el estudiante recibio, un examen con banco se
    muestra entero y no acepta ni una respuesta.
    """
    session_id = examen_con_banco(authed_app, cuantas=20, pool_size=5)

    with TestClient(authed_app) as client:
        recibidas = client.get(
            f"/api/v1/exam/{session_id}/questions", headers=bearer(STUDENT_TOKEN)
        ).json()
        primera = recibidas[0]
        guardado = client.put(
            f"/api/v1/exam/{session_id}/answers",
            json={
                "answers": [
                    {
                        "question_id": primera["id"],
                        "selected_option_id": primera["options"][0]["id"],
                    }
                ]
            },
            headers=bearer(STUDENT_TOKEN),
        )

    assert guardado.status_code == 200, guardado.text


def test_una_pregunta_del_banco_que_no_le_salio_no_se_le_acepta(authed_app: FastAPI) -> None:
    """El sorteo tambien acota lo que se puede responder.

    Si se aceptara cualquier pregunta del banco, un estudiante podria responder
    las veinte y llevarse puntos por preguntas que su examen nunca le mostro.
    """
    session_id = examen_con_banco(authed_app, cuantas=20, pool_size=5)

    with TestClient(authed_app) as client:
        suyas = {
            q["id"]
            for q in client.get(
                f"/api/v1/exam/{session_id}/questions", headers=bearer(STUDENT_TOKEN)
            ).json()
        }
        # Del banco, pero fuera de su sorteo: se saca de la lista del docente.
        todas = client.get(
            f"/api/v1/question-banks/{_banco_del_examen(client, session_id)}/questions",
            headers=bearer(TEACHER_TOKEN),
        ).json()
        ajena = next(q for q in todas if q["id"] not in suyas)

        guardado = client.put(
            f"/api/v1/exam/{session_id}/answers",
            json={
                "answers": [
                    {"question_id": ajena["id"], "selected_option_id": ajena["options"][0]["id"]}
                ]
            },
            headers=bearer(STUDENT_TOKEN),
        )

    assert guardado.status_code == 400, guardado.text
    assert "no es de este examen" in guardado.json()["detail"]


def _banco_del_examen(client: TestClient, session_id: str) -> str:
    atados = client.get(f"/api/v1/sessions/{session_id}/banks", headers=bearer(TEACHER_TOKEN))
    assert atados.status_code == 200, atados.text
    bank_id: str = atados.json()[0]["id"]
    return bank_id
