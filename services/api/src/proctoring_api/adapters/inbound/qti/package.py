"""Leer un paquete QTI/SCORM (`.zip`) sin tocar el disco.

`parse_manifest` es puro a propósito: recibe los bytes de cada archivo y nunca
abre nada. Abrir el `.zip` es trabajo de este adaptador, y es donde hay que
tener cuidado: un archivo comprimido es la forma clásica de colar una bomba de
descompresión o una ruta que se escapa del directorio.

Aquí nada se escribe en disco. El contenido se lee en memoria con tope, así que
el peor caso de un paquete hostil es un rechazo, no un servidor sin espacio.
"""

from __future__ import annotations

import zipfile
from io import BytesIO

from proctoring_api.adapters.inbound.qti.importer import ImportResult, parse_manifest, parse_qti

#: Firma de un `.zip`. Es lo que distingue un paquete de un XML suelto.
ZIP_MAGIC = b"PK\x03\x04"

#: El manifiesto siempre se llama así y vive en la raíz del paquete.
MANIFEST_NAME = "imsmanifest.xml"

#: Topes del paquete abierto. `parse_manifest` tiene los suyos sobre lo que se
#: le entrega; estos protegen el paso anterior, que es el que descomprime.
MAX_ENTRIES = 300
MAX_UNCOMPRESSED_BYTES = 20_000_000
#: Un archivo que se expande más de cien veces es una bomba de descompresión.
MAX_COMPRESSION_RATIO = 100


def looks_like_package(data: bytes) -> bool:
    return data.startswith(ZIP_MAGIC)


def parse_package(data: bytes) -> ImportResult:
    """Lee un paquete IMS/SCORM y devuelve sus preguntas.

    Raises:
        ValueError: si no es un zip legible, si no trae `imsmanifest.xml`, o si
            pasa alguno de los topes.
    """
    try:
        archivo = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as error:
        raise ValueError("El paquete no se puede abrir como archivo comprimido") from error

    entradas = [i for i in archivo.infolist() if not i.is_dir()]
    if len(entradas) > MAX_ENTRIES:
        raise ValueError(f"El paquete trae mas de {MAX_ENTRIES} archivos")

    total = sum(i.file_size for i in entradas)
    if total > MAX_UNCOMPRESSED_BYTES:
        raise ValueError(
            f"El paquete descomprimido pasa de {MAX_UNCOMPRESSED_BYTES // 1_000_000} MB"
        )

    comprimido = sum(i.compress_size for i in entradas)
    if comprimido > 0 and total / comprimido > MAX_COMPRESSION_RATIO:
        raise ValueError("El paquete se expande demasiado al descomprimirse")

    contenido: dict[str, bytes] = {}
    manifiesto: bytes | None = None
    for entrada in entradas:
        nombre = entrada.filename
        # Las rutas del zip se normalizan con separador POSIX. Una que se escape
        # del paquete se descarta aqui; `parse_manifest` ademas no la aceptaria.
        if nombre.startswith("/") or "\\" in nombre or ".." in nombre.split("/"):
            continue
        datos = archivo.read(entrada)
        if nombre == MANIFEST_NAME:
            manifiesto = datos
        else:
            contenido[nombre] = datos

    if manifiesto is None:
        raise ValueError(
            f"El paquete no trae {MANIFEST_NAME} en su raiz. "
            "Si exportaste solo las preguntas, sube el XML en vez del .zip"
        )

    return parse_manifest(manifiesto, contenido)


def parse_upload(data: bytes) -> ImportResult:
    """Lee lo que subió el docente, sea un XML suelto o un paquete.

    Es lo que recibe el caso de uso: no tiene que saber cuál de los dos le
    tocó, y el docente no tiene que elegir el formato en la pantalla.
    """
    return parse_package(data) if looks_like_package(data) else parse_qti(data)


__all__ = ["looks_like_package", "parse_package", "parse_upload"]
