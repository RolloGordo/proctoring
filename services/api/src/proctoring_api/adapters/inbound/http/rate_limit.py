"""Limitación de peticiones.

Dos problemas distintos, y por eso dos límites:

1. **Fuerza bruta sobre `/sessions/join`.** El código de acceso tiene unos 900
   millones de combinaciones, así que adivinarlo no es inmediato — pero sin un
   límite nada frena los intentos ni deja rastro de que ocurrieron.
2. **Agotar el servicio.** La API corre en el plan gratuito de Render. Un cliente
   con un bucle mal escrito, o malintencionado, la tumba para todos los
   estudiantes que estén rindiendo en ese momento.

La implementación es una **ventana deslizante**, con dos almacenes:

- **Redis** (`RATE_LIMIT_BACKEND=redis`), compartido por todas las réplicas. Con
  la API escalada en horizontal detrás de un balanceador es el único que
  funciona: en memoria cada réplica cuenta por su lado, y con cuatro réplicas
  el límite real sería cuatro veces el escrito (ADR-0011).
- **Memoria** (`memory`, el de siempre), para una sola instancia y para pruebas.

Si Redis no responde, se cuenta en la memoria de la réplica en vez de bloquear:
cortar un examen por un tropiezo de Redis sería peor que limitar por réplica un
rato. Se deja constancia en el log para que no pase desapercibido.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Limite:
    """Cuántas peticiones se admiten en cuántos segundos."""

    peticiones: int
    ventana_segundos: int

    @property
    def descripcion(self) -> str:
        return f"{self.peticiones} peticiones cada {self.ventana_segundos} s"


#: Límite general de escritura. Un examen genera eventos de forma continua, así
#: que tiene que ser holgado: 120 por minuto da margen de sobra a un cliente
#: honesto y corta a uno descontrolado.
LIMITE_GENERAL = Limite(peticiones=120, ventana_segundos=60)

#: Límite estricto para el código de acceso. Un estudiante lo teclea una o dos
#: veces; diez intentos por minuto es generoso para un humano y demasiado lento
#: para una fuerza bruta.
LIMITE_CODIGO = Limite(peticiones=10, ventana_segundos=60)

#: Rutas con límite propio, por prefijo.
RUTAS_ESTRICTAS = {"/api/v1/sessions/join": LIMITE_CODIGO}

#: Métodos que no cuentan para el límite general.
#:
#: Las lecturas son baratas y la pantalla en vivo del docente las hace a menudo;
#: limitarlas estorbaría sin proteger gran cosa. Las escrituras son las que
#: cuestan.
METODOS_LIBRES = frozenset({"GET", "HEAD", "OPTIONS"})

#: Rutas que nunca se limitan: el healthcheck del contenedor las consulta cada
#: 15 s y bloquearlo reiniciaría el servicio por error.
RUTAS_LIBRES = frozenset({"/health"})


class VentanaDeslizante:
    """Cuenta peticiones por clave en una ventana de tiempo.

    Guarda las marcas de tiempo y descarta las que salen de la ventana. Es más
    preciso que contar por bloques fijos, que deja pasar el doble del límite
    justo en el cambio de bloque.
    """

    def __init__(self) -> None:
        self._marcas: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def admite(self, clave: str, limite: Limite) -> tuple[bool, int]:
        """Registra un intento y dice si se admite y cuántos segundos esperar."""
        ahora = time.monotonic()
        desde = ahora - limite.ventana_segundos

        with self._lock:
            marcas = self._marcas[clave]
            while marcas and marcas[0] < desde:
                marcas.popleft()

            if len(marcas) >= limite.peticiones:
                espera = int(marcas[0] + limite.ventana_segundos - ahora) + 1
                return False, max(espera, 1)

            marcas.append(ahora)

            # Las claves que se quedan vacías se eliminan: si no, el diccionario
            # crece con cada IP que pasa por el servicio y nunca baja.
            if not marcas:
                del self._marcas[clave]

            return True, 0

    def limpiar(self) -> None:
        """Vacía el contador. Solo para pruebas."""
        with self._lock:
            self._marcas.clear()


Red = ipaddress.IPv4Network | ipaddress.IPv6Network


class Ventana(Protocol):
    """Dónde se cuentan las peticiones: en la memoria de la réplica o en Redis."""

    async def admite(self, clave: str, limite: Limite) -> tuple[bool, int]:
        """Registra un intento y dice si se admite y cuántos segundos esperar."""
        ...


class VentanaEnMemoria:
    """La ventana deslizante en memoria, con la interfaz asíncrona del middleware."""

    def __init__(self, ventana: VentanaDeslizante | None = None) -> None:
        self._ventana = ventana or VentanaDeslizante()

    async def admite(self, clave: str, limite: Limite) -> tuple[bool, int]:
        return self._ventana.admite(clave, limite)


#: La ventana deslizante en Redis, en un solo paso atómico. Usa el reloj de
#: Redis (`TIME`), no el de cada réplica: con relojes distintos, dos réplicas
#: verían ventanas distintas para el mismo cliente.
#:
#: Cada intento admitido es un miembro único del conjunto ordenado, con su
#: instante en milisegundos como puntuación; los que salen de la ventana se
#: borran antes de contar. La clave caduca sola cuando el cliente deja de pedir.
SCRIPT_VENTANA = """
local t = redis.call('TIME')
local ahora = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local ventana = tonumber(ARGV[1])
local limite = tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ahora - ventana)
if redis.call('ZCARD', KEYS[1]) >= limite then
  local primera = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  return {0, math.ceil((tonumber(primera[2]) + ventana - ahora) / 1000)}
end
redis.call('ZADD', KEYS[1], ahora, ARGV[3])
redis.call('PEXPIRE', KEYS[1], ventana)
return {1, 0}
"""


class VentanaRedis:
    """La ventana deslizante compartida por todas las réplicas, en Redis.

    Si Redis falla, cuenta en la memoria de la réplica (ver el docstring del
    módulo) y lo registra una vez por minuto como mucho, para no inundar el log
    justo cuando algo va mal.
    """

    PREFIJO = "rl:"

    def __init__(self, cliente: Any, respaldo: VentanaEnMemoria | None = None) -> None:
        # `redis.asyncio.Redis`. Tipado suelto para que quien solo use la
        # ventana en memoria no tenga que importar redis.
        self._script = cliente.register_script(SCRIPT_VENTANA)
        self._respaldo = respaldo or VentanaEnMemoria()
        self._ultimo_aviso = float("-inf")

    async def admite(self, clave: str, limite: Limite) -> tuple[bool, int]:
        try:
            admitida, espera = await self._script(
                keys=[self.PREFIJO + clave],
                args=[limite.ventana_segundos * 1000, limite.peticiones, uuid.uuid4().hex],
            )
        except Exception:
            ahora = time.monotonic()
            if ahora - self._ultimo_aviso > 60:
                self._ultimo_aviso = ahora
                logger.warning("Redis no responde: el límite se cuenta por réplica", exc_info=True)
            return await self._respaldo.admite(clave, limite)
        if admitida:
            return True, 0
        return False, max(int(espera), 1)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Aplica los límites por cliente."""

    def __init__(
        self,
        app: ASGIApp,
        general: Limite = LIMITE_GENERAL,
        estrictas: dict[str, Limite] | None = None,
        ventana: Ventana | None = None,
        proxies_de_confianza: Iterable[str] = (),
    ) -> None:
        super().__init__(app)
        self._general = general
        self._estrictas = estrictas if estrictas is not None else dict(RUTAS_ESTRICTAS)
        self._ventana: Ventana = ventana or VentanaEnMemoria()
        self._proxies = redes(proxies_de_confianza)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> JSONResponse:
        ruta = request.url.path

        if ruta in RUTAS_LIBRES:
            return await call_next(request)  # type: ignore[return-value]

        limite = self._estrictas.get(ruta)
        if limite is None:
            if request.method in METODOS_LIBRES:
                return await call_next(request)  # type: ignore[return-value]
            limite = self._general

        quien = _identificar(request, self._proxies)
        clave = f"{quien}|{ruta if ruta in self._estrictas else '*'}"
        admitida, espera = await self._ventana.admite(clave, limite)

        if not admitida:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": (
                        f"Demasiadas peticiones. El limite es {limite.descripcion}. "
                        f"Intentalo de nuevo en {espera} s."
                    )
                },
                headers={"Retry-After": str(espera)},
            )

        return await call_next(request)  # type: ignore[return-value]


def redes(proxies: Iterable[str]) -> tuple[Red, ...]:
    """Las redes de los proxies de confianza, a partir de `10.0.0.0/8,127.0.0.1`."""
    return tuple(ipaddress.ip_network(p.strip(), strict=False) for p in proxies if p.strip())


def _ip_del_cliente(request: Request, proxies: tuple[Red, ...]) -> str:
    """La IP de quien pide, también detrás de un balanceador.

    Detrás de nginx o del proxy de Render, `request.client` es el proxy, y todos
    los anónimos caerían en la misma ventana. Pero `X-Forwarded-For` lo puede
    escribir cualquiera: solo se le cree si la petición viene de un proxy de
    confianza, y se toma la última IP que **no** es de confianza (la que añadió
    nuestro propio proxy), no la primera, que es la que el cliente puede inventar.
    """
    directa = request.client.host if request.client else "desconocido"
    if not proxies or not _es_de(directa, proxies):
        return directa
    cadena = [ip.strip() for ip in request.headers.get("X-Forwarded-For", "").split(",")]
    for ip in reversed([ip for ip in cadena if ip]):
        if not _es_de(ip, proxies):
            return ip
    return directa


def _es_de(ip: str, redes_: tuple[Red, ...]) -> bool:
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(direccion in red for red in redes_)


def _identificar(request: Request, proxies: tuple[Red, ...] = ()) -> str:
    """Identifica al cliente.

    Se prefiere la persona sobre la IP: detrás de la red de una universidad todos
    los estudiantes comparten IP de salida, y limitar por IP los castigaría a
    todos por culpa de uno.

    **La persona es el `sub` del token, no el token.** Antes la clave eran los
    últimos 32 caracteres del Bearer, sin mirarlo (SEC-05): mandar un token
    basura distinto en cada petición daba una ventana nueva cada vez, y quien
    tenía cuenta podía renovar la sesión para estrenar token y saltarse los
    diez intentos por minuto del código de acceso. El `sub` es el mismo en todos
    los tokens de una persona, así que renovar ya no sirve.

    El token no se verifica aquí (eso lo hace la autenticación, después): un
    token sin `sub` legible cuenta como anónimo y cae en la ventana de su IP,
    que comparte con toda la basura que llegue por ahí.
    """
    autorizacion = request.headers.get("Authorization", "")
    if autorizacion.startswith("Bearer "):
        sujeto = _sujeto(autorizacion[7:])
        if sujeto is not None:
            return f"u:{sujeto}"

    return f"ip:{_ip_del_cliente(request, proxies)}"


def _sujeto(token: str) -> str | None:
    """El `sub` de un JWT, leído sin verificar la firma; `None` si no se puede."""
    partes = token.split(".")
    if len(partes) != 3:
        return None
    carga = partes[1] + "=" * (-len(partes[1]) % 4)
    try:
        datos = json.loads(base64.urlsafe_b64decode(carga))
    except (ValueError, TypeError):
        return None
    sujeto = datos.get("sub") if isinstance(datos, dict) else None
    if not isinstance(sujeto, str) or not 0 < len(sujeto) <= 64:
        return None
    return sujeto
