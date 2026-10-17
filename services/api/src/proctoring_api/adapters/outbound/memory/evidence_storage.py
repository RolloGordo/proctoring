"""Almacenamiento de evidencia de mentira, para desarrollo y pruebas.

Devuelve una URL con forma correcta pero que **no acepta subidas**. Sirve para
que Rider y Jesus puedan desarrollar el flujo (pedir la URL, construir el
`evidence_path`, mandar el evento) sin credenciales de Supabase.
"""

from __future__ import annotations

import threading

from proctoring_api.application.ports.evidence_storage import SignedUpload

#: Validez que se finge. La de Supabase es de 2 horas para las subidas firmadas.
FAKE_EXPIRY_SECONDS = 7200


class InMemoryEvidenceStorage:
    """Implementacion de `EvidenceStorage` que no sube nada a ningun sitio."""

    def __init__(self, base_url: str = "http://localhost:8000/__fake-storage") -> None:
        self._base_url = base_url.rstrip("/")
        self._issued: list[tuple[str, str]] = []
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

    @property
    def issued(self) -> list[tuple[str, str]]:
        """Permisos entregados, como (bucket, path). Solo para pruebas."""
        with self._lock:
            return list(self._issued)
