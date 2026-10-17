"""Revisión de caso y decisión: el auditor reúne evidencia, el docente decide."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from proctoring_api.domain.event import EventType, ProctoringEvent
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.participant import SessionParticipant
from proctoring_api.domain.user import ProfileSummary, UserRole

from tests.conftest import (
    CONTRACT_STUDENT_ID,
    NOW,
    STUDENT_TOKEN,
    TEACHER_ID,
    TEACHER_TOKEN,
)

pytestmark = pytest.mark.integration

OTRO_DOCENTE_ID = UUID("5c4b3a29-1807-4f6e-9d5c-4b3a29180716")
JUSTIFICACION = "El monitor adicional es el habitual del estudiante, lo confirmo con el."


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def caso(app: Any, *, docente: UUID = TEACHER_ID) -> tuple[str, str]:
    """Una sesion con un estudiante que participo y dejo senales."""
    sesion = ExamSession.create(
        teacher_id=docente,
        title="Parcial",
        starts_at=NOW - timedelta(minutes=30),
        duration_minutes=90,
    )
    app.state.session_repository.save(sesion)
    app.state.participant_repository.save(
        SessionParticipant.enroll(
            session_id=sesion.id, student_id=CONTRACT_STUDENT_ID, consented_at=NOW
        ).verified(NOW)
    )
    app.state.profile_repository.add_profile(
        ProfileSummary(CONTRACT_STUDENT_ID, UserRole.STUDENT, "ana@upao.edu.pe", "Ana Rojas")
    )
    for tipo, duracion in [
        (EventType.SUSPICIOUS_PROCESS, 0),
        (EventType.FOCUS_LOST, 3_000),
        (EventType.EXTRA_DISPLAY, 0),
    ]:
        app.state.event_repository.save(
            ProctoringEvent.create(
                session_id=sesion.id,
                student_id=CONTRACT_STUDENT_ID,
                question_id=None,
                event_type=tipo,
                started_at=NOW - timedelta(minutes=10),
                duration_ms=duracion,
                metadata={"process_name": "anydesk"}
                if tipo is EventType.SUSPICIOUS_PROCESS
                else {},
            )
        )
    return str(sesion.id), str(CONTRACT_STUDENT_ID)


class TestRevisar:
    def test_reune_la_evidencia_del_estudiante(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sid, est = caso(authed_app)

        respuesta = authed_client.get(
            f"/api/v1/sessions/{sid}/students/{est}/case", headers=bearer(TEACHER_TOKEN)
        )

        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["participant"]["student_name"] == "Ana Rojas"
        assert len(cuerpo["events"]) == 3
        assert cuerpo["decisions"] == []

    def test_trae_el_riesgo_con_su_desglose(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sid, est = caso(authed_app)

        riesgo = authed_client.get(
            f"/api/v1/sessions/{sid}/students/{est}/case", headers=bearer(TEACHER_TOKEN)
        ).json()["risk"]

        assert riesgo["level"] in {"medium", "high"}
        assert riesgo["score"] == sum(s["points"] for s in riesgo["signals"])
        # El desglose es lo que importa: sin el, el numero no se puede discutir.
        assert {s["event_type"] for s in riesgo["signals"]} == {
            "suspicious_process",
            "focus_lost",
            "extra_display",
        }

    def test_solo_trae_los_eventos_de_ese_estudiante(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sid, est = caso(authed_app)
        # Otro estudiante, otra senal en la misma sesion.
        authed_app.state.event_repository.save(
            ProctoringEvent.create(
                session_id=UUID(sid),
                student_id=uuid4(),
                question_id=None,
                event_type=EventType.EXTRA_PERSON,
                started_at=NOW,
                duration_ms=0,
            )
        )

        eventos = authed_client.get(
            f"/api/v1/sessions/{sid}/students/{est}/case", headers=bearer(TEACHER_TOKEN)
        ).json()["events"]

        assert "extra_person" not in {e["event_type"] for e in eventos}


class TestAccesoAjeno:
    def test_un_estudiante_no_revisa_casos(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sid, est = caso(authed_app)

        respuesta = authed_client.get(
            f"/api/v1/sessions/{sid}/students/{est}/case", headers=bearer(STUDENT_TOKEN)
        )

        assert respuesta.status_code == 403

    def test_un_docente_no_revisa_el_caso_de_la_sesion_de_otro(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sid, est = caso(authed_app, docente=OTRO_DOCENTE_ID)

        respuesta = authed_client.get(
            f"/api/v1/sessions/{sid}/students/{est}/case", headers=bearer(TEACHER_TOKEN)
        )

        assert respuesta.status_code == 403

    def test_sesion_ajena_e_inexistente_y_estudiante_ajeno_responden_lo_mismo(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        # Distinguirlos permitiria averiguar que sesiones y que estudiantes existen.
        sid, est = caso(authed_app)
        ajena, est_ajena = caso(authed_app, docente=OTRO_DOCENTE_ID)

        sesion_ajena = authed_client.get(
            f"/api/v1/sessions/{ajena}/students/{est_ajena}/case", headers=bearer(TEACHER_TOKEN)
        )
        inexistente = authed_client.get(
            f"/api/v1/sessions/{uuid4()}/students/{est}/case", headers=bearer(TEACHER_TOKEN)
        )
        no_participo = authed_client.get(
            f"/api/v1/sessions/{sid}/students/{uuid4()}/case", headers=bearer(TEACHER_TOKEN)
        )

        assert {r.status_code for r in (sesion_ajena, inexistente, no_participo)} == {403}

    def test_sin_token_responde_401(self, authed_client: TestClient, authed_app: Any) -> None:
        sid, est = caso(authed_app)

        assert authed_client.get(f"/api/v1/sessions/{sid}/students/{est}/case").status_code == 401
        assert (
            authed_client.post(
                f"/api/v1/sessions/{sid}/students/{est}/decision",
                json={"decision": "dismissed", "justification": JUSTIFICACION},
            ).status_code
            == 401
        )


class TestDecidir:
    def decidir(
        self,
        client: TestClient,
        sid: str,
        est: str,
        decision: str = "dismissed",
        justificacion: str = JUSTIFICACION,
        token: str = TEACHER_TOKEN,
    ) -> Any:
        return client.post(
            f"/api/v1/sessions/{sid}/students/{est}/decision",
            json={"decision": decision, "justification": justificacion},
            headers=bearer(token),
        )

    def test_el_docente_decide_con_justificacion(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sid, est = caso(authed_app)

        respuesta = self.decidir(authed_client, sid, est)

        assert respuesta.status_code == 201, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["decision"] == "dismissed"
        assert cuerpo["justification"] == JUSTIFICACION
        # Quien decide sale del token, no del cuerpo.
        assert cuerpo["teacher_id"] == str(TEACHER_ID)

    def test_sin_justificacion_suficiente_responde_400_y_no_guarda_nada(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        # La promesa central del proyecto: nadie decide sin explicar por que.
        sid, est = caso(authed_app)

        respuesta = self.decidir(authed_client, sid, est, justificacion="ok")

        assert respuesta.status_code == 400
        assert "al menos" in respuesta.json()["detail"]
        decisiones = authed_client.get(
            f"/api/v1/sessions/{sid}/decisions", headers=bearer(TEACHER_TOKEN)
        ).json()
        assert decisiones == []

    def test_una_decision_desconocida_responde_422(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sid, est = caso(authed_app)

        assert self.decidir(authed_client, sid, est, decision="anular").status_code == 422

    def test_no_se_puede_decidir_por_otro_docente(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sid, est = caso(authed_app)

        respuesta = authed_client.post(
            f"/api/v1/sessions/{sid}/students/{est}/decision",
            json={
                "decision": "confirmed",
                "justification": JUSTIFICACION,
                "teacher_id": str(OTRO_DOCENTE_ID),
            },
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 422

    def test_un_estudiante_no_decide(self, authed_client: TestClient, authed_app: Any) -> None:
        sid, est = caso(authed_app)

        assert self.decidir(authed_client, sid, est, token=STUDENT_TOKEN).status_code == 403

    def test_no_se_decide_sobre_una_sesion_ajena(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sid, est = caso(authed_app, docente=OTRO_DOCENTE_ID)

        assert self.decidir(authed_client, sid, est).status_code == 403

    def test_no_se_decide_sobre_quien_no_participo(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sid, _ = caso(authed_app)

        assert self.decidir(authed_client, sid, str(uuid4())).status_code == 403

    def test_cambiar_de_parecer_agrega_otra_y_conserva_el_historial(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        # Una decision es evidencia: no se edita ni se borra.
        sid, est = caso(authed_app)
        self.decidir(
            authed_client,
            sid,
            est,
            decision="confirmed",
            justificacion="Vi el acceso remoto abierto.",
        )
        authed_app.state.decision_repository.list_by_session(UUID(sid))  # no debe fallar
        self.decidir(authed_client, sid, est, decision="dismissed", justificacion=JUSTIFICACION)

        decisiones = authed_client.get(
            f"/api/v1/sessions/{sid}/students/{est}/case", headers=bearer(TEACHER_TOKEN)
        ).json()["decisions"]

        assert len(decisiones) == 2
        # La vigente es la primera: la mas reciente.
        assert decisiones[0]["decision"] == "dismissed"
        assert decisiones[1]["decision"] == "confirmed"

    def test_decidir_no_anula_ni_cambia_el_examen_del_estudiante(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        # El sistema es un auditor, no un juez: decidir registra, no ejecuta.
        sid, est = caso(authed_app)
        antes = authed_app.state.participant_repository.find(UUID(sid), CONTRACT_STUDENT_ID)

        self.decidir(authed_client, sid, est, decision="confirmed")

        despues = authed_app.state.participant_repository.find(UUID(sid), CONTRACT_STUDENT_ID)
        assert despues == antes


class TestListarDecisiones:
    def test_un_estudiante_no_ve_las_decisiones(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sid, _ = caso(authed_app)

        assert (
            authed_client.get(
                f"/api/v1/sessions/{sid}/decisions", headers=bearer(STUDENT_TOKEN)
            ).status_code
            == 403
        )

    def test_un_docente_no_ve_las_decisiones_de_otro(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sid, _ = caso(authed_app, docente=OTRO_DOCENTE_ID)

        assert (
            authed_client.get(
                f"/api/v1/sessions/{sid}/decisions", headers=bearer(TEACHER_TOKEN)
            ).status_code
            == 403
        )


class TestElEstudianteVeLaDecision:
    """`GET /me/exams/{id}/decision`.

    El sistema obliga al docente a justificar por escrito lo que decide, y esa
    justificacion solo la veia el. Prometerle al estudiante transparencia sobre
    lo que se observa y callarle por que se decidio lo que se decidio es
    transparencia a medias.

    Todo va con tokens reales: lo que se prueba es que cada quien ve lo suyo, y
    sin autenticacion no hay "cada quien".
    """

    def decidir(self, client: TestClient, sesion: str, estudiante: str, tipo: str) -> None:
        respuesta = client.post(
            f"/api/v1/sessions/{sesion}/students/{estudiante}/decision",
            json={"decision": tipo, "justification": JUSTIFICACION},
            headers=bearer(TEACHER_TOKEN),
        )
        assert respuesta.status_code in (200, 201), respuesta.text

    def mia(self, client: TestClient, sesion: str) -> Any:
        return client.get(f"/api/v1/me/exams/{sesion}/decision", headers=bearer(STUDENT_TOKEN))

    def test_ve_la_decision_y_su_justificacion(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sesion, estudiante = caso(authed_app)
        self.decidir(authed_client, sesion, estudiante, "dismissed")

        respuesta = self.mia(authed_client, sesion)

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["decision"] == "dismissed"
        assert cuerpo["justification"] == JUSTIFICACION

    def test_sin_decision_devuelve_nulo_y_no_404(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        # Que un caso este bajo revision no es informacion que ayude: presiona.
        sesion, _ = caso(authed_app)

        respuesta = self.mia(authed_client, sesion)

        assert respuesta.status_code == 200
        assert respuesta.json() is None

    def test_si_el_docente_se_corrige_vale_lo_ultimo(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sesion, estudiante = caso(authed_app)
        self.decidir(authed_client, sesion, estudiante, "confirmed")
        self.decidir(authed_client, sesion, estudiante, "dismissed")

        assert self.mia(authed_client, sesion).json()["decision"] == "dismissed"

    def test_no_se_ve_la_decision_de_un_examen_ajeno(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sesion = ExamSession.create(
            teacher_id=TEACHER_ID,
            title="Examen de otro grupo",
            starts_at=NOW - timedelta(minutes=30),
            duration_minutes=90,
        )
        authed_app.state.session_repository.save(sesion)

        assert self.mia(authed_client, str(sesion.id)).status_code == 403

    def test_una_sesion_inexistente_responde_igual(self, authed_client: TestClient) -> None:
        assert self.mia(authed_client, str(uuid4())).status_code == 403

    def test_el_docente_tiene_su_propia_vista(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sesion, _ = caso(authed_app)

        respuesta = authed_client.get(
            f"/api/v1/me/exams/{sesion}/decision", headers=bearer(TEACHER_TOKEN)
        )

        assert respuesta.status_code == 403

    def test_cada_estudiante_ve_solo_la_suya(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        # Lo decisivo: se busca por la matricula de quien pregunta, no por un
        # identificador que venga del cliente.
        sesion, estudiante = caso(authed_app)
        self.decidir(authed_client, sesion, estudiante, "confirmed")

        assert self.mia(authed_client, sesion).json()["student_id"] == estudiante
