"""Ver una evidencia ya guardada.

Los tres buckets son privados, así que hasta ahora una captura se subía y nadie
podía mirarla: el docente veía el evento con su `evidence_path` y ahí se
acababa. Esto devuelve una URL firmada y temporal para ese archivo.

Temporal a propósito. Un enlace copiado de la pantalla de revisión no puede
convertirse en acceso permanente a la cara de un estudiante.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from proctoring_api.application.ports.evidence_storage import EvidenceStorage
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.session_access import ensure_teacher_owns_session
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.evidence import EvidenceKind
from proctoring_api.domain.user import AuthenticatedUser

#: Cuánto vive el enlace. Suficiente para mirar un caso entero sin recargar, y
#: corto para que copiarlo no sirva de gran cosa mañana.
READ_EXPIRY_SECONDS = int(timedelta(minutes=15).total_seconds())


class CreateEvidenceReadUrl:
    """Una URL temporal para ver una captura o escuchar un fragmento."""

    def __init__(
        self,
        storage: EvidenceStorage,
        buckets: dict[EvidenceKind, str],
        sessions: ExamSessionRepository | None = None,
    ) -> None:
        self._storage = storage
        self._buckets = buckets
        self._sessions = sessions

    def execute(
        self,
        session_id: UUID,
        student_id: UUID,
        path: str,
        kind: EvidenceKind,
        *,
        actor: AuthenticatedUser | None = None,
    ) -> str:
        """Devuelve la URL firmada de lectura.

        Raises:
            AuthorizationError: si quien pide no es el docente de ese examen, o
                si la ruta no pertenece a ese estudiante en ese examen.
        """
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo el docente mira la evidencia de un caso")
        ensure_teacher_owns_session(self._sessions, session_id, actor)

        _ensure_path_belongs(path, session_id, student_id)

        return self._storage.create_read_url(self._buckets[kind], path, READ_EXPIRY_SECONDS)


def _ensure_path_belongs(path: str, session_id: UUID, student_id: UUID) -> None:
    """La ruta tiene que ser de ese estudiante en ese examen.

    `build_evidence_path` escribe `{session_id}/{student_id}/{uuid}.{ext}`, así
    que el prefijo dice de quién es el archivo y se puede comprobar sin ir a la
    base de datos.

    Sin esta comprobación, un docente con un examen propio podría pedir la URL
    de **cualquier** ruta del bucket, incluida la de un estudiante de otro
    profesor, con solo cambiar el cuerpo de la petición. La firma la pone el
    servidor con la clave de servicio: aquí no hay otra cosa que impida leerla.
    """
    partes = path.split("/")
    if len(partes) != 3 or partes[0] != str(session_id) or partes[1] != str(student_id):
        raise AuthorizationError("Esa evidencia no es de este caso")

    # Una ruta con `..` no deberia poder existir —la escribe el servidor— pero
    # comprobarlo cuesta una linea y el dia que alguien acepte una ruta de fuera
    # esto ya esta puesto.
    if ".." in partes or not partes[2]:
        raise AuthorizationError("Esa evidencia no es de este caso")


__all__ = ["READ_EXPIRY_SECONDS", "CreateEvidenceReadUrl"]
