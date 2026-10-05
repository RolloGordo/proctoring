"""Cursos: crearlos, matricular estudiantes y verlos."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from proctoring_api.application.course_access import ensure_teacher_owns_course
from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.course_repository import CourseRepository
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.ports.profile_repository import ProfileRepository
from proctoring_api.application.use_cases.create_exam_session import DEFAULT_DEV_TEACHER_ID
from proctoring_api.application.use_cases.manage_enrollment import DEFAULT_DEV_STUDENT_ID
from proctoring_api.domain.course import Course
from proctoring_api.domain.errors import AuthorizationError, DomainError
from proctoring_api.domain.exam_session import ExamSession, SessionStatus
from proctoring_api.domain.user import AuthenticatedUser, ProfileSummary, UserRole


class StudentNotFoundError(DomainError):
    """No hay un estudiante con ese correo."""


@dataclass(frozen=True, slots=True)
class TeacherCourse:
    """Un curso con cuantos estudiantes tiene."""

    course: Course
    student_count: int


@dataclass(frozen=True, slots=True)
class CourseMember:
    """Un matriculado, con quien es."""

    student_id: UUID
    enrolled_at: datetime
    #: `None` si la persona ya no tiene perfil. No se omite de la lista: seguiria
    #: matriculada, y esconderla seria mentirle al docente.
    profile: ProfileSummary | None


@dataclass(frozen=True, slots=True)
class EnrollResult:
    member: CourseMember
    already_enrolled: bool


@dataclass(frozen=True, slots=True)
class MyCourse:
    """Una clase del estudiante, con los examenes que le tocan."""

    course: Course
    exams: Sequence[ExamSession]


class CreateCourse:
    """Crea un curso. Solo un docente."""

    def __init__(
        self,
        courses: CourseRepository,
        clock: Clock,
        dev_teacher_id: UUID = DEFAULT_DEV_TEACHER_ID,
    ) -> None:
        self._courses = courses
        self._clock = clock
        self._dev_teacher_id = dev_teacher_id

    def execute(
        self, name: str, section: str | None, *, actor: AuthenticatedUser | None = None
    ) -> Course:
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo un docente puede crear un curso")

        course = Course.create(
            teacher_id=actor.id if actor is not None else self._dev_teacher_id,
            name=name,
            section=section,
            created_at=self._clock.now(),
        )
        self._courses.save(course)
        return course


class ListTeacherCourses:
    """Los cursos del docente que pregunta, con su numero de estudiantes."""

    def __init__(
        self, courses: CourseRepository, dev_teacher_id: UUID = DEFAULT_DEV_TEACHER_ID
    ) -> None:
        self._courses = courses
        self._dev_teacher_id = dev_teacher_id

    def execute(self, *, actor: AuthenticatedUser | None = None) -> Sequence[TeacherCourse]:
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo un docente tiene cursos propios")

        teacher_id = actor.id if actor is not None else self._dev_teacher_id
        cursos = self._courses.list_by_teacher(teacher_id)
        # El id sale del token: no hay forma de pedir los de otro. Y el conteo
        # llega en una consulta para todos, no una por curso.
        conteo = self._courses.count_enrollments([c.id for c in cursos])
        return [TeacherCourse(course=c, student_count=conteo.get(c.id, 0)) for c in cursos]


class GetCourse:
    """Un curso del docente."""

    def __init__(self, courses: CourseRepository) -> None:
        self._courses = courses

    def execute(self, course_id: UUID, *, actor: AuthenticatedUser | None = None) -> TeacherCourse:
        course = ensure_teacher_owns_course(self._courses, course_id, actor)
        conteo = self._courses.count_enrollments([course.id])
        return TeacherCourse(course=course, student_count=conteo.get(course.id, 0))


class EnrollStudentInCourse:
    """Matricula a un estudiante por su correo.

    Es idempotente: matricular dos veces a la misma persona no es un error.
    """

    def __init__(
        self, courses: CourseRepository, profiles: ProfileRepository, clock: Clock
    ) -> None:
        self._courses = courses
        self._profiles = profiles
        self._clock = clock

    def execute(
        self, course_id: UUID, email: str, *, actor: AuthenticatedUser | None = None
    ) -> EnrollResult:
        """Raises:
        AuthorizationError: si el curso no es del docente.
        StudentNotFoundError: si no hay un estudiante con ese correo.
        """
        course = ensure_teacher_owns_course(self._courses, course_id, actor)

        profile = self._profiles.find_by_email(email)
        # Un correo que no existe y uno que es de un docente responden LO MISMO.
        # Distinguirlos le diria a cualquier docente quien tiene cuenta y con que rol.
        if profile is None or profile.role is not UserRole.STUDENT:
            raise StudentNotFoundError(
                "No hay un estudiante con ese correo. Tiene que haberse registrado antes."
            )

        enrolled_at = self._clock.now()
        is_new = self._courses.enroll(course.id, profile.id, enrolled_at)
        return EnrollResult(
            member=CourseMember(student_id=profile.id, enrolled_at=enrolled_at, profile=profile),
            already_enrolled=not is_new,
        )


class ListCourseMembers:
    """Los estudiantes de un curso, con nombre y correo."""

    def __init__(self, courses: CourseRepository, profiles: ProfileRepository) -> None:
        self._courses = courses
        self._profiles = profiles

    def execute(
        self, course_id: UUID, *, actor: AuthenticatedUser | None = None
    ) -> Sequence[CourseMember]:
        course = ensure_teacher_owns_course(self._courses, course_id, actor)
        matriculas = self._courses.list_enrollments(course.id)
        # Nombres de todos en una consulta, no una por fila.
        perfiles = self._profiles.get_summaries([m.student_id for m in matriculas])
        return [
            CourseMember(
                student_id=m.student_id,
                enrolled_at=m.enrolled_at,
                profile=perfiles.get(m.student_id),
            )
            for m in matriculas
        ]


class ListMyCourses:
    """Las clases del estudiante y los examenes que vienen en cada una.

    Estar en un curso **no da acceso a sus examenes**: para rendir uno sigue
    haciendo falta el codigo de acceso. El curso sirve para saber que viene.
    """

    def __init__(
        self,
        courses: CourseRepository,
        sessions: ExamSessionRepository,
        dev_student_id: UUID = DEFAULT_DEV_STUDENT_ID,
    ) -> None:
        self._courses = courses
        self._sessions = sessions
        self._dev_student_id = dev_student_id

    def execute(self, *, actor: AuthenticatedUser | None = None) -> Sequence[MyCourse]:
        if actor is not None and actor.is_teacher:
            raise AuthorizationError("Un docente ve sus cursos desde su propio panel")

        quien = actor.id if actor is not None else self._dev_student_id
        cursos = self._courses.list_by_student(quien)
        if not cursos:
            return []

        sesiones = self._sessions.list_by_courses([c.id for c in cursos])
        por_curso: dict[UUID, list[ExamSession]] = {c.id: [] for c in cursos}
        for sesion in sesiones:
            # Un borrador no es de nadie todavia: el docente aun lo esta armando.
            if sesion.course_id in por_curso and sesion.status is not SessionStatus.DRAFT:
                por_curso[sesion.course_id].append(sesion)

        return [MyCourse(course=c, exams=por_curso[c.id]) for c in cursos]
