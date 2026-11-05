"""Limitación de peticiones.

Dos problemas distintos, y por eso dos límites:

1. **Fuerza bruta sobre `/sessions/join`.** El código de acceso tiene unos 900
   millones de combinaciones, así que adivinarlo no es inmediato — pero sin un
   límite nada frena los intentos ni deja rastro de que ocurrieron.
2. **Agotar el servicio.** La API corre en el plan gratuito de Render. Un cliente
   con un bucle mal escrito, o malintencionado, la tumba para todos los
   estudiantes que estén rindiendo en ese momento.

La implementación es una **ventana deslizante en memoria**. Eso significa que el
límite es *por instancia*: con varias réplicas, cada una cuenta por su lado. Para
este proyecto es suficiente porque solo hay una instancia, y es honesto decirlo:
si algún día hay más, esto tiene que pasar a Redis, que ya está desplegado.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp


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


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Aplica los límites por cliente."""

    def __init__(
        self,
        app: ASGIApp,
        general: Limite = LIMITE_GENERAL,
        estrictas: dict[str, Limite] | None = None,
    ) -> None:
        super().__init__(app)
        self._general = general
        self._estrictas = estrictas if estrictas is not None else dict(RUTAS_ESTRICTAS)
        self._ventana = VentanaDeslizante()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> JSONResponse:
        ruta = request.url.path

        if ruta in RUTAS_LIBRES:
            return await call_next(request)  # type: ignore[return-value]

        limite = self._estrictas.get(ruta)
        if limite is None:
            if request.method in METODOS_LIBRES:
                return await call_next(request)  # type: ignore[return-value]
            limite = self._general

        clave = f"{_identificar(request)}|{ruta if ruta in self._estrictas else '*'}"
        admitida, espera = self._ventana.admite(clave, limite)

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


def _identificar(request: Request) -> str:
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

    return f"ip:{request.client.host if request.client else 'desconocido'}"


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
