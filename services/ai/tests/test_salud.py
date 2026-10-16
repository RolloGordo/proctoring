"""El endpoint de salud del worker (TA-078).

Existe porque el worker no sirve peticiones y las plataformas gratuitas donde
cabe dan por caido un contenedor sin puerto abierto. Estas pruebas levantan el
servidor de verdad en un puerto libre: simularlo no demostraria lo unico que
importa, que es que algo escuche.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request

import pytest

from salud import servir_salud


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def servidor():
    creados = []

    def levantar(estado):
        puerto = puerto_libre()
        servidor = servir_salud(estado, puerto)
        assert servidor is not None
        creados.append(servidor)
        return f"http://127.0.0.1:{puerto}/health"

    yield levantar
    for s in creados:
        s.shutdown()
        s.server_close()


def test_con_la_cola_viva_responde_200(servidor) -> None:
    url = servidor(lambda: {"queue": True, "queues": ["high", "audio"]})

    with urllib.request.urlopen(url, timeout=5) as respuesta:  # noqa: S310
        assert respuesta.status == 200
        assert json.loads(respuesta.read())["queues"] == ["high", "audio"]


def test_sin_cola_responde_503(servidor) -> None:
    # Un worker que perdio Redis esta inservible aunque el proceso siga en pie:
    # contestar 200 ahi haria que la plataforma nunca lo reiniciara.
    url = servidor(lambda: {"queue": False})

    with pytest.raises(urllib.error.HTTPError) as fallo:
        urllib.request.urlopen(url, timeout=5)  # noqa: S310

    assert fallo.value.code == 503


def test_un_puerto_ocupado_no_tumba_el_worker() -> None:
    """Devuelve `None` en vez de reventar.

    El trabajo del worker es la cola: quedarse sin procesar audio porque el
    puerto estaba cogido seria peor que no tener prueba de vida.

    El socket que lo ocupa se ata a `0.0.0.0`, la misma direccion que usa el
    servidor. Atarlo a `127.0.0.1` no chocaba en Windows —son direcciones
    distintas— y la prueba pasaba sin demostrar nada.
    """
    with socket.socket() as ocupado:
        ocupado.bind(("0.0.0.0", 0))  # noqa: S104
        ocupado.listen(1)
        puerto = int(ocupado.getsockname()[1])

        assert servir_salud(lambda: {"queue": True}, puerto) is None
