"""Comprobaciones estructurales de seguridad.

Estas pruebas no verifican una regla concreta: verifican que **no se pueda
olvidar** aplicarla. La diferencia importa, porque el modo de fallo real no es
que alguien escriba mal una comprobación, sino que añada un endpoint y no la
ponga.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

#: Rutas que pueden ser públicas, con el motivo.
#:
#: `/health` lo consultan el healthcheck del contenedor y Render, que no tienen
#: token. La documentación describe la forma de la API, no sus datos.
PUBLICAS = {
    "/health",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/openapi.json",
}


def rutas_de(app: FastAPI) -> list[APIRoute]:
    """Todas las rutas de la aplicacion, incluidas las de los routers incluidos.

    **Hay que recorrer en profundidad.** Desde FastAPI 0.1xx, `include_router` no
    aplana las rutas en `app.routes`: deja un envoltorio por router. Mirar solo el
    primer nivel devolvia una lista **vacia**, y las dos pruebas de abajo pasaban
    sin comprobar nada. Una prueba que no puede fallar es peor que no tenerla,
    porque da confianza.
    """
    encontradas: list[APIRoute] = []
    pendientes: list[object] = list(app.routes)
    while pendientes:
        actual = pendientes.pop()
        if isinstance(actual, APIRoute):
            encontradas.append(actual)
            continue
        router = getattr(actual, "original_router", None)
        if router is not None:
            pendientes.extend(router.routes)
    return encontradas


def _guardianes(ruta: APIRoute) -> set[str]:
    """Las dependencias que protegen una ruta, por nombre."""
    return {d.call.__name__ for d in ruta.dependant.dependencies if d.call}


def test_rutas_de_encuentra_los_endpoints(authed_app: FastAPI) -> None:
    """Protege al propio recorrido: si vuelve a devolver poco, esto falla.

    El numero no es magico; es "muchas mas que las cuatro de la documentacion".
    """
    rutas = rutas_de(authed_app)

    assert len(rutas) > 20, f"Solo se encontraron {len(rutas)} rutas: el recorrido esta roto"
    assert "/api/v1/sessions" in {r.path for r in rutas}


class TestTodoEndpointIdentificaAlActor:
    def test_ninguna_ruta_se_queda_sin_current_user(self, authed_app: FastAPI) -> None:
        """El agujero que esto cierra.

        Si alguien añade un endpoint y olvida pedir `current_user`, el caso de
        uso recibe `actor=None` y **no comprueba nada**: queda abierto a
        cualquiera con la URL. Antes solo lo detectaba la revisión de código.
        """
        sin_actor = []
        for ruta in rutas_de(authed_app):
            if ruta.path in PUBLICAS:
                continue
            if _guardianes(ruta) & {"get_current_user", "verify_internal_token"}:
                continue
            sin_actor.append(f"{sorted(ruta.methods or [])} {ruta.path}")

        assert sin_actor == [], (
            f"Estos endpoints no identifican a quien los llama y quedan abiertos: {sin_actor}"
        )

    def test_los_internos_usan_el_secreto_y_no_un_token_de_usuario(
        self, authed_app: FastAPI
    ) -> None:
        """Los endpoints de `services/ai` se autentican con el secreto compartido.

        El worker no es un usuario: darle una cuenta seria darle permisos sobre
        datos de estudiantes. Y al reves, una ruta interna que pidiera
        `get_current_user` seria inalcanzable para el worker.
        """
        internos = [r for r in rutas_de(authed_app) if r.path.startswith("/api/v1/internal")]

        assert internos, "No se encontro ninguna ruta interna"
        for ruta in internos:
            assert "verify_internal_token" in _guardianes(ruta), (
                f"La ruta interna {ruta.path} no exige el secreto compartido"
            )

    def test_la_lista_de_publicas_no_crece_sin_querer(self, authed_app: FastAPI) -> None:
        # Si alguien añade una ruta pública, que sea una decisión consciente.
        publicas_reales = {
            r.path
            for r in rutas_de(authed_app)
            if not _guardianes(r) & {"get_current_user", "verify_internal_token"}
        }

        assert publicas_reales <= PUBLICAS


class TestSinTokenNadaResponde:
    """Con autenticación activa, ningún endipoint de datos contesta sin token."""

    @pytest.mark.parametrize(
        ("metodo", "ruta"),
        [
            ("get", "/api/v1/sessions"),
            ("post", "/api/v1/sessions"),
            ("get", f"/api/v1/sessions/{uuid4()}"),
            ("get", f"/api/v1/sessions/{uuid4()}/events"),
            ("get", f"/api/v1/sessions/{uuid4()}/alerts"),
            ("get", f"/api/v1/sessions/{uuid4()}/questions"),
            ("post", f"/api/v1/sessions/{uuid4()}/questions"),
            ("get", f"/api/v1/exam/{uuid4()}/questions"),
            ("post", "/api/v1/sessions/join"),
            ("post", "/api/v1/events"),
            ("post", "/api/v1/evidence/upload-url"),
        ],
    )
    def test_responde_401(self, authed_client: TestClient, metodo: str, ruta: str) -> None:
        # Sin cuerpo en GET: enviarlo lo rechaza la capa HTTP antes de llegar
        # a la autenticacion, y la prueba medaria otra cosa.
        respuesta = (
            authed_client.get(ruta)
            if metodo == "get"
            else getattr(authed_client, metodo)(ruta, json={})
        )

        assert respuesta.status_code == 401, (
            f"{metodo.upper()} {ruta} respondio {respuesta.status_code}"
        )


class TestLosMensajesNoFiltranInformacion:
    def test_una_sesion_ajena_y_una_inexistente_responden_igual(
        self, authed_client: TestClient, authed_app: Any
    ) -> None:
        from datetime import timedelta

        from proctoring_api.domain.exam_session import ExamSession

        from tests.conftest import NOW, TEACHER_TOKEN

        ajena = ExamSession.create(
            teacher_id=uuid4(),
            title="Examen de otro docente",
            starts_at=NOW - timedelta(minutes=5),
            duration_minutes=60,
        )
        authed_app.state.session_repository.save(ajena)
        cabeceras = {"Authorization": f"Bearer {TEACHER_TOKEN}"}

        de_otro = authed_client.get(f"/api/v1/sessions/{ajena.id}", headers=cabeceras)
        inexistente = authed_client.get(f"/api/v1/sessions/{uuid4()}", headers=cabeceras)

        # Si se distinguieran, se podrian tantear ids hasta enumerar que examenes
        # existen en el sistema.
        assert de_otro.status_code == inexistente.status_code == 403
        assert de_otro.json() == inexistente.json()

    def test_un_codigo_de_acceso_invalido_no_dice_por_que(self, client: TestClient) -> None:
        primera = client.post("/api/v1/sessions/join", json={"access_code": "AAAAAA"})
        segunda = client.post("/api/v1/sessions/join", json={"access_code": "BBBBBB"})

        assert primera.json() == segunda.json()
        assert "AAAAAA" not in primera.text


class TestLimitesDeEntrada:
    """Un cuerpo sin tope es una forma barata de tumbar el servicio."""

    def test_el_metadata_de_un_evento_tiene_tope(
        self, client: TestClient, contract_example: Any
    ) -> None:
        payload = contract_example("focus_lost")
        payload["metadata"] = {"relleno": "x" * 100_000}

        respuesta = client.post("/api/v1/events", json=payload)

        assert respuesta.status_code == 422

    def test_no_se_pueden_crear_mil_preguntas_de_una(self, client: TestClient) -> None:
        pregunta = {"question_type": "essay", "statement": "¿Por qué?"}

        respuesta = client.post(
            f"/api/v1/sessions/{uuid4()}/questions", json={"questions": [pregunta] * 500}
        )

        assert respuesta.status_code == 422

    def test_el_enunciado_tiene_tope(self, client: TestClient) -> None:
        respuesta = client.post(
            f"/api/v1/sessions/{uuid4()}/questions",
            json={"questions": [{"question_type": "essay", "statement": "x" * 10_000}]},
        )

        assert respuesta.status_code == 422


class TestCors:
    def test_un_comodin_con_credenciales_no_arranca(self) -> None:
        """Dejaria que cualquier sitio hiciera peticiones en nombre del docente."""
        from proctoring_api.config import Settings
        from proctoring_api.main import create_app

        with pytest.raises(ValueError, match="CORS_ORIGINS"):
            create_app(
                Settings(
                    env="local",
                    auth_enabled=False,
                    event_repository="memory",
                    job_queue="memory",
                    cors_origins=["*"],
                )
            )

    def test_una_lista_de_origenes_si(self) -> None:
        from proctoring_api.config import Settings
        from proctoring_api.main import create_app

        app = create_app(
            Settings(
                env="local",
                auth_enabled=False,
                event_repository="memory",
                job_queue="memory",
                cors_origins=["http://localhost:5173", "https://proctoring.vercel.app"],
            )
        )

        assert app is not None
