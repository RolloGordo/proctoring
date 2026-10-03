"""URLs firmadas de subida contra Supabase Storage.

Los buckets son **privados** (migracion `20261003120200_realtime_and_storage.sql`),
asi que ni el cliente ni nadie puede escribir en ellos sin una firma. Esta firma
la genera la API con la service role key, y vale para **una ruta concreta**: quien
la reciba no puede subir a otra parte del bucket ni sobrescribir evidencia ajena.
"""

from __future__ import annotations

from typing import Any, cast

from supabase import Client

from proctoring_api.application.ports.evidence_storage import SignedUpload

#: Validez de una URL de subida firmada en Supabase Storage.
UPLOAD_EXPIRY_SECONDS = 7200


class SupabaseEvidenceStorage:
    """Implementacion de `EvidenceStorage` sobre Supabase Storage."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def create_upload_url(self, bucket: str, path: str, content_type: str) -> SignedUpload:
        response = cast(
            "dict[str, Any]",
            self._client.storage.from_(bucket).create_signed_upload_url(path),
        )

        # El SDK ha cambiado estas claves entre versiones; se aceptan las dos
        # formas para que una actualizacion no rompa la subida en silencio.
        url = response.get("signed_url") or response.get("signedUrl") or ""
        token = response.get("token")

        return SignedUpload(
            path=response.get("path") or path,
            url=str(url),
            token=str(token) if token else None,
            expires_in_seconds=UPLOAD_EXPIRY_SECONDS,
        )
