"""Cliente HTTP hacia Supabase que sobrevive a una conexion reutilizada y muerta.

En produccion aparecieron 500 en `/participants` y `/decisions` con esto:

    httpx.RemoteProtocolError: Server disconnected

No es un fallo nuestro ni de Supabase: es una conexion persistente que el otro
extremo ya habia cerrado y que httpx reutilizo igualmente. Pasa mas en HTTP/2 y
mas aun en un servicio del plan gratuito, que se duerme y corta lo que tuviera
abierto. Al docente le llegaba un error al abrir la revision del caso.

Se reintenta **solo lo idempotente**. Un `Server disconnected` dice que la
conexion murio, no si el servidor llego a procesar la peticion: repetir un GET
no cuesta nada, pero repetir un POST podria escribir dos veces el mismo evento
o la misma decision, y duplicar evidencia delante de un docente que decide
sobre una nota es peor que devolver un error.
"""

from __future__ import annotations

import logging
import time
from typing import Final

import httpx

logger = logging.getLogger(__name__)

#: Metodos que se pueden repetir sin cambiar nada en el otro lado.
METODOS_IDEMPOTENTES: Final = frozenset({"GET", "HEAD", "OPTIONS"})

#: Lo que significa «la conexion murio antes de contestar». No se sabe si la
#: peticion llego: solo se repite lo idempotente.
FALLOS_DE_CONEXION: Final = (httpx.RemoteProtocolError, httpx.ReadError)

#: La conexion **no llego a abrirse**: no salio ni un byte de la peticion, asi
#: que repetirla no puede duplicar nada, tampoco un POST. Es lo que aparecio en
#: la prueba de carga con mil estudiantes (ADR-0011): `ConnectTimeout` contra
#: Supabase y un 500 para quien guardaba su respuesta.
FALLOS_SIN_ENVIAR: Final = (httpx.ConnectError, httpx.ConnectTimeout)

#: Cuanto se espera a que abra la conexion. Antes era el mismo de toda la
#: peticion (20 s): un intento fallido dejaba al estudiante veinte segundos
#: mirando la pantalla antes de reintentar.
CONEXION_SEGUNDOS: Final = 3.0

#: Un reintento basta: si la conexion estaba muerta, la siguiente es nueva.
INTENTOS: Final = 2

#: Cuanto se espera antes de repetir. Corto a proposito: hay alguien mirando una
#: pantalla, no es un trabajo de fondo.
ESPERA_SEGUNDOS: Final = 0.25

#: Cuanto puede quedarse ociosa una conexion antes de descartarla.
#:
#: Por defecto httpx las guarda cinco minutos, tiempo de sobra para que el otro
#: extremo la cierre sin avisar. Con cinco segundos se abre alguna conexion mas
#: y se dejan de heredar conexiones muertas.
KEEPALIVE_SEGUNDOS: Final = 5.0


class _TransporteConReintento(httpx.HTTPTransport):
    """Repite una peticion cuando es seguro hacerlo.

    Siempre, si la conexion no llego a abrirse; solo si es idempotente, si murio
    a mitad de camino.
    """

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        ultimo: Exception | None = None
        for intento in range(1, INTENTOS + 1):
            try:
                return super().handle_request(request)
            except (*FALLOS_SIN_ENVIAR, *FALLOS_DE_CONEXION) as fallo:
                sin_enviar = isinstance(fallo, FALLOS_SIN_ENVIAR)
                if not sin_enviar and request.method not in METODOS_IDEMPOTENTES:
                    raise
                ultimo = fallo
                if intento < INTENTOS:
                    logger.warning(
                        "Conexion con Supabase caida en %s %s; se reintenta: %s",
                        request.method,
                        request.url.path,
                        fallo,
                    )
                    time.sleep(ESPERA_SEGUNDOS)
        assert ultimo is not None
        raise ultimo


#: Conexiones que se guardan abiertas para reutilizar. Tantas como hilos atiende
#: un proceso de la API (40, el valor por defecto de anyio para los endpoints
#: síncronos). Con las 20 de httpx, en la prueba de carga (ADR-0011) la mitad de
#: los hilos abría una conexión nueva en cada consulta; con mil estudiantes eso
#: acabó en `ConnectTimeout` y errores 500. En producción cada conexión nueva
#: es además un saludo TLS por internet hasta Supabase.
CONEXIONES_REUTILIZABLES: Final = 40


def cliente_resistente(timeout_segundos: float = 20.0) -> httpx.Client:
    """El cliente que se le pasa a `create_client` como `httpx_client`."""
    return httpx.Client(
        transport=_TransporteConReintento(),
        timeout=httpx.Timeout(timeout_segundos, connect=CONEXION_SEGUNDOS),
        limits=httpx.Limits(
            max_connections=100,
            max_keepalive_connections=CONEXIONES_REUTILIZABLES,
            keepalive_expiry=KEEPALIVE_SEGUNDOS,
        ),
    )
