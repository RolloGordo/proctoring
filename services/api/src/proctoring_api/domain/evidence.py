"""Evidencia: capturas y fragmentos de audio.

El cliente **no manda el archivo a la API**. Pide una URL firmada, sube el archivo
**directo a Storage** y despues manda el evento con la ruta. Asi el trafico pesado
no pasa por la API, que es lo que hace viable el presupuesto del proyecto. Ver
[ADR-0004](../../../../docs/adr/0004-deteccion-liviana-cliente-sin-video-continuo.md).
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from proctoring_api.domain.errors import InvalidEventError


class EvidenceKind(StrEnum):
    """Que se va a subir. Determina el bucket y las extensiones aceptadas."""

    #: Captura del canvas al detectar una senal de vision.
    IMAGE = "image"
    #: Fragmento de audio con habla, para el analisis de IA por voz.
    AUDIO = "audio"
    #: Rostro de referencia que se registra una vez, al inicio.
    REFERENCE_FACE = "reference_face"


#: Extensiones permitidas por tipo, con su mime.
#:
#: Tienen que coincidir con `allowed_mime_types` de los buckets, que se definen en
#: la migracion `20261003120200_realtime_and_storage.sql`. Si aqui se acepta algo
#: que el bucket rechaza, el cliente recibe una URL firmada que falla al subir, y
#: el error aparece lejos de su causa.
ALLOWED_EXTENSIONS: dict[EvidenceKind, dict[str, str]] = {
    EvidenceKind.IMAGE: {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    },
    EvidenceKind.AUDIO: {
        "webm": "audio/webm",
        "wav": "audio/wav",
        "ogg": "audio/ogg",
        "mp3": "audio/mpeg",
    },
    EvidenceKind.REFERENCE_FACE: {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    },
}


def content_type_for(kind: EvidenceKind, extension: str) -> str:
    """Mime correspondiente, validando la extension.

    Raises:
        InvalidEventError: si la extension no esta permitida para ese tipo.
    """
    normalised = extension.lower().lstrip(".")
    allowed = ALLOWED_EXTENSIONS[kind]

    if normalised not in allowed:
        raise InvalidEventError(
            f"Extension '{extension}' no permitida para {kind.value}. "
            f"Acepta: {', '.join(sorted(allowed))}"
        )
    return allowed[normalised]


def build_evidence_path(
    session_id: UUID, student_id: UUID, extension: str, name: UUID | None = None
) -> str:
    """Ruta dentro del bucket: `{session_id}/{student_id}/{uuid}.{ext}`.

    La estructura no es decorativa: tener la sesion y el estudiante en el prefijo
    permite borrar toda la evidencia de un examen con un solo prefijo cuando
    corresponda, y hace evidente a quien pertenece cada archivo al auditarlo.

    El nombre es un uuid nuevo, no el del evento: la URL se pide **antes** de que
    el evento exista.
    """
    normalised = extension.lower().lstrip(".")
    return f"{session_id}/{student_id}/{name or uuid4()}.{normalised}"


def path_belongs_to(path: str, *, student_id: UUID, session_id: UUID | None = None) -> bool:
    """¿La ruta es de ese estudiante (y, si se da, de ese examen)?

    Toda ruta que escribe `build_evidence_path` tiene la forma
    `{session_id}/{student_id}/{nombre}`, así que el prefijo dice de quién es el
    archivo sin ir a la base de datos. Es lo que se comprueba antes de firmar
    una URL de lectura o de mandarle una ruta al worker de IA: las rutas llegan
    en el cuerpo de la petición y el cliente puede escribir cualquier cosa.

    Sin `session_id` solo se exige que sea del estudiante: la cara de
    referencia se sube durante un examen, pero vale para todos.
    """
    partes = path.split("/")
    if len(partes) != 3 or ".." in partes or not partes[2]:
        return False
    try:
        UUID(partes[0])
    except ValueError:
        return False
    if partes[1] != str(student_id):
        return False
    return session_id is None or partes[0] == str(session_id)
