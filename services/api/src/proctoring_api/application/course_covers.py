"""Las portadas de los cursos: dónde viven y cómo se leen."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from proctoring_api.application.ports.evidence_storage import EvidenceStorage
from proctoring_api.domain.course import Course

#: Una hora. El bucket es privado, así que la portada se ve con una URL firmada.
#: Dura lo bastante para una sesión de trabajo y, si alguien copia el enlace,
#: deja de servir el mismo día.
COVER_READ_SECONDS = 3600


class CourseCovers:
    """Firma las URLs de lectura de las portadas, todas en una sola petición."""

    def __init__(
        self,
        storage: EvidenceStorage,
        bucket: str,
        expires_in_seconds: int = COVER_READ_SECONDS,
    ) -> None:
        self.storage = storage
        self.bucket = bucket
        self._expires_in_seconds = expires_in_seconds

    def urls(self, courses: Sequence[Course]) -> Mapping[UUID, str]:
        """La URL de la portada de cada curso que tiene una.

        Un curso sin portada, o cuya imagen ya no está en el bucket, no aparece:
        la web pinta su portada de reserva.
        """
        rutas = {c.cover_path: c.id for c in courses if c.cover_path}
        if not rutas:
            return {}
        firmadas = self.storage.create_read_urls(self.bucket, list(rutas), self._expires_in_seconds)
        return {rutas[ruta]: url for ruta, url in firmadas.items() if ruta in rutas}
