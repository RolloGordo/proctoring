"""Puerto de cursos y de la matricula de estudiantes en ellos."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from proctoring_api.domain.course import Course, CourseEnrollment


class CourseRepository(Protocol):
    """Guarda cursos y quien esta matriculado en cada uno."""

    def save(self, course: Course) -> None:
        """Crea el curso."""
        ...

    def find_by_id(self, course_id: UUID) -> Course | None:
        """El curso, o `None` si no existe."""
        ...

    def list_by_teacher(self, teacher_id: UUID) -> Sequence[Course]:
        """Cursos de un docente, del mas reciente al mas antiguo."""
        ...

    def list_by_student(self, student_id: UUID) -> Sequence[Course]:
        """Cursos en los que esta matriculado un estudiante."""
        ...

    def enroll(self, course_id: UUID, student_id: UUID, enrolled_at: datetime) -> bool:
        """Matricula al estudiante. Devuelve `False` si ya lo estaba.

        Es idempotente: matricular dos veces a la misma persona no es un error ni
        crea una segunda fila.
        """
        ...

    def list_enrollments(self, course_id: UUID) -> Sequence[CourseEnrollment]:
        """Los matriculados de un curso, por orden de llegada."""
        ...

    def count_enrollments(self, course_ids: Sequence[UUID]) -> Mapping[UUID, int]:
        """Cuantos estudiantes tiene cada curso, en una sola consulta.

        Los cursos sin nadie no aparecen en el resultado: quien lo use debe
        tratar la ausencia como cero.
        """
        ...
