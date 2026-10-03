"""Puerto de almacenamiento de evidencia."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SignedUpload:
    """Permiso temporal para subir **un** archivo a **una** ruta concreta."""

    #: Ruta dentro del bucket. Es lo que el cliente pondra en `evidence_path`.
    path: str
    #: URL a la que subir el archivo.
    url: str
    #: Token de subida, cuando el proveedor lo entrega aparte de la URL.
    token: str | None
    #: Validez en segundos.
    expires_in_seconds: int


class EvidenceStorage(Protocol):
    """Genera permisos de subida directa, sin que el archivo pase por la API."""

    def create_upload_url(self, bucket: str, path: str, content_type: str) -> SignedUpload:
        """URL firmada para subir a `path` dentro de `bucket`.

        La firma es para **una ruta concreta**: quien reciba la URL no puede
        subir a otra parte del bucket ni sobrescribir evidencia ajena.
        """
        ...
