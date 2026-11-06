"""Puerto de almacenamiento de evidencia."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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

    def create_read_url(self, bucket: str, path: str, expires_in_seconds: int) -> str:
        """URL firmada para **leer** un archivo de evidencia.

        Los tres buckets son privados: sin esto, una captura se guarda y nadie
        puede verla. La URL caduca a proposito, para que un enlace copiado de la
        pantalla de revision no se convierta en acceso permanente a la cara de
        un estudiante.
        """
        ...

    def create_read_urls(
        self, bucket: str, paths: Sequence[str], expires_in_seconds: int
    ) -> Mapping[str, str]:
        """URLs firmadas de lectura para varios archivos, en una sola petición.

        Un archivo que ya no existe **no aparece** en el resultado en vez de
        hacer fallar a los demás: quien lo use pinta lo que haya y trata la
        ausencia como «sin imagen».
        """
        ...

    def remove(self, bucket: str, paths: Sequence[str]) -> None:
        """Borra esos archivos del bucket. Borrar uno que no existe no es error."""
        ...
