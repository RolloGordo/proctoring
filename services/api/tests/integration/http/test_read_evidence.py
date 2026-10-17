"""Ver una evidencia guardada, y no la de otro.

Los tres buckets son privados, así que hasta ahora una captura se subía y nadie
podía mirarla. Lo que de verdad se prueba aquí es lo contrario: que pedir la URL
de un archivo ajeno no funcione aunque quien pida sea un docente con un examen
propio.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from proctoring_api.domain.participant import SessionParticipant

from tests.conftest import (
    CONTRACT_SESSION_ID,
    CONTRACT_STUDENT_ID,
    NOW,
    OTHER_STUDENT_ID,
    OTHER_TEACHER_TOKEN,
    STUDENT_TOKEN,
    TEACHER_TOKEN,
)

pytestmark = pytest.mark.integration

RUTA = f"{CONTRACT_SESSION_ID}/{CONTRACT_STUDENT_ID}/{uuid4()}.jpg"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def matricular(app: FastAPI, session_id: UUID = CONTRACT_SESSION_ID) -> None:
    app.state.participant_repository.save(
        SessionParticipant.enroll(
            session_id=session_id, student_id=CONTRACT_STUDENT_ID, consented_at=NOW
        ).verified(NOW)
    )


def pedir(
    client: TestClient,
    ruta: str,
    *,
    token: str = TEACHER_TOKEN,
    kind: str = "image",
    session_id: UUID = CONTRACT_SESSION_ID,
    student_id: UUID = CONTRACT_STUDENT_ID,
) -> Any:
    return client.post(
        f"/api/v1/sessions/{session_id}/students/{student_id}/evidence-url",
        json={"path": ruta, "kind": kind},
        headers=bearer(token),
    )


class TestVerLaEvidencia:
    def test_el_docente_obtiene_una_url(self, authed_app: FastAPI) -> None:
        matricular(authed_app)

        with TestClient(authed_app) as client:
            respuesta = pedir(client, RUTA)

        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["url"]
        assert respuesta.json()["expires_in_seconds"] > 0

    def test_el_enlace_caduca(self, authed_app: FastAPI) -> None:
        """Uno copiado de la pantalla no puede valer para siempre: es la cara de
        un estudiante."""
        matricular(authed_app)

        with TestClient(authed_app) as client:
            respuesta = pedir(client, RUTA)

        assert 0 < respuesta.json()["expires_in_seconds"] <= 3600

    @pytest.mark.parametrize("kind", ["image", "audio", "reference_face"])
    def test_los_tres_tipos_de_evidencia(self, authed_app: FastAPI, kind: str) -> None:
        matricular(authed_app)
        extension = "jpg" if kind != "audio" else "webm"
        ruta = f"{CONTRACT_SESSION_ID}/{CONTRACT_STUDENT_ID}/{uuid4()}.{extension}"

        with TestClient(authed_app) as client:
            assert pedir(client, ruta, kind=kind).status_code == 200


class TestNoSeLeeLoAjeno:
    def test_una_ruta_de_otro_estudiante_se_rechaza(self, authed_app: FastAPI) -> None:
        """El agujero evidente: cambiar el estudiante en el cuerpo de la peticion.
        La ruta lleva el dueño en el prefijo, y tiene que coincidir."""
        matricular(authed_app)
        ajena = f"{CONTRACT_SESSION_ID}/{OTHER_STUDENT_ID}/{uuid4()}.jpg"

        with TestClient(authed_app) as client:
            respuesta = pedir(client, ajena)

        assert respuesta.status_code == 403

    def test_una_ruta_de_otro_examen_se_rechaza(self, authed_app: FastAPI) -> None:
        matricular(authed_app)
        ajena = f"{uuid4()}/{CONTRACT_STUDENT_ID}/{uuid4()}.jpg"

        with TestClient(authed_app) as client:
            respuesta = pedir(client, ajena)

        assert respuesta.status_code == 403

    def test_una_ruta_que_se_escapa_del_prefijo_se_rechaza(self, authed_app: FastAPI) -> None:
        matricular(authed_app)

        with TestClient(authed_app) as client:
            for ruta in (
                f"{CONTRACT_SESSION_ID}/{CONTRACT_STUDENT_ID}/../../otro/x.jpg",
                f"../{CONTRACT_SESSION_ID}/{CONTRACT_STUDENT_ID}/x.jpg",
                f"{CONTRACT_SESSION_ID}/{CONTRACT_STUDENT_ID}/",
                "x.jpg",
            ):
                assert pedir(client, ruta).status_code == 403, ruta

    def test_el_examen_de_otro_docente_se_rechaza(self, authed_app: FastAPI) -> None:
        matricular(authed_app)

        with TestClient(authed_app) as client:
            respuesta = pedir(client, RUTA, token=OTHER_TEACHER_TOKEN)

        assert respuesta.status_code == 403

    def test_un_estudiante_no_pide_urls_de_evidencia(self, authed_app: FastAPI) -> None:
        """Ni siquiera de la suya: la revision es del docente."""
        matricular(authed_app)

        with TestClient(authed_app) as client:
            respuesta = pedir(client, RUTA, token=STUDENT_TOKEN)

        assert respuesta.status_code == 403

    def test_sin_token_no_se_pide_nada(self, authed_app: FastAPI) -> None:
        matricular(authed_app)

        with TestClient(authed_app) as client:
            respuesta = client.post(
                f"/api/v1/sessions/{CONTRACT_SESSION_ID}"
                f"/students/{CONTRACT_STUDENT_ID}/evidence-url",
                json={"path": RUTA, "kind": "image"},
            )

        assert respuesta.status_code == 401


class TestElCasoTraeElAudio:
    def test_un_caso_sin_audio_devuelve_lista_vacia(self, authed_app: FastAPI) -> None:
        matricular(authed_app)

        with TestClient(authed_app) as client:
            caso = client.get(
                f"/api/v1/sessions/{CONTRACT_SESSION_ID}/students/{CONTRACT_STUDENT_ID}/case",
                headers=bearer(TEACHER_TOKEN),
            )

        assert caso.status_code == 200, caso.text
        assert caso.json()["audio_analyses"] == []

    def test_el_fragmento_analizado_llega_al_caso(
        self, authed_app: FastAPI, contract_example: Any
    ) -> None:
        """Es lo que deja al docente escuchar lo que se marcó, en vez de leer
        solo "posible consulta a IA"."""
        matricular(authed_app)
        ejemplo = contract_example("speech_detected")

        with TestClient(authed_app) as client:
            creado = client.post("/api/v1/events", json=ejemplo, headers=bearer(STUDENT_TOKEN))
            assert creado.status_code == 201, creado.text
            event_id = creado.json()["id"]

            medido = client.post(
                f"/api/v1/internal/audio-jobs/{event_id}/result",
                json={
                    "transcript": "como se calcula la mediana",
                    "similarity": 0.91,
                    "synthetic_voice_score": 0.88,
                    "processing_ms": 2400,
                    "model_versions": {"whisper": "small"},
                },
                headers={"X-Internal-Token": "secreto-interno-de-prueba"},
            )
            assert medido.status_code == 200, medido.text

            caso = client.get(
                f"/api/v1/sessions/{CONTRACT_SESSION_ID}/students/{CONTRACT_STUDENT_ID}/case",
                headers=bearer(TEACHER_TOKEN),
            )

        [analisis] = caso.json()["audio_analyses"]
        assert analisis["transcript"] == "como se calcula la mediana"
        assert analisis["similarity"] == 0.91
        # Las dos condiciones se cumplieron, asi que la API aviso.
        assert analisis["alerted"] is True
