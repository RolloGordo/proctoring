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
from proctoring_api.domain.evidence import EvidenceKind, path_belongs_to
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

    Sin esta comprobación, un docente con un examen propio podría pedir la URL
    de **cualquier** ruta del bucket, incluida la de un estudiante de otro
    profesor, con solo cambiar el cuerpo de la petición. La firma la pone el
    servidor con la clave de servicio: aquí no hay otra cosa que impida leerla.
    """
    if not path_belongs_to(path, student_id=student_id, session_id=session_id):
        raise AuthorizationError("Esa evidencia no es de este caso")


__all__ = ["READ_EXPIRY_SECONDS", "CreateEvidenceReadUrl"]
