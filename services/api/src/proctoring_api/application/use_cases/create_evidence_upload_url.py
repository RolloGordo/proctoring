"""Caso de uso: pedir permiso para subir evidencia."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from proctoring_api.application.ports.evidence_storage import EvidenceStorage, SignedUpload
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.evidence import (
    EvidenceKind,
    build_evidence_path,
    content_type_for,
)
from proctoring_api.domain.user import AuthenticatedUser


@dataclass(frozen=True, slots=True)
class EvidenceUploadRequest:
    session_id: UUID
    student_id: UUID
    kind: EvidenceKind
    extension: str


class CreateEvidenceUploadUrl:
    """Entrega una URL firmada para que el cliente suba directo a Storage.

    La API nunca recibe el archivo. Si lo recibiera, cada captura y cada
    fragmento de audio pasaria por el plan gratuito de Render, que es justo el
    coste que ADR-0004 evita.
    """

    def __init__(self, storage: EvidenceStorage, buckets: dict[EvidenceKind, str]) -> None:
        self._storage = storage
        self._buckets = buckets

    def execute(
        self, request: EvidenceUploadRequest, *, actor: AuthenticatedUser | None = None
    ) -> SignedUpload:
        """Crea el permiso de subida.

        Raises:
            AuthorizationError: si el actor no puede subir evidencia de ese
                estudiante.
            InvalidEventError: si la extension no esta permitida para ese tipo.
        """
        if actor is not None:
            self._authorize(request, actor)

        # Valida la extension antes de construir nada: una URL firmada para un
        # tipo que el bucket rechaza haria fallar la subida lejos de su causa.
        content_type = content_type_for(request.kind, request.extension)

        path = build_evidence_path(request.session_id, request.student_id, request.extension)
        return self._storage.create_upload_url(self._buckets[request.kind], path, content_type)

    @staticmethod
    def _authorize(request: EvidenceUploadRequest, actor: AuthenticatedUser) -> None:
        """Solo el propio estudiante sube evidencia sobre si mismo.

        Sin esto, cualquiera con un token valido conseguiria permiso de escritura
        en la carpeta de otro estudiante y podria plantar una captura falsa que
        termina delante de un docente.
        """
        if actor.is_teacher:
            raise AuthorizationError(
                "Un docente no sube evidencia: la genera el cliente del estudiante"
            )

        if actor.id != request.student_id:
            raise AuthorizationError("No puedes subir evidencia a nombre de otro estudiante")
