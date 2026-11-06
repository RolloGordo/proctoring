"""Almacenamiento de evidencia de mentira, para desarrollo y pruebas.

Devuelve una URL con forma correcta pero que **no acepta subidas**. Sirve para
que Rider y Jesus puedan desarrollar el flujo (pedir la URL, construir el
`evidence_path`, mandar el evento) sin credenciales de Supabase.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence

from proctoring_api.application.ports.evidence_storage import SignedUpload

#: Validez que se finge. La de Supabase es de 2 horas para las subidas firmadas.
FAKE_EXPIRY_SECONDS = 7200


class InMemoryEvidenceStorage:
    """Implementacion de `EvidenceStorage` que no sube nada a ningun sitio."""

    def __init__(self, base_url: str = "http://localhost:8000/__fake-storage") -> None:
        self._base_url = base_url.rstrip("/")
        self._issued: list[tuple[str, str]] = []
        #: Archivos borrados, como (bucket, path). Lo que se borre deja de tener
        #: URL de lectura, igual que en Storage.
        self._removed: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def create_upload_url(self, bucket: str, path: str, content_type: str) -> SignedUpload:
        with self._lock:
            self._issued.append((bucket, path))

        return SignedUpload(
            path=path,
            url=f"{self._base_url}/{bucket}/{path}",
            token=None,
            expires_in_seconds=FAKE_EXPIRY_SECONDS,
        )

    def create_read_url(self, bucket: str, path: str, expires_in_seconds: int) -> str:
        self._issued.append((bucket, path))
        return f"{self._base_url}/{bucket}/{path}?leer={expires_in_seconds}"

    def create_read_urls(
        self, bucket: str, paths: Sequence[str], expires_in_seconds: int
    ) -> Mapping[str, str]:
        with self._lock:
            vivos = [p for p in paths if (bucket, p) not in self._removed]
        return {p: self.create_read_url(bucket, p, expires_in_seconds) for p in vivos}

    def remove(self, bucket: str, paths: Sequence[str]) -> None:
        with self._lock:
            self._removed.update((bucket, p) for p in paths)

    @property
    def removed(self) -> set[tuple[str, str]]:
        """Archivos borrados, como (bucket, path). Solo para pruebas."""
        with self._lock:
            return set(self._removed)

    @property
    def issued(self) -> list[tuple[str, str]]:
        """Permisos entregados, como (bucket, path). Solo para pruebas."""
        with self._lock:
            return list(self._issued)
