"""Que un servicio dormido no cuente como un trabajo roto."""

from __future__ import annotations

import httpx
import pytest

import tasks


@pytest.fixture(autouse=True)
def _sin_esperas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las esperas de verdad suman minuto y medio; aqui no se duerme."""
    monkeypatch.setattr(tasks.time, "sleep", lambda _segundos: None)


def _respuesta(codigo: int, cuerpo: dict[str, object] | None = None) -> httpx.Response:
    return httpx.Response(
        codigo,
        json=cuerpo if cuerpo is not None else {"ok": True},
        request=httpx.Request("GET", "https://api.ejemplo/x"),
    )


def test_un_502_se_reintenta_hasta_que_la_api_despierta() -> None:
    # **El fallo que dejaba sin verificacion facial a cada estudiante.** El plan
    # gratuito duerme la API; despertarla pasa del minuto y durante ese rato
    # Render devuelve 502. El reintento de RQ es `Retry(max=3)` sin intervalo,
    # asi que los tres intentos se gastaban en milisegundos y el trabajo moria.
    intentos: list[int] = []

    def hacer() -> httpx.Response:
        intentos.append(len(intentos))
        return _respuesta(502) if len(intentos) < 3 else _respuesta(200, {"verified": True})

    assert tasks._con_reintentos(hacer, "GET /x") == {"verified": True}
    assert len(intentos) == 3


def test_tambien_se_reintenta_si_no_hay_a_quien_conectarse() -> None:
    # Mientras el contenedor arranca no hay nadie escuchando: eso no es un 502,
    # es un fallo de conexion, y significa exactamente lo mismo.
    intentos: list[int] = []

    def hacer() -> httpx.Response:
        intentos.append(len(intentos))
        if len(intentos) == 1:
            raise httpx.ConnectError("conexion rechazada")
        return _respuesta(200)

    assert tasks._con_reintentos(hacer, "GET /x") == {"ok": True}
    assert len(intentos) == 2


def test_un_error_de_verdad_no_se_reintenta() -> None:
    # Un 401 o un 422 daria igual para siempre. Insistir solo retrasa el fallo
    # y gasta minuto y medio por trabajo.
    intentos: list[int] = []

    def hacer() -> httpx.Response:
        intentos.append(len(intentos))
        return _respuesta(401)

    with pytest.raises(httpx.HTTPStatusError):
        tasks._con_reintentos(hacer, "GET /x")
    assert len(intentos) == 1


def test_si_nunca_despierta_acaba_lanzando() -> None:
    # No se traga el fallo: si la API no vuelve, el trabajo tiene que constar
    # como fallido en vez de dar por buena una verificacion que no ocurrio.
    intentos: list[int] = []

    def hacer() -> httpx.Response:
        intentos.append(len(intentos))
        return _respuesta(503)

    with pytest.raises(httpx.HTTPStatusError):
        tasks._con_reintentos(hacer, "GET /x")
    assert len(intentos) == len(tasks.ESPERAS_REINTENTO) + 1
