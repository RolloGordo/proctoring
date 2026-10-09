"""Importar un archivo QTI a un banco, por HTTP.

Es lo que sustituye a escribir las preguntas una por una. Lo que más importa
aquí es qué pasa con lo que **no** se puede importar: un archivo con una
pregunta rara no puede perder las otras treinta y nueve en silencio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import OTHER_TEACHER_TOKEN, STUDENT_TOKEN, TEACHER_TOKEN

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "qti"
XML = {"Content-Type": "application/xml"}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", **XML}


def crear_banco(client: TestClient, nombre: str = "Banco QTI") -> str:
    respuesta = client.post(
        "/api/v1/question-banks",
        json={"name": nombre},
        headers={"Authorization": f"Bearer {TEACHER_TOKEN}"},
    )
    assert respuesta.status_code == 201, respuesta.text
    bank_id: str = respuesta.json()["id"]
    return bank_id


def fixture(nombre: str) -> bytes:
    return (FIXTURES / f"{nombre}.xml").read_bytes()


def importar(
    client: TestClient, bank_id: str, cuerpo: bytes, *, token: str = TEACHER_TOKEN, **params: Any
) -> Any:
    return client.post(
        f"/api/v1/question-banks/{bank_id}/import/qti",
        content=cuerpo,
        headers=bearer(token),
        params=params,
    )


class TestImportar:
    def test_una_pregunta_de_opcion_multiple_entra_entera(self, authed_client: TestClient) -> None:
        bank_id = crear_banco(authed_client)

        respuesta = importar(authed_client, bank_id, fixture("multiple_choice"))

        assert respuesta.status_code == 201, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["imported_count"] == 1
        [pregunta] = cuerpo["imported"]
        assert pregunta["question_type"] == "multiple_choice"
        assert len(pregunta["options"]) == 2
        assert sum(o["is_correct"] for o in pregunta["options"]) == 1

    @pytest.mark.parametrize(
        ("archivo", "tipo"),
        [
            ("essay", "essay"),
            ("fill_blank", "fill_blank"),
            ("multiple_choice", "multiple_choice"),
            ("numeric", "numeric"),
            ("numeric_tolerance", "numeric"),
            ("true_false", "true_false"),
        ],
    )
    def test_cada_fixture_llega_al_banco(
        self, authed_client: TestClient, archivo: str, tipo: str
    ) -> None:
        """Las seis que escribió Pierreluiggi, ahora por el camino real."""
        bank_id = crear_banco(authed_client)

        respuesta = importar(authed_client, bank_id, fixture(archivo))

        assert respuesta.status_code == 201, respuesta.text
        assert respuesta.json()["imported"][0]["question_type"] == tipo

    def test_la_tolerancia_numerica_sobrevive(self, authed_client: TestClient) -> None:
        """Sin ella, una respuesta de 3.14 contra pi se marcaría como error."""
        bank_id = crear_banco(authed_client)

        respuesta = importar(authed_client, bank_id, fixture("numeric_tolerance"))

        pregunta = respuesta.json()["imported"][0]
        assert pregunta["correct_numeric_answer"] is not None
        assert float(pregunta["numeric_tolerance"]) == 0.01

    def test_lo_importado_queda_en_el_banco(self, authed_client: TestClient) -> None:
        bank_id = crear_banco(authed_client)
        importar(authed_client, bank_id, fixture("multiple_choice"))

        en_el_banco = authed_client.get(
            f"/api/v1/question-banks/{bank_id}/questions",
            headers={"Authorization": f"Bearer {TEACHER_TOKEN}"},
        )

        assert len(en_el_banco.json()) == 1

    def test_importar_dos_veces_acumula_sin_pisar(self, authed_client: TestClient) -> None:
        """Un banco se llena a lo largo del ciclo, archivo a archivo."""
        bank_id = crear_banco(authed_client)
        importar(authed_client, bank_id, fixture("essay"))
        importar(authed_client, bank_id, fixture("numeric"))

        en_el_banco = authed_client.get(
            f"/api/v1/question-banks/{bank_id}/questions",
            headers={"Authorization": f"Bearer {TEACHER_TOKEN}"},
        )

        assert [q["question_type"] for q in en_el_banco.json()] == ["essay", "numeric"]
        assert [q["position"] for q in en_el_banco.json()] == [1, 2]

    def test_queda_marcado_de_donde_vino(self, authed_client: TestClient) -> None:
        """Permite responder después "esto se importó, no lo escribí yo"."""
        bank_id = crear_banco(authed_client)
        importar(authed_client, bank_id, fixture("essay"))

        en_el_banco = authed_client.get(
            f"/api/v1/question-banks/{bank_id}/questions",
            headers={"Authorization": f"Bearer {TEACHER_TOKEN}"},
        )

        assert en_el_banco.json()[0]["source_format"] == "qti"


class TestAvisosYDescartes:
    def test_completar_avisa_de_la_diferencia_al_calificar(self, authed_client: TestClient) -> None:
        """Aquí se ignoran tildes y mayúsculas; QTI exige coincidencia exacta.
        La pregunta entra, pero el docente tiene que saberlo."""
        bank_id = crear_banco(authed_client)

        respuesta = importar(authed_client, bank_id, fixture("fill_blank"))

        assert respuesta.json()["imported_count"] == 1
        assert len(respuesta.json()["warnings"]) == 1
        assert "tilde" in respuesta.json()["warnings"][0]["reason"].lower() or (
            "accent" in respuesta.json()["warnings"][0]["reason"].lower()
        )

    def test_un_item_raro_no_se_lleva_a_los_demas(self, authed_client: TestClient) -> None:
        """La promesa de fondo: importar cuarenta no falla por una."""
        bank_id = crear_banco(authed_client)
        # Dos items dentro de un contenedor: uno bueno y otro sin identificador,
        # que el importador no puede aceptar.
        bueno = fixture("essay").decode("utf-8").split("?>", 1)[-1].strip()
        roto = '<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1"/>'
        juntos = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<assessmentTest xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1">'
            f"{bueno}{roto}"
            "</assessmentTest>"
        )

        respuesta = importar(authed_client, bank_id, juntos.encode("utf-8"))

        assert respuesta.status_code == 201, respuesta.text
        assert respuesta.json()["imported_count"] == 1
        assert len(respuesta.json()["skipped"]) == 1


class TestEnsayo:
    def test_dry_run_no_guarda_nada(self, authed_client: TestClient) -> None:
        bank_id = crear_banco(authed_client)

        respuesta = importar(authed_client, bank_id, fixture("essay"), dry_run=True)

        assert respuesta.status_code == 201, respuesta.text
        assert respuesta.json()["dry_run"] is True
        en_el_banco = authed_client.get(
            f"/api/v1/question-banks/{bank_id}/questions",
            headers={"Authorization": f"Bearer {TEACHER_TOKEN}"},
        )
        assert en_el_banco.json() == []

    def test_dry_run_sigue_diciendo_que_se_quedaria_fuera(self, authed_client: TestClient) -> None:
        """Es justo para lo que sirve: mirar antes de guardar."""
        bank_id = crear_banco(authed_client)

        respuesta = importar(authed_client, bank_id, fixture("fill_blank"), dry_run=True)

        assert len(respuesta.json()["warnings"]) == 1


class TestArchivosMalos:
    def test_un_archivo_que_no_es_qti_se_rechaza(self, authed_client: TestClient) -> None:
        bank_id = crear_banco(authed_client)

        respuesta = importar(authed_client, bank_id, b"<html><body>no soy QTI</body></html>")

        assert respuesta.status_code == 400
        assert "qti" in respuesta.json()["detail"].lower()

    def test_un_xml_roto_se_rechaza(self, authed_client: TestClient) -> None:
        bank_id = crear_banco(authed_client)

        respuesta = importar(authed_client, bank_id, b"<assessmentItem")

        assert respuesta.status_code == 400

    def test_un_archivo_vacio_se_rechaza(self, authed_client: TestClient) -> None:
        bank_id = crear_banco(authed_client)

        assert importar(authed_client, bank_id, b"").status_code == 400

    def test_se_rechaza_un_xml_con_entidades(self, authed_client: TestClient) -> None:
        """La bomba de entidades: un XML que se expande hasta agotar la memoria."""
        bank_id = crear_banco(authed_client)
        bomba = (
            b'<?xml version="1.0"?>'
            b'<!DOCTYPE lolz [<!ENTITY lol "lol">'
            b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]>'
            b"<assessmentItem>&lol2;</assessmentItem>"
        )

        respuesta = importar(authed_client, bank_id, bomba)

        assert respuesta.status_code == 400

    def test_un_archivo_enorme_se_rechaza_sin_leerlo(self, authed_client: TestClient) -> None:
        """413 y no 400: el problema es el tamaño, no el contenido. Y se mira el
        `Content-Length` antes de cargar nada en memoria."""
        bank_id = crear_banco(authed_client)

        respuesta = importar(authed_client, bank_id, b"<x/>" + b"a" * 1_000_001)

        assert respuesta.status_code == 413


class TestPermisos:
    def test_no_se_importa_a_un_banco_ajeno(self, authed_client: TestClient) -> None:
        bank_id = crear_banco(authed_client)

        respuesta = importar(authed_client, bank_id, fixture("essay"), token=OTHER_TEACHER_TOKEN)

        assert respuesta.status_code == 403

    def test_un_banco_inexistente_responde_igual_que_uno_ajeno(
        self, authed_client: TestClient
    ) -> None:
        bank_id = crear_banco(authed_client)

        ajeno = importar(authed_client, bank_id, fixture("essay"), token=OTHER_TEACHER_TOKEN)
        no_existe = importar(
            authed_client, str(uuid4()), fixture("essay"), token=OTHER_TEACHER_TOKEN
        )

        assert ajeno.status_code == no_existe.status_code == 403
        assert ajeno.json() == no_existe.json()

    def test_un_estudiante_no_importa_preguntas(self, authed_client: TestClient) -> None:
        bank_id = crear_banco(authed_client)

        respuesta = importar(authed_client, bank_id, fixture("essay"), token=STUDENT_TOKEN)

        assert respuesta.status_code == 403

    def test_sin_token_no_se_importa(self, authed_client: TestClient) -> None:
        bank_id = crear_banco(authed_client)

        respuesta = authed_client.post(
            f"/api/v1/question-banks/{bank_id}/import/qti",
            content=fixture("essay"),
            headers=XML,
        )

        assert respuesta.status_code == 401

    def test_un_rechazo_no_deja_nada_a_medias(self, authed_client: TestClient) -> None:
        """Un 403 no puede dejar preguntas sueltas en el banco."""
        bank_id = crear_banco(authed_client)
        importar(authed_client, bank_id, fixture("essay"), token=OTHER_TEACHER_TOKEN)

        en_el_banco = authed_client.get(
            f"/api/v1/question-banks/{bank_id}/questions",
            headers={"Authorization": f"Bearer {TEACHER_TOKEN}"},
        )

        assert en_el_banco.json() == []
