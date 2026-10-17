"""Cursos: el grupo de estudiantes al que un docente toma exámenes.

Un curso agrupa a quienes están matriculados en él y a los exámenes que se les
toman. Que un estudiante esté en un curso **no le da acceso a sus exámenes**: para
rendir uno sigue necesitando el código de acceso y aceptar la supervisión. El
curso le sirve para ver qué exámenes vienen, no para saltarse la entrada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from proctoring_api.domain.errors import DomainError

MAX_NAME_LENGTH = 120
MAX_SECTION_LENGTH = 40


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
