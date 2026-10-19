"""Que una conexion reutilizada y muerta no acabe en un 500 para el docente."""

from __future__ import annotations

import time as _time

import httpx
import pytest

from proctoring_api.adapters.outbound.supabase import http


def _peticion(metodo: str) -> httpx.Request:
    return httpx.Request(metodo, "https://supabase.ejemplo/rest/v1/events")


def test_un_get_se_reintenta_cuando_la_conexion_murio(monkeypatch: pytest.MonkeyPatch) -> None:
    # `RemoteProtocolError: Server disconnected` es una conexion persistente que
    # el otro extremo ya habia cerrado. La siguiente es nueva y funciona.
    monkeypatch.setattr(_time, "sleep", lambda _s: None)
    intentos: list[int] = []

    def falso(self: object, request: httpx.Request) -> httpx.Response:
        intentos.append(len(intentos))
        if len(intentos) == 1:
            raise httpx.RemoteProtocolError("Server disconnected", request=request)
        return httpx.Response(200, json=[], request=request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", falso)

    respuesta = http._TransporteConReintento().handle_request(_peticion("GET"))

    assert respuesta.status_code == 200
    assert len(intentos) == 2


def test_un_post_no_se_repite_nunca(monkeypatch: pytest.MonkeyPatch) -> None:
    # **Lo importante de este arreglo.** Un `Server disconnected` dice que la
    # conexion murio, no si el servidor llego a procesar la peticion. Repetir un
    # POST podria escribir dos veces el mismo evento, y duplicar evidencia
    # delante de un docente que decide sobre una nota es peor que un error.
    monkeypatch.setattr(_time, "sleep", lambda _s: None)
    intentos: list[int] = []

    def falso(self: object, request: httpx.Request) -> httpx.Response:
        intentos.append(len(intentos))
        raise httpx.RemoteProtocolError("Server disconnected", request=request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", falso)

    with pytest.raises(httpx.RemoteProtocolError):
        http._TransporteConReintento().handle_request(_peticion("POST"))

    assert len(intentos) == 1


def test_un_error_de_verdad_no_se_reintenta(monkeypatch: pytest.MonkeyPatch) -> None:
    # Un 500 del servidor es una respuesta, no una conexion rota: repetirlo solo
    # retrasaria el fallo.
    intentos: list[int] = []

    def falso(self: object, request: httpx.Request) -> httpx.Response:
        intentos.append(len(intentos))
        return httpx.Response(500, request=request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", falso)

    assert http._TransporteConReintento().handle_request(_peticion("GET")).status_code == 500
    assert len(intentos) == 1


def test_las_conexiones_ociosas_se_descartan_pronto() -> None:
    # Por defecto httpx las guarda cinco minutos, tiempo de sobra para que el
    # otro extremo las cierre sin avisar.
    with http.cliente_resistente() as cliente:
        assert isinstance(cliente, httpx.Client)
    assert http.KEEPALIVE_SEGUNDOS <= 10
