"""Un endpoint de salud minimo, para que el worker pueda vivir en un plan gratuito.

El worker consume de una cola y no sirve peticiones, asi que por si mismo no
abre ningun puerto. El problema es que las plataformas gratuitas donde cabe
—Hugging Face Spaces y los Web Services de Render— **esperan un puerto abierto**:
si nadie escucha, dan el contenedor por caido y lo reinician en bucle. Render
ademas solo regala Web Services; los Background Workers se pagan.

Asi que el mismo proceso levanta esto en un hilo aparte. No es un servicio de
IA: es la prueba de vida que la plataforma necesita, y de paso dice algo util
—si la cola responde— en vez de un 200 vacio que no distingue un worker sano de
uno que perdio Redis hace una hora.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

logger = logging.getLogger("salud")

#: El que usan los Spaces de Hugging Face por defecto. Render y otros inyectan
#: `PORT`, asi que el entorno manda.
PUERTO_POR_DEFECTO = 7860


class _Servidor(ThreadingHTTPServer):
    """Como el normal, pero sin reutilizar un puerto que ya tiene alguien.

    `ThreadingHTTPServer` trae `allow_reuse_address = 1`, y en Windows eso no
    significa lo mismo que en Linux: alli deja **apropiarse** de un puerto que
    otro proceso esta escuchando, en vez de fallar. Dos servidores compartiendo
    puerto en silencio es peor que no abrirlo, porque los sondeos de la
    plataforma caen en cualquiera de los dos.

    El motivo habitual para reutilizar —no esperar al TIME_WAIT al reiniciar—
    aqui no aplica: cada reinicio es un contenedor nuevo.
    """

    allow_reuse_address = False


def _handler(estado: Callable[[], dict[str, Any]]) -> type[BaseHTTPRequestHandler]:
    class Salud(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (lo nombra la biblioteca estandar)
            cuerpo = estado()
            datos = json.dumps(cuerpo).encode()
            # 503 cuando la cola no responde: un worker que perdio Redis esta
            # inservible aunque el proceso siga en pie, y la plataforma tiene
            # que poder reiniciarlo.
            self.send_response(200 if cuerpo.get("queue") else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def log_message(self, formato: str, *args: Any) -> None:
            """Silencia el registro por peticion.

            La plataforma sondea cada pocos segundos; dejarlo encendido llena
            los registros y esconde lo unico que importa, que son los trabajos.
            """

    return Salud


def servir_salud(
    estado: Callable[[], dict[str, Any]], puerto: int | None = None
) -> ThreadingHTTPServer | None:
    """Levanta el endpoint en un hilo de fondo y devuelve el servidor.

    Devuelve `None` si el puerto no se puede abrir. **No es un fallo fatal**: el
    trabajo del worker es la cola, y quedarse sin procesar audio porque el
    puerto estaba ocupado seria peor que no tener prueba de vida.
    """
    elegido = puerto if puerto is not None else int(os.environ.get("PORT", PUERTO_POR_DEFECTO))
    try:
        servidor = _Servidor(("0.0.0.0", elegido), _handler(estado))  # noqa: S104
    except OSError as fallo:
        logger.warning("No se pudo abrir el puerto de salud %s: %s", elegido, fallo)
        return None

    hilo = threading.Thread(target=servidor.serve_forever, name="salud", daemon=True)
    hilo.start()
    logger.info("Salud escuchando en el puerto %s", elegido)
    return servidor
