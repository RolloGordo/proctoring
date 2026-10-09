"""El codigo de acceso se puede guardar hasta la hora de inicio.

Lo que se prueba aqui es que **la API no lo devuelve**, no que la pantalla no lo
pinte. Esconderlo solo en la pantalla seria decoracion: el codigo viajaria en el
JSON y cualquiera con la consola del navegador abierta lo leeria.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import NOW, TEACHER_TOKEN

pytestmark = pytest.mark.integration


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def crear(client: TestClient, **extra: Any) -> dict[str, Any]:
    """Un examen que empieza en una hora, o lo que diga `starts_at`."""
    cuerpo: dict[str, Any] = {
        "title": "Examen con codigo guardado",
        "starts_at": (NOW + timedelta(hours=1)).isoformat(),
        "duration_minutes": 60,
        **extra,
    }
    respuesta = client.post("/api/v1/sessions", json=cuerpo, headers=bearer(TEACHER_TOKEN))
    assert respuesta.status_code == 201, respuesta.text
    datos: dict[str, Any] = respuesta.json()
    return datos


class TestSinLaOpcion:
    def test_por_defecto_el_codigo_se_ve(self, authed_client: TestClient) -> None:
        """Es como funcionaban los examenes antes de que existiera la opcion, y
        los ya creados tienen que seguir igual."""
        examen = crear(authed_client)

        assert examen["reveal_code_at_start"] is False
        assert examen["access_code"]


class TestConLaOpcion:
    def test_al_crearlo_no_viene_el_codigo(self, authed_client: TestClient) -> None:
        """Ni en la respuesta de creacion. Si viniera aqui, guardarlo despues no
        serviria de nada: es el primer sitio donde el docente lo veria."""
        examen = crear(authed_client, reveal_code_at_start=True)

        assert examen["reveal_code_at_start"] is True
        assert examen["access_code"] is None

    def test_tampoco_al_pedir_el_examen(self, authed_client: TestClient) -> None:
        examen = crear(authed_client, reveal_code_at_start=True)

        traido = authed_client.get(
            f"/api/v1/sessions/{examen['id']}", headers=bearer(TEACHER_TOKEN)
        )

        assert traido.status_code == 200, traido.text
        assert traido.json()["access_code"] is None

    def test_tampoco_en_el_listado(self, authed_client: TestClient) -> None:
        examen = crear(authed_client, reveal_code_at_start=True)

        lista = authed_client.get("/api/v1/sessions", headers=bearer(TEACHER_TOKEN))

        guardado = next(s for s in lista.json() if s["id"] == examen["id"])
        assert guardado["access_code"] is None

    def test_al_empezar_el_examen_aparece(self, authed_client: TestClient) -> None:
        """El docente lo necesita justo entonces: es lo que dicta en clase."""
        empezado = crear(authed_client, reveal_code_at_start=True, starts_at=NOW.isoformat())

        assert empezado["access_code"]

    def test_un_examen_ya_empezado_lo_sigue_mostrando(self, authed_client: TestClient) -> None:
        empezado = crear(
            authed_client,
            reveal_code_at_start=True,
            starts_at=(NOW - timedelta(minutes=30)).isoformat(),
        )

        assert empezado["access_code"]


class TestCambiarDeOpinion:
    def test_se_puede_activar_despues_de_crear(self, authed_client: TestClient) -> None:
        examen = crear(authed_client)
        assert examen["access_code"]

        corregido = authed_client.patch(
            f"/api/v1/sessions/{examen['id']}",
            json={"reveal_code_at_start": True},
            headers=bearer(TEACHER_TOKEN),
        )

        assert corregido.status_code == 200, corregido.text
        assert corregido.json()["access_code"] is None

    def test_se_puede_desactivar(self, authed_client: TestClient) -> None:
        examen = crear(authed_client, reveal_code_at_start=True)

        corregido = authed_client.patch(
            f"/api/v1/sessions/{examen['id']}",
            json={"reveal_code_at_start": False},
            headers=bearer(TEACHER_TOKEN),
        )

        assert corregido.json()["access_code"]

    def test_editar_otra_cosa_no_lo_desactiva(self, authed_client: TestClient) -> None:
        """Un PATCH solo cambia lo que trae. Si editar el titulo revelara el
        codigo, la opcion se perderia sin que nadie la tocara."""
        examen = crear(authed_client, reveal_code_at_start=True)

        corregido = authed_client.patch(
            f"/api/v1/sessions/{examen['id']}",
            json={"title": "Otro titulo"},
            headers=bearer(TEACHER_TOKEN),
        )

        assert corregido.json()["reveal_code_at_start"] is True
        assert corregido.json()["access_code"] is None


class TestElCodigoGuardadoSigueSirviendo:
    def test_el_estudiante_entra_con_el(self, authed_client: TestClient) -> None:
        """Guardarlo no lo invalida: el docente lo dicta al empezar y el codigo
        es el mismo de siempre."""
        guardado = crear(authed_client, reveal_code_at_start=True, starts_at=NOW.isoformat())
        codigo = guardado["access_code"]

        entrada = authed_client.post(
            "/api/v1/sessions/join",
            json={"access_code": codigo},
            headers=bearer("token-estudiante"),
        )

        assert entrada.status_code == 200, entrada.text
        assert entrada.json()["session_id"] == guardado["id"]
