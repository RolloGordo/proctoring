"""Cursos: el grupo de estudiantes al que un docente toma exámenes.

Un curso agrupa a quienes están matriculados en él y a los exámenes que se les
toman. Que un estudiante esté en un curso **no le da acceso a sus exámenes**: para
rendir uno sigue necesitando el código de acceso y aceptar la supervisión. El
curso le sirve para ver qué exámenes vienen, no para saltarse la entrada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID, uuid4

from proctoring_api.domain.errors import DomainError

MAX_NAME_LENGTH = 120
MAX_SECTION_LENGTH = 40

#: Formatos de portada que se aceptan, con la extensión que lleva el archivo.
#: Son los mismos que admite el bucket `course-covers`: la web convierte la
#: imagen a WebP antes de subirla, y JPEG o PNG quedan para el navegador que no
#: sepa codificar WebP.
COVER_CONTENT_TYPES: dict[str, str] = {
    "image/webp": "webp",
    "image/jpeg": "jpg",
    "image/png": "png",
}


class InvalidCourseError(DomainError):
    """El curso no cumple las reglas del dominio."""


@dataclass(frozen=True, slots=True)
class Course:
    """Un curso de un docente."""

    id: UUID
    teacher_id: UUID
    name: str
    section: str | None
    created_at: datetime
    #: Ruta de la portada dentro del bucket `course-covers`, o `None` si el curso
    #: no tiene imagen y la web pinta la portada de reserva.
    cover_path: str | None = None

    def with_cover(self, cover_path: str | None) -> Course:
        """El mismo curso con otra portada (o sin ella).

        Raises:
            InvalidCourseError: si la ruta no es una portada de **este** curso.
        """
        if cover_path is not None and not is_cover_of(self.id, cover_path):
            raise InvalidCourseError("Esa imagen no es una portada de este curso")
        return replace(self, cover_path=cover_path)

    @classmethod
    def create(
        cls,
        *,
        teacher_id: UUID,
        name: str,
        created_at: datetime,
        section: str | None = None,
        course_id: UUID | None = None,
    ) -> Course:
        """Crea un curso validado.

        Raises:
            InvalidCourseError: si el nombre está vacío o algún campo es demasiado
                largo, o si la fecha no trae zona horaria.
        """
        clean_name = " ".join(name.split())
        if not clean_name:
            raise InvalidCourseError("El curso necesita un nombre")
        if len(clean_name) > MAX_NAME_LENGTH:
            raise InvalidCourseError(f"El nombre supera los {MAX_NAME_LENGTH} caracteres")

        clean_section = " ".join((section or "").split()) or None
        if clean_section is not None and len(clean_section) > MAX_SECTION_LENGTH:
            raise InvalidCourseError(f"La sección supera los {MAX_SECTION_LENGTH} caracteres")

        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise InvalidCourseError("created_at debe traer zona horaria")

        return cls(
            id=course_id if course_id is not None else uuid4(),
            teacher_id=teacher_id,
            name=clean_name,
            section=clean_section,
            created_at=created_at,
        )


@dataclass(frozen=True, slots=True)
class CourseEnrollment:
    """Un estudiante matriculado en un curso."""

    course_id: UUID
    student_id: UUID
    enrolled_at: datetime


def cover_path_for(course_id: UUID, content_type: str, *, object_id: UUID | None = None) -> str:
    """Ruta nueva para la portada de un curso: `<curso>/<aleatorio>.<ext>`.

    Cada subida estrena nombre. Así el navegador nunca muestra la portada vieja
    desde su caché, y una URL firmada de la imagen anterior no sirve para la
    nueva.

    Raises:
        InvalidCourseError: si el formato no es una imagen admitida.
    """
    extension = COVER_CONTENT_TYPES.get(content_type)
    if extension is None:
        raise InvalidCourseError("La portada tiene que ser una imagen WebP, JPEG o PNG")
    return f"{course_id}/{(object_id or uuid4()).hex}.{extension}"


def is_cover_of(course_id: UUID, path: str) -> bool:
    """Si `path` tiene la forma de una portada de ese curso.

    Impide que un docente apunte su curso a la imagen de otro, o a cualquier
    otra ruta del bucket.
    """
    extensions = "|".join(sorted(set(COVER_CONTENT_TYPES.values())))
    return re.fullmatch(rf"{course_id}/[0-9a-f]{{32}}\.(?:{extensions})", path) is not None
