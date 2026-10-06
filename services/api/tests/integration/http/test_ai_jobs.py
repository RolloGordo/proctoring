"""El contrato con `services/ai`: el worker mide, la API decide."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from proctoring_api.application.use_cases.manage_enrollment import DEFAULT_DEV_STUDENT_ID
from proctoring_api.application.use_cases.manage_questions import NewQuestion
from proctoring_api.domain.event import EventType, ProctoringEvent
from proctoring_api.domain.exam_session import (
    ExamSession,
    SupervisionModule,
    SupervisionPreset,
)
from proctoring_api.domain.participant import SessionParticipant
from proctoring_api.domain.question import QuestionType

from tests.conftest import (
    CONTRACT_STUDENT_ID,
    INTERNAL_TOKEN,
    NOW,
    STUDENT_TOKEN,
    TEACHER_ID,
    TEACHER_TOKEN,
)

pytestmark = pytest.mark.integration

INTERNO = {"X-Internal-Token": INTERNAL_TOKEN}
ENUNCIADO = "¿Qué garantiza Row Level Security en PostgreSQL?"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def examen_con_habla(app: Any, *, student_id: UUID = DEFAULT_DEV_STUDENT_ID) -> dict[str, Any]:
    """Una sesión estricta con una pregunta y un evento `speech_detected`."""
    sesion = ExamSession.create(
        teacher_id=TEACHER_ID,
        title="Parcial",
        starts_at=NOW - timedelta(minutes=5),
        duration_minutes=60,
        # STRICT es el preset que incluye ai_voice, con sus umbrales por defecto.
        preset=SupervisionPreset.STRICT,
    )
    app.state.session_repository.save(sesion)
    app.state.participant_repository.save(
        SessionParticipant.enroll(
            session_id=sesion.id, student_id=student_id, consented_at=NOW
        ).verified(NOW)
    )
    pregunta = app.state.add_questions.execute(
        sesion.id,
        [
            NewQuestion(
                question_type=QuestionType.MULTIPLE_CHOICE,
                statement=ENUNCIADO,
                options=[("Filtra filas", True), ("Comprime", False)],
            )
        ],
    )[0]
    evento = ProctoringEvent.create(
        session_id=sesion.id,
        student_id=student_id,
        question_id=pregunta.id,
        event_type=EventType.SPEECH_DETECTED,
        started_at=NOW,
        duration_ms=8_000,
        evidence_path="audio/fragmento.webm",
    )
    app.state.event_repository.save(evento)
    return {"sesion": sesion, "pregunta": pregunta, "evento": evento}


class TestElTrabajoDeAudio:
    def test_trae_el_enunciado_con_el_que_comparar(self, client: TestClient, app: Any) -> None:
        datos = examen_con_habla(app)

        respuesta = client.get(f"/api/v1/internal/audio-jobs/{datos['evento'].id}")

        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        # Sin el enunciado el worker no tiene con que comparar la transcripcion.
        assert cuerpo["question_statement"] == ENUNCIADO
        assert cuerpo["audio_path"] == "audio/fragmento.webm"
        assert cuerpo["similarity_threshold"] == 0.6
        assert cuerpo["synthetic_threshold"] == 0.5

    def test_un_evento_sin_audio_no_es_trabajo(self, client: TestClient, app: Any) -> None:
        sesion = ExamSession.create(
            teacher_id=TEACHER_ID,
            title="Parcial",
            starts_at=NOW - timedelta(minutes=5),
            duration_minutes=60,
        )
        app.state.session_repository.save(sesion)
        evento = ProctoringEvent.create(
            session_id=sesion.id,
            student_id=DEFAULT_DEV_STUDENT_ID,
            question_id=uuid4(),
            event_type=EventType.SPEECH_DETECTED,
            started_at=NOW,
            duration_ms=1000,
        )
        app.state.event_repository.save(evento)

        respuesta = client.get(f"/api/v1/internal/audio-jobs/{evento.id}")

        assert respuesta.status_code == 400
        assert "audio" in respuesta.json()["detail"]

    def test_un_evento_que_no_es_de_habla_tampoco(self, client: TestClient, app: Any) -> None:
        sesion = ExamSession.create(
            teacher_id=TEACHER_ID,
            title="Parcial",
            starts_at=NOW - timedelta(minutes=5),
            duration_minutes=60,
        )
        app.state.session_repository.save(sesion)
        evento = ProctoringEvent.create(
            session_id=sesion.id,
            student_id=DEFAULT_DEV_STUDENT_ID,
            question_id=None,
            event_type=EventType.FOCUS_LOST,
            started_at=NOW,
            duration_ms=3000,
            evidence_path="img/x.jpg",
        )
        app.state.event_repository.save(evento)

        assert client.get(f"/api/v1/internal/audio-jobs/{evento.id}").status_code == 400

    def test_un_evento_inexistente(self, client: TestClient) -> None:
        assert client.get(f"/api/v1/internal/audio-jobs/{uuid4()}").status_code == 400


class TestLaApiDecideSiAlerta:
    """La regla que define el proyecto, de punta a punta por HTTP."""

    def medir(self, client: TestClient, evento_id: UUID, **medidas: object) -> Any:
        return client.post(f"/api/v1/internal/audio-jobs/{evento_id}/result", json=medidas)

    def test_con_las_dos_condiciones_alerta(self, client: TestClient, app: Any) -> None:
        datos = examen_con_habla(app)

        respuesta = self.medir(
            client,
            datos["evento"].id,
            transcript="dime que garantiza row level security",
            similarity=0.88,
            synthetic_voice_score=0.76,
            processing_ms=2300,
            model_versions={"asr": "faster-whisper-small"},
        )

        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["alerted"] is True
        alertas = app.state.alert_repository.list_by_session(datos["sesion"].id)
        assert len(alertas) == 1
        assert alertas[0].severity.value == "high"

    def test_leer_en_voz_alta_no_alerta(self, client: TestClient, app: Any) -> None:
        # Mucha similitud, sin voz sintetica. Es el falso positivo que el
        # proyecto existe para evitar, y aqui se comprueba por HTTP.
        datos = examen_con_habla(app)

        respuesta = self.medir(
            client,
            datos["evento"].id,
            transcript=ENUNCIADO,
            similarity=0.97,
            synthetic_voice_score=0.04,
        )

        assert respuesta.json()["alerted"] is False
        assert app.state.alert_repository.list_by_session(datos["sesion"].id) == []

    def test_una_voz_de_fondo_sin_relacion_tampoco(self, client: TestClient, app: Any) -> None:
        datos = examen_con_habla(app)

        respuesta = self.medir(
            client, datos["evento"].id, similarity=0.12, synthetic_voice_score=0.93
        )

        assert respuesta.json()["alerted"] is False

    def test_lo_medido_queda_guardado_aunque_no_alerte(self, client: TestClient, app: Any) -> None:
        # Es evidencia y es lo que sostiene el informe de FPR.
        datos = examen_con_habla(app)

        self.medir(
            client,
            datos["evento"].id,
            transcript="leyendo la pregunta",
            similarity=0.9,
            synthetic_voice_score=0.1,
            processing_ms=1800,
        )

        guardado = app.state.audio_analysis_repository.find_by_event(datos["evento"].id)
        assert guardado is not None
        assert guardado.transcript == "leyendo la pregunta"
        assert guardado.processing_ms == 1800
        assert guardado.matched_question_id == datos["pregunta"].id

    def test_los_umbrales_de_la_sesion_mandan(self, client: TestClient, app: Any) -> None:
        datos = examen_con_habla(app)
        # Solo `custom` respeta los modulos que se pasan; con un preset con
        # nombre manda la configuracion del preset.
        exigente = ExamSession.create(
            teacher_id=TEACHER_ID,
            title="Exigente",
            starts_at=NOW - timedelta(minutes=5),
            duration_minutes=60,
            preset=SupervisionPreset.CUSTOM,
            modules={SupervisionModule.AI_VOICE: {"similarity_threshold": 0.95}},
        )
        app.state.session_repository.save(exigente)
        evento = ProctoringEvent.create(
            session_id=exigente.id,
            student_id=DEFAULT_DEV_STUDENT_ID,
            question_id=datos["pregunta"].id,
            event_type=EventType.SPEECH_DETECTED,
            started_at=NOW,
            duration_ms=5000,
            evidence_path="audio/otro.webm",
        )
        app.state.event_repository.save(evento)

        # La misma medida que alerta en la sesion normal, aqui no llega al umbral.
        assert (
            self.medir(client, evento.id, similarity=0.88, synthetic_voice_score=0.76).json()[
                "alerted"
            ]
            is False
        )

    def test_reprocesar_reemplaza_en_vez_de_acumular(self, client: TestClient, app: Any) -> None:
        # RQ reintenta hasta tres veces; eso no puede dejar tres filas.
        datos = examen_con_habla(app)

        self.medir(client, datos["evento"].id, similarity=0.1, synthetic_voice_score=0.1)
        self.medir(client, datos["evento"].id, similarity=0.9, synthetic_voice_score=0.9)

        guardado = app.state.audio_analysis_repository.find_by_event(datos["evento"].id)
        assert guardado is not None
        assert guardado.similarity == 0.9

    def test_una_medida_fuera_de_rango_se_rechaza(self, client: TestClient, app: Any) -> None:
        datos = examen_con_habla(app)

        assert self.medir(client, datos["evento"].id, similarity=1.5).status_code == 422

    def test_una_clave_de_mas_se_rechaza(self, client: TestClient, app: Any) -> None:
        datos = examen_con_habla(app)

        # El worker no puede colar un `severity` ni decidir por su cuenta.
        assert self.medir(client, datos["evento"].id, severity="high").status_code == 422


class TestElSecretoInterno:
    def test_sin_el_secreto_no_se_entra(self, authed_client: TestClient, authed_app: Any) -> None:
        datos = examen_con_habla(authed_app, student_id=CONTRACT_STUDENT_ID)

        respuesta = authed_client.get(f"/api/v1/internal/audio-jobs/{datos['evento'].id}")

        assert respuesta.status_code == 401

    def test_con_un_secreto_equivocado_tampoco(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        datos = examen_con_habla(authed_app, student_id=CONTRACT_STUDENT_ID)

        respuesta = authed_client.get(
            f"/api/v1/internal/audio-jobs/{datos['evento'].id}",
            headers={"X-Internal-Token": "casi-el-secreto"},
        )

        assert respuesta.status_code == 401

    def test_un_token_de_usuario_no_sirve_para_los_internos(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        # Un docente con sesion no debe poder escribir resultados de analisis.
        datos = examen_con_habla(authed_app, student_id=CONTRACT_STUDENT_ID)

        respuesta = authed_client.post(
            f"/api/v1/internal/audio-jobs/{datos['evento'].id}/result",
            json={"similarity": 0.9, "synthetic_voice_score": 0.9},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 401

    def test_con_el_secreto_correcto_si(self, authed_client: TestClient, authed_app: Any) -> None:
        datos = examen_con_habla(authed_app, student_id=CONTRACT_STUDENT_ID)

        respuesta = authed_client.get(
            f"/api/v1/internal/audio-jobs/{datos['evento'].id}", headers=INTERNO
        )

        assert respuesta.status_code == 200


class TestVerificacionDeIdentidad:
    def preparar(self, client: TestClient, app: Any) -> dict[str, Any]:
        datos = examen_con_habla(app)
        client.post("/api/v1/me/reference-face", json={"storage_path": "caras/ana.jpg"})
        return datos

    def test_el_estudiante_registra_su_rostro_y_pide_verificarse(
        self, client: TestClient, app: Any
    ) -> None:
        datos = self.preparar(client, app)

        respuesta = client.post(
            f"/api/v1/exam/{datos['sesion'].id}/identity/check",
            json={"capture_path": "capturas/ahora.jpg"},
        )

        # 202: la verificacion todavia no ocurrio, solo se encolo.
        assert respuesta.status_code == 202, respuesta.text
        assert app.state.job_queue.face_verification_jobs

    def test_sin_rostro_de_referencia_no_se_puede_verificar(
        self, client: TestClient, app: Any
    ) -> None:
        datos = examen_con_habla(app)

        respuesta = client.post(
            f"/api/v1/exam/{datos['sesion'].id}/identity/check",
            json={"capture_path": "capturas/ahora.jpg"},
        )

        assert respuesta.status_code == 400
        assert "referencia" in respuesta.json()["detail"]

    def test_el_worker_recibe_las_dos_rutas_y_el_umbral(self, client: TestClient, app: Any) -> None:
        datos = self.preparar(client, app)
        client.post(
            f"/api/v1/exam/{datos['sesion'].id}/identity/check",
            json={"capture_path": "capturas/ahora.jpg"},
        )
        participante_id, captura = app.state.job_queue.face_verification_jobs[0]

        respuesta = client.get(
            f"/api/v1/internal/face-jobs/{participante_id}", params={"capture_path": captura}
        )

        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["reference_path"] == "caras/ana.jpg"
        assert cuerpo["capture_path"] == "capturas/ahora.jpg"
        assert cuerpo["similarity_threshold"] == 0.45

    def test_una_coincidencia_deja_al_estudiante_listo(self, client: TestClient, app: Any) -> None:
        datos = self.preparar(client, app)

        respuesta = client.post(
            f"/api/v1/internal/sessions/{datos['sesion'].id}"
            f"/students/{DEFAULT_DEV_STUDENT_ID}/identity-result",
            json={"similarity": 0.81, "latency_ms": 180, "model_version": "arcface-1"},
        )

        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["result"] == "match"
        assert cuerpo["can_take_exam"] is True

    def test_un_fallo_no_expulsa_al_estudiante(self, client: TestClient, app: Any) -> None:
        # Queda esperando a que el docente lo admita a mano. Un reconocimiento que
        # falla con mala luz no puede costarle el examen a nadie.
        datos = self.preparar(client, app)

        respuesta = client.post(
            f"/api/v1/internal/sessions/{datos['sesion'].id}"
            f"/students/{DEFAULT_DEV_STUDENT_ID}/identity-result",
            json={"similarity": 0.1},
        )

        cuerpo = respuesta.json()
        assert cuerpo["result"] == "no_match"
        assert cuerpo["can_take_exam"] is False
        participante = app.state.participant_repository.find(
            datos["sesion"].id, DEFAULT_DEV_STUDENT_ID
        )
        assert participante is not None

    def test_sin_poder_medir_queda_inconcluso_y_no_verifica(
        self, client: TestClient, app: Any
    ) -> None:
        datos = self.preparar(client, app)

        respuesta = client.post(
            f"/api/v1/internal/sessions/{datos['sesion'].id}"
            f"/students/{DEFAULT_DEV_STUDENT_ID}/identity-result",
            json={"inconclusive": True},
        )

        assert respuesta.json()["result"] == "inconclusive"
        assert respuesta.json()["can_take_exam"] is False

    def test_el_resultado_queda_como_evidencia(self, client: TestClient, app: Any) -> None:
        datos = self.preparar(client, app)
        client.post(
            f"/api/v1/internal/sessions/{datos['sesion'].id}"
            f"/students/{DEFAULT_DEV_STUDENT_ID}/identity-result",
            json={"similarity": 0.81, "latency_ms": 180, "model_version": "arcface-1"},
        )

        eventos = app.state.event_repository.list_by_session(datos["sesion"].id)
        checks = [e for e in eventos if e.event_type is EventType.IDENTITY_CHECK]
        assert len(checks) == 1
        # Los numeros se guardan tambien cuando pasa: sostienen el informe de FAR/FRR.
        assert checks[0].metadata["similarity"] == 0.81
        assert checks[0].metadata["threshold"] == 0.45
        assert checks[0].metadata["latency_ms"] == 180

    def test_un_docente_no_registra_rostro_de_referencia(self, authed_client: TestClient) -> None:
        respuesta = authed_client.post(
            "/api/v1/me/reference-face",
            json={"storage_path": "caras/x.jpg"},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 403

    def test_sin_token_no_se_registra_rostro(self, authed_client: TestClient) -> None:
        assert (
            authed_client.post(
                "/api/v1/me/reference-face", json={"storage_path": "caras/x.jpg"}
            ).status_code
            == 401
        )

    def test_quien_no_participa_no_recibe_resultado(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        datos = examen_con_habla(authed_app, student_id=CONTRACT_STUDENT_ID)

        respuesta = authed_client.post(
            f"/api/v1/internal/sessions/{datos['sesion'].id}/students/{uuid4()}/identity-result",
            json={"similarity": 0.9},
            headers=INTERNO,
        )

        assert respuesta.status_code == 400

    def test_un_estudiante_no_verifica_por_otro(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        # El estudiante sale del token: no hay parametro con el que suplantar.
        datos = examen_con_habla(authed_app, student_id=CONTRACT_STUDENT_ID)
        authed_client.post(
            "/api/v1/me/reference-face",
            json={"storage_path": "caras/ana.jpg"},
            headers=bearer(STUDENT_TOKEN),
        )

        respuesta = authed_client.post(
            f"/api/v1/exam/{datos['sesion'].id}/identity/check",
            json={"capture_path": "capturas/ahora.jpg"},
            headers=bearer(STUDENT_TOKEN),
        )

        assert respuesta.status_code == 202
