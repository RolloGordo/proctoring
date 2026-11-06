"""La portada de un curso: pedir dónde subirla y fijarla o quitarla.

La imagen **no pasa por la API**: la web pide una URL firmada para una ruta
concreta, sube el archivo directo a Storage y después avisa de que esa ruta es
la portada. Es el mismo camino que la evidencia, por la misma razón: la API no
carga con archivos.
"""

from __future__ import annotations

import logging
from uuid import UUID

from proctoring_api.application.course_access import ensure_teacher_owns_course
from proctoring_api.application.course_covers import CourseCovers
from proctoring_api.application.ports.course_repository import CourseRepository
from proctoring_api.application.ports.evidence_storage import SignedUpload
from proctoring_api.application.use_cases.manage_courses import TeacherCourse
from proctoring_api.domain.course import cover_path_for
from proctoring_api.domain.user import AuthenticatedUser

logger = logging.getLogger(__name__)


class RequestCourseCoverUpload:
    """URL firmada para subir la portada de un curso. Solo su docente."""

    def __init__(self, courses: CourseRepository, covers: CourseCovers) -> None:
        self._courses = courses
        self._covers = covers

    def execute(
        self, course_id: UUID, content_type: str, *, actor: AuthenticatedUser | None = None
    ) -> SignedUpload:
        """Raises:
        AuthorizationError: si el curso no es del docente.
        InvalidCourseError: si el formato no es WebP, JPEG o PNG.
        """
        course = ensure_teacher_owns_course(self._courses, course_id, actor)
        path = cover_path_for(course.id, content_type)
        return self._covers.storage.create_upload_url(self._covers.bucket, path, content_type)


class SetCourseCover:
    """Fija la portada de un curso, o la quita con `None`. Solo su docente.

    La imagen anterior se borra del bucket: con el plan gratuito de Supabase el
    espacio es limitado, y una portada reemplazada no la vuelve a pedir nadie.
    """

    def __init__(self, courses: CourseRepository, covers: CourseCovers) -> None:
        self._courses = courses
        self._covers = covers

    def execute(
        self,
        course_id: UUID,
        cover_path: str | None,
        *,
        actor: AuthenticatedUser | None = None,
    ) -> TeacherCourse:
        """Raises:
        AuthorizationError: si el curso no es del docente.
        InvalidCourseError: si la ruta no es una portada de este curso.
        """
        course = ensure_teacher_owns_course(self._courses, course_id, actor)
        updated = course.with_cover(cover_path)
        self._courses.set_cover(course.id, updated.cover_path)

        anterior = course.cover_path
        if anterior and anterior != updated.cover_path:
            # Que no se pueda borrar la imagen vieja no deshace el cambio: el
            # docente ya ve su portada nueva y el archivo huérfano no le cuesta
            # nada. Se deja constancia para poder limpiarlo.
            try:
                self._covers.storage.remove(self._covers.bucket, [anterior])
            except Exception:
                logger.warning("No se pudo borrar la portada anterior %s", anterior, exc_info=True)

        conteo = self._courses.count_enrollments([course.id])
        return TeacherCourse(
            course=updated,
            student_count=conteo.get(course.id, 0),
            cover_url=self._covers.urls([updated]).get(course.id),
        )
