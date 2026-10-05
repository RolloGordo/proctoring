"""Regla de acceso a un curso: solo su docente."""

from __future__ import annotations

from uuid import UUID

from proctoring_api.application.ports.course_repository import CourseRepository
from proctoring_api.domain.course import Course
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.user import AuthenticatedUser


def ensure_teacher_owns_course(
    courses: CourseRepository,
    course_id: UUID,
    actor: AuthenticatedUser | None,
) -> Course:
    """Devuelve el curso si quien pregunta es su docente.

    Un docente no ve ni modifica los cursos de otro: en ellos hay nombres y
    correos de estudiantes concretos.

    Raises:
        AuthorizationError: si el curso no es suyo **o no existe**. Se responde lo
            mismo en los dos casos a proposito: distinguirlos permitiria averiguar
            que cursos existen.
    """
    course = courses.find_by_id(course_id)
    if course is None:
        raise AuthorizationError("No tienes acceso a este curso")

    # Sin autenticacion (solo en local) no hay a quien comparar.
    if actor is not None and (not actor.is_teacher or course.teacher_id != actor.id):
        raise AuthorizationError("No tienes acceso a este curso")

    return course
