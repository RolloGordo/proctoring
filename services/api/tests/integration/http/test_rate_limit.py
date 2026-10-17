"""Limitación de peticiones.

Las pruebas usan una app propia con el límite **activado**: el resto de la suite
corre con él desactivado, porque hace decenas de peticiones seguidas desde el
mismo cliente y chocaría con el límite sin estar probando nada de eso.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from proctoring_api.adapters.inbound.http.rate_limit import Limite
from proctoring_api.config import Settings
from proctoring_api.main import create_app

from tests.conftest import NOW, FixedClock

pytestmark = pytest.mark.integration


def app_limitada(general: Limite, estrictas: dict[str, Limite] | None = None) -> TestClient:
    app = create_app(
        Settings(
            env="test",
            auth_enabled=False,
            event_repository="memory",
            job_queue="memory",
            rate_limit_enabled=False,  # se añade a mano para controlar los límites
        ),
        clock=FixedClock(NOW),
    )
    from proctoring_api.adapters.inbound.http.rate_limit import RateLimitMiddleware

    app.add_middleware(RateLimitMiddleware, general=general, estrictas=estrictas or {})
    return TestClient(app)


@pytest.fixture
def cliente() -> Iterator[TestClient]:
    with app_limitada(Limite(peticiones=3, ventana_segundos=60)) as c:
        yield c


class TestLimiteGeneral:
    def test_corta_al_pasarse(self, cliente: TestClient) -> None:
        cuerpo = {"title": "Examen", "starts_at": "2026-10-03T10:00:00Z", "duration_minutes": 60}

        codigos = [cliente.post("/api/v1/sessions", json=cuerpo).status_code for _ in range(5)]

        assert codigos[:3] == [201, 201, 201]
        assert codigos[3:] == [429, 429]

    def test_el_429_dice_cuanto_esperar(self, cliente: TestClient) -> None:
        cuerpo = {"title": "Examen", "starts_at": "2026-10-03T10:00:00Z", "duration_minutes": 60}
        for _ in range(3):
            cliente.post("/api/v1/sessions", json=cuerpo)

        respuesta = cliente.post("/api/v1/sessions", json=cuerpo)

        assert respuesta.status_code == 429
        assert "Retry-After" in respuesta.headers
        assert int(respuesta.headers["Retry-After"]) > 0
        assert "Demasiadas peticiones" in respuesta.json()["detail"]

    def test_las_lecturas_no_cuentan(self, cliente: TestClient) -> None:
        # La pantalla en vivo del docente lee a menudo; limitarla estorbaria sin
        # proteger gran cosa, porque lo que cuesta son las escrituras.
        codigos = [cliente.get("/api/v1/sessions").status_code for _ in range(10)]

        assert all(c == 200 for c in codigos)

    def test_el_healthcheck_nunca_se_limita(self, cliente: TestClient) -> None:
        # El contenedor lo consulta cada 15 s; bloquearlo reiniciaria el servicio.
        assert all(cliente.get("/health").status_code == 200 for _ in range(20))


class TestLimiteDelCodigoDeAcceso:
    """La fuerza bruta sobre el codigo de acceso es el riesgo concreto."""

    def test_tiene_su_propio_limite_mas_estricto(self) -> None:
        with app_limitada(
            Limite(peticiones=100, ventana_segundos=60),
            {"/api/v1/sessions/join": Limite(peticiones=2, ventana_segundos=60)},
        ) as cliente:
            codigos = [
                cliente.post("/api/v1/sessions/join", json={"access_code": "ZZZZZZ"}).status_code
                for _ in range(4)
            ]

        # Los dos primeros fallan por codigo inexistente (400), no por limite.
        assert codigos[:2] == [400, 400]
        assert codigos[2:] == [429, 429]

    def test_el_limite_general_no_tapa_al_estricto(self) -> None:
        # Con un general holgado, el estricto tiene que seguir cortando.
        with app_limitada(
            Limite(peticiones=1000, ventana_segundos=60),
            {"/api/v1/sessions/join": Limite(peticiones=1, ventana_segundos=60)},
        ) as cliente:
            cliente.post("/api/v1/sessions/join", json={"access_code": "AAAAAA"})
            segunda = cliente.post("/api/v1/sessions/join", json={"access_code": "BBBBBB"})

        assert segunda.status_code == 429


class TestIdentificacionDelCliente:
    def test_dos_tokens_distintos_no_comparten_cupo(self) -> None:
        """Detrás de la red de una universidad todos comparten IP de salida.

        Limitar por IP castigaría a todos los estudiantes por culpa de uno.
        """
        cuerpo = {"title": "Examen", "starts_at": "2026-10-03T10:00:00Z", "duration_minutes": 60}
        with app_limitada(Limite(peticiones=2, ventana_segundos=60)) as cliente:
            ana = {"Authorization": "Bearer " + "a" * 40}
            luis = {"Authorization": "Bearer " + "b" * 40}

            for _ in range(2):
                cliente.post("/api/v1/sessions", json=cuerpo, headers=ana)

            de_ana = cliente.post("/api/v1/sessions", json=cuerpo, headers=ana)
            de_luis = cliente.post("/api/v1/sessions", json=cuerpo, headers=luis)

        assert de_ana.status_code == 429
        assert de_luis.status_code == 201


class TestVentanaDeslizante:
    def test_cuenta_por_ventana_y_no_por_bloques(self) -> None:
        """Contar por bloques fijos deja pasar el doble en el cambio de bloque."""
        from proctoring_api.adapters.inbound.http.rate_limit import VentanaDeslizante

        ventana = VentanaDeslizante()
        limite = Limite(peticiones=2, ventana_segundos=60)

        assert ventana.admite("x", limite)[0] is True
        assert ventana.admite("x", limite)[0] is True
        admitida, espera = ventana.admite("x", limite)

        assert admitida is False
        assert 0 < espera <= 61

    def test_claves_distintas_no_se_estorban(self) -> None:
        from proctoring_api.adapters.inbound.http.rate_limit import VentanaDeslizante

        ventana = VentanaDeslizante()
        limite = Limite(peticiones=1, ventana_segundos=60)

        assert ventana.admite("a", limite)[0] is True
        assert ventana.admite("b", limite)[0] is True
        assert ventana.admite("a", limite)[0] is False


def test_el_limite_viene_activado_por_defecto() -> None:
    # Si la variable falta en un despliegue, se protege.
    assert Settings(_env_file=None).rate_limit_enabled is True  # type: ignore[call-arg]
