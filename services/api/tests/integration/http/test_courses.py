"""Cursos: crearlos, matricular por correo y ver las clases. Foco en autorización."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.participant import SessionParticipant
from proctoring_api.domain.user import ProfileSummary, UserRole

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

#: Un segundo docente: sus cursos no son del TEACHER_ID de las pruebas.
OTRO_DOCENTE_ID = UUID("5c4b3a29-1807-4f6e-9d5c-4b3a29180716")
CORREO_ESTUDIANTE = "ana@upao.edu.pe"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def registrar_perfiles(app: Any) -> None:
    """Da nombre y correo a las personas de las pruebas, como haria `public.profiles`."""
    repo = app.state.profile_repository
    repo.add_profile(
        ProfileSummary(CONTRACT_STUDENT_ID, UserRole.STUDENT, CORREO_ESTUDIANTE, "Ana Rojas")
    )
    repo.add_profile(
        ProfileSummary(OTHER_STUDENT_ID, UserRole.STUDENT, "luis@upao.edu.pe", "Luis Paz")
    )
    repo.add_profile(
        ProfileSummary(TEACHER_ID, UserRole.TEACHER, "docente@upao.edu.pe", "Docente Uno")
    )


def crear_curso(client: TestClient, nombre: str = "Taller Integrador 1") -> dict[str, Any]:
    respuesta = client.post(
        "/api/v1/courses",
        json={"name": nombre, "section": "A"},
        headers=bearer(TEACHER_TOKEN),
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()  # type: ignore[no-any-return]


class TestCrear:
    def test_el_docente_crea_su_curso(self, authed_client: TestClient) -> None:
        curso = crear_curso(authed_client)

        assert curso["name"] == "Taller Integrador 1"
        assert curso["section"] == "A"
        assert curso["student_count"] == 0

    def test_un_estudiante_no_crea_cursos(self, authed_client: TestClient) -> None:
        respuesta = authed_client.post(
            "/api/v1/courses", json={"name": "Mio"}, headers=bearer(STUDENT_TOKEN)
        )

        assert respuesta.status_code == 403

    def test_400_con_el_nombre_en_blanco(self, authed_client: TestClient) -> None:
        respuesta = authed_client.post(
            "/api/v1/courses", json={"name": "   "}, headers=bearer(TEACHER_TOKEN)
        )

        assert respuesta.status_code == 400

    def test_422_con_una_clave_de_mas(self, authed_client: TestClient) -> None:
        respuesta = authed_client.post(
            "/api/v1/courses",
            json={"name": "X", "teacher_id": str(OTRO_DOCENTE_ID)},
            headers=bearer(TEACHER_TOKEN),
        )

        # El dueno sale del token: no se puede crear un curso a nombre de otro.
        assert respuesta.status_code == 422

    def test_sin_token_responde_401(self, authed_client: TestClient) -> None:
        assert authed_client.post("/api/v1/courses", json={"name": "X"}).status_code == 401


class TestMatricular:
    def test_matricula_por_correo_y_aparece_en_la_lista(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        registrar_perfiles(authed_app)
        curso = crear_curso(authed_client)

        respuesta = authed_client.post(
            f"/api/v1/courses/{curso['id']}/students",
            json={"email": CORREO_ESTUDIANTE},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["already_enrolled"] is False
        lista = authed_client.get(
            f"/api/v1/courses/{curso['id']}/students", headers=bearer(TEACHER_TOKEN)
        ).json()
        assert [(m["email"], m["full_name"]) for m in lista] == [(CORREO_ESTUDIANTE, "Ana Rojas")]

    def test_no_distingue_mayusculas_en_el_correo(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        registrar_perfiles(authed_app)
        curso = crear_curso(authed_client)

        respuesta = authed_client.post(
            f"/api/v1/courses/{curso['id']}/students",
            json={"email": "  ANA@UPAO.EDU.PE "},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 200

    def test_es_idempotente(self, authed_client: TestClient, authed_app: Any) -> None:
        registrar_perfiles(authed_app)
        curso = crear_curso(authed_client)
        url = f"/api/v1/courses/{curso['id']}/students"
        cuerpo = {"email": CORREO_ESTUDIANTE}

        authed_client.post(url, json=cuerpo, headers=bearer(TEACHER_TOKEN))
        segunda = authed_client.post(url, json=cuerpo, headers=bearer(TEACHER_TOKEN))

        assert segunda.status_code == 200
        assert segunda.json()["already_enrolled"] is True
        assert len(authed_client.get(url, headers=bearer(TEACHER_TOKEN)).json()) == 1

    def test_un_correo_inexistente_y_uno_de_docente_responden_lo_mismo(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        # Distinguirlos le diria a cualquier docente quien tiene cuenta y con que rol.
        registrar_perfiles(authed_app)
        curso = crear_curso(authed_client)
        url = f"/api/v1/courses/{curso['id']}/students"

        inexistente = authed_client.post(
            url, json={"email": "nadie@upao.edu.pe"}, headers=bearer(TEACHER_TOKEN)
        )
        de_docente = authed_client.post(
            url, json={"email": "docente@upao.edu.pe"}, headers=bearer(TEACHER_TOKEN)
        )

        assert inexistente.status_code == de_docente.status_code == 400
        assert inexistente.json() == de_docente.json()

    def test_422_con_algo_que_no_es_un_correo(self, authed_client: TestClient) -> None:
        curso = crear_curso(authed_client)

        respuesta = authed_client.post(
            f"/api/v1/courses/{curso['id']}/students",
            json={"email": "no-es-un-correo"},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 422

    def test_la_lista_de_cursos_cuenta_los_estudiantes(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        registrar_perfiles(authed_app)
        curso = crear_curso(authed_client)
        for correo in (CORREO_ESTUDIANTE, "luis@upao.edu.pe"):
            authed_client.post(
                f"/api/v1/courses/{curso['id']}/students",
                json={"email": correo},
                headers=bearer(TEACHER_TOKEN),
            )

        [listado] = authed_client.get("/api/v1/courses", headers=bearer(TEACHER_TOKEN)).json()

        assert listado["student_count"] == 2


class TestAccesoAjeno:
    """Un docente no ve ni toca los cursos de otro: ahi hay nombres y correos."""

    def curso_de_otro_docente(self, app: Any) -> str:
        from proctoring_api.domain.course import Course

        curso = Course.create(teacher_id=OTRO_DOCENTE_ID, name="Ajeno", created_at=NOW)
        app.state.course_repository.save(curso)
        return str(curso.id)

    def test_no_se_ve_un_curso_ajeno(self, authed_client: TestClient, authed_app: Any) -> None:
        ajeno = self.curso_de_otro_docente(authed_app)

        respuesta = authed_client.get(f"/api/v1/courses/{ajeno}", headers=bearer(TEACHER_TOKEN))

        assert respuesta.status_code == 403

    def test_ajeno_e_inexistente_responden_lo_mismo(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        # Distinguirlos permitiria averiguar que cursos existen.
        ajeno = self.curso_de_otro_docente(authed_app)

        de_otro = authed_client.get(f"/api/v1/courses/{ajeno}", headers=bearer(TEACHER_TOKEN))
        inventado = authed_client.get(f"/api/v1/courses/{uuid4()}", headers=bearer(TEACHER_TOKEN))

        assert de_otro.status_code == inventado.status_code == 403
        assert de_otro.json() == inventado.json()

    def test_no_se_matricula_en_un_curso_ajeno(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        registrar_perfiles(authed_app)
        ajeno = self.curso_de_otro_docente(authed_app)

        respuesta = authed_client.post(
            f"/api/v1/courses/{ajeno}/students",
            json={"email": CORREO_ESTUDIANTE},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 403

    def test_no_se_lista_a_los_estudiantes_de_un_curso_ajeno(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        ajeno = self.curso_de_otro_docente(authed_app)

        respuesta = authed_client.get(
            f"/api/v1/courses/{ajeno}/students", headers=bearer(TEACHER_TOKEN)
        )

        assert respuesta.status_code == 403

    def test_la_lista_de_cursos_solo_trae_los_propios(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        self.curso_de_otro_docente(authed_app)
        crear_curso(authed_client, "Mio")

        nombres = [
            c["name"]
            for c in authed_client.get("/api/v1/courses", headers=bearer(TEACHER_TOKEN)).json()
        ]

        assert nombres == ["Mio"]

    def test_un_estudiante_no_lista_cursos_de_docente(self, authed_client: TestClient) -> None:
        respuesta = authed_client.get("/api/v1/courses", headers=bearer(STUDENT_TOKEN))

        assert respuesta.status_code == 403


class TestExamenEnUnCurso:
    def datos(self, client: TestClient) -> dict[str, Any]:
        return {
            "title": "Parcial",
            "starts_at": (NOW + timedelta(days=1)).isoformat(),
            "duration_minutes": 60,
        }

    def test_un_examen_se_asocia_a_un_curso_propio(self, authed_client: TestClient) -> None:
        curso = crear_curso(authed_client)

        respuesta = authed_client.post(
            "/api/v1/sessions",
            json={**self.datos(authed_client), "course_id": curso["id"]},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 201, respuesta.text
        assert respuesta.json()["course_id"] == curso["id"]

    def test_no_se_cuelga_un_examen_del_curso_de_otro(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        from proctoring_api.domain.course import Course

        ajeno = Course.create(teacher_id=OTRO_DOCENTE_ID, name="Ajeno", created_at=NOW)
        authed_app.state.course_repository.save(ajeno)

        respuesta = authed_client.post(
            "/api/v1/sessions",
            json={**self.datos(authed_client), "course_id": str(ajeno.id)},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 403

    def test_un_curso_inventado_responde_403_y_no_un_error_de_base(
        self, authed_client: TestClient
    ) -> None:
        # Sin esta comprobacion, un id inexistente llegaba a la base y volvia como
        # un error de clave foranea, incomprensible para el docente.
        respuesta = authed_client.post(
            "/api/v1/sessions",
            json={**self.datos(authed_client), "course_id": str(uuid4())},
            headers=bearer(TEACHER_TOKEN),
        )

        assert respuesta.status_code == 403


class TestMisClases:
    def clase_con_examen(self, client: TestClient, app: Any) -> tuple[str, str]:
        registrar_perfiles(app)
        curso = crear_curso(client, "Base de Datos")
        client.post(
            f"/api/v1/courses/{curso['id']}/students",
            json={"email": CORREO_ESTUDIANTE},
            headers=bearer(TEACHER_TOKEN),
        )
        sesion = client.post(
            "/api/v1/sessions",
            json={
                "title": "Parcial 1",
                "starts_at": (NOW + timedelta(days=2)).isoformat(),
                "duration_minutes": 90,
                "course_id": curso["id"],
            },
            headers=bearer(TEACHER_TOKEN),
        ).json()
        return curso["id"], sesion["id"]

    def test_el_estudiante_ve_su_clase_y_los_examenes_que_vienen(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        curso_id, sesion_id = self.clase_con_examen(authed_client, authed_app)

        [clase] = authed_client.get("/api/v1/me/courses", headers=bearer(STUDENT_TOKEN)).json()

        assert clase["id"] == curso_id
        assert clase["name"] == "Base de Datos"
        assert [e["session_id"] for e in clase["exams"]] == [sesion_id]

    def test_no_se_filtra_el_codigo_de_acceso(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        # Estar en la clase no da acceso al examen: para rendirlo hace falta el
        # codigo, que el docente reparte.
        self.clase_con_examen(authed_client, authed_app)

        texto = authed_client.get("/api/v1/me/courses", headers=bearer(STUDENT_TOKEN)).text

        assert "access_code" not in texto

    def test_quien_no_esta_matriculado_no_ve_la_clase(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        self.clase_con_examen(authed_client, authed_app)

        ajeno = authed_client.get("/api/v1/me/courses", headers=bearer(OTHER_STUDENT_TOKEN))

        assert ajeno.json() == []

    def test_un_docente_recibe_403(self, authed_client: TestClient) -> None:
        assert (
            authed_client.get("/api/v1/me/courses", headers=bearer(TEACHER_TOKEN)).status_code
            == 403
        )


class TestSalaDeEsperaConNombres:
    def test_la_sala_muestra_nombre_y_correo(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        registrar_perfiles(authed_app)
        sesion = ExamSession.create(
            teacher_id=TEACHER_ID,
            title="Parcial",
            starts_at=NOW - timedelta(minutes=2),
            duration_minutes=60,
        )
        authed_app.state.session_repository.save(sesion)
        authed_app.state.participant_repository.save(
            SessionParticipant.enroll(
                session_id=sesion.id, student_id=CONTRACT_STUDENT_ID, consented_at=NOW
            )
        )

        [participante] = authed_client.get(
            f"/api/v1/sessions/{sesion.id}/participants", headers=bearer(TEACHER_TOKEN)
        ).json()

        assert participante["student_name"] == "Ana Rojas"
        assert participante["student_email"] == CORREO_ESTUDIANTE

    def test_sin_perfil_se_muestra_igual_sin_nombre(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        sesion = ExamSession.create(
            teacher_id=TEACHER_ID,
            title="Parcial",
            starts_at=NOW - timedelta(minutes=2),
            duration_minutes=60,
        )
        authed_app.state.session_repository.save(sesion)
        authed_app.state.participant_repository.save(
            SessionParticipant.enroll(session_id=sesion.id, student_id=uuid4(), consented_at=NOW)
        )

        [participante] = authed_client.get(
            f"/api/v1/sessions/{sesion.id}/participants", headers=bearer(TEACHER_TOKEN)
        ).json()

        # Sigue siendo un participante: esconderlo seria mentirle al docente.
        assert participante["student_name"] is None
