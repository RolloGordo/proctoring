"""El límite compartido entre réplicas (ADR-0011) y la IP real detrás del balanceador.

La ventana de Redis se prueba con el script Lua de verdad, sobre fakeredis: lo
que importa es que dos réplicas que hablan con el mismo Redis cuenten juntas.
"""

from __future__ import annotations

import asyncio
from typing import Any

import fakeredis
import pytest
from starlette.requests import Request

from proctoring_api.adapters.inbound.http.rate_limit import (
    Limite,
    VentanaRedis,
    _identificar,
    redes,
)

LIMITE = Limite(peticiones=3, ventana_segundos=60)


def correr(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture
def servidor() -> fakeredis.FakeServer:
    return fakeredis.FakeServer()


def replica(servidor: fakeredis.FakeServer) -> VentanaRedis:
    """Una réplica de la API: su propio cliente, el mismo Redis."""
    return VentanaRedis(fakeredis.FakeAsyncRedis(server=servidor))


class TestVentanaRedis:
    def test_admite_hasta_el_limite_y_dice_cuanto_esperar(
        self, servidor: fakeredis.FakeServer
    ) -> None:
        async def probar() -> list[tuple[bool, int]]:
            ventana = replica(servidor)
            return [await ventana.admite("u:ana|*", LIMITE) for _ in range(4)]

        resultados = correr(probar())

        assert [admitida for admitida, _ in resultados] == [True, True, True, False]
        assert 1 <= resultados[-1][1] <= 60

    def test_dos_replicas_cuentan_juntas(self, servidor: fakeredis.FakeServer) -> None:
        """El motivo de todo esto: con la ventana en memoria, cada una dejaría pasar 3."""

        async def probar() -> list[bool]:
            a, b = replica(servidor), replica(servidor)
            orden = [a, b, a, b, a, b]
            return [(await r.admite("u:ana|*", LIMITE))[0] for r in orden]

        assert correr(probar()) == [True, True, True, False, False, False]

    def test_cada_persona_tiene_su_ventana(self, servidor: fakeredis.FakeServer) -> None:
        async def probar() -> tuple[bool, bool]:
            ventana = replica(servidor)
            for _ in range(3):
                await ventana.admite("u:ana|*", LIMITE)
            return (
                (await ventana.admite("u:ana|*", LIMITE))[0],
                (await ventana.admite("u:luis|*", LIMITE))[0],
            )

        assert correr(probar()) == (False, True)

    def test_la_clave_caduca_sola(self, servidor: fakeredis.FakeServer) -> None:
        async def probar() -> int:
            cliente = fakeredis.FakeAsyncRedis(server=servidor)
            await VentanaRedis(cliente).admite("u:ana|*", LIMITE)
            ttl: int = await cliente.pttl("rl:u:ana|*")
            return ttl

        assert 0 < correr(probar()) <= 60_000

    def test_si_redis_cae_cuenta_en_la_replica_sin_bloquear(self) -> None:
        class RedisCaido:
            def register_script(self, _script: str) -> Any:
                async def falla(**_kw: Any) -> Any:
                    raise ConnectionError("Redis no responde")

                return falla

        async def probar() -> list[bool]:
            ventana = VentanaRedis(RedisCaido())
            return [(await ventana.admite("u:ana|*", LIMITE))[0] for _ in range(4)]

        # Sigue limitando (en memoria), pero no deja a nadie sin examen.
        assert correr(probar()) == [True, True, True, False]


def peticion(cliente: str, cabeceras: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (cabeceras or {}).items()],
        "client": (cliente, 12345),
    }
    return Request(scope)


class TestIpDetrasDelBalanceador:
    BALANCEADOR = redes(["172.16.0.0/12"])

    def test_sin_proxies_de_confianza_no_se_cree_la_cabecera(self) -> None:
        req = peticion("172.18.0.5", {"X-Forwarded-For": "1.2.3.4"})

        assert _identificar(req) == "ip:172.18.0.5"

    def test_detras_del_balanceador_se_usa_la_ip_que_el_anadio(self) -> None:
        req = peticion("172.18.0.5", {"X-Forwarded-For": "200.48.10.7"})

        assert _identificar(req, self.BALANCEADOR) == "ip:200.48.10.7"

    def test_no_se_puede_inventar_la_ip(self) -> None:
        """El cliente pone una IP falsa delante; nginx añade la real al final."""
        req = peticion("172.18.0.5", {"X-Forwarded-For": "9.9.9.9, 200.48.10.7"})

        assert _identificar(req, self.BALANCEADOR) == "ip:200.48.10.7"

    def test_quien_no_es_el_balanceador_no_puede_usar_la_cabecera(self) -> None:
        req = peticion("200.48.10.7", {"X-Forwarded-For": "9.9.9.9"})

        assert _identificar(req, self.BALANCEADOR) == "ip:200.48.10.7"

    def test_con_token_manda_la_persona_no_la_ip(self) -> None:
        # Un JWT con sub "ana" (sin firma: aquí no se verifica, solo se lee).
        token = "e30.eyJzdWIiOiJhbmEifQ.firma"
        req = peticion(
            "172.18.0.5",
            {"X-Forwarded-For": "200.48.10.7", "Authorization": f"Bearer {token}"},
        )

        assert _identificar(req, self.BALANCEADOR) == "u:ana"
