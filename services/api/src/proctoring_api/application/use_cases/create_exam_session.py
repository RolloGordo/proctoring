"""Caso de uso: crear una sesion de examen."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from proctoring_api.application.ports.course_repository import CourseRepository
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.exam_session import (
    ExamSession,
    InvalidExamSessionError,
    SupervisionModule,
    SupervisionPreset,
    generate_access_code,
)
from proctoring_api.domain.user import AuthenticatedUser

#: Intentos de generar un codigo de acceso libre antes de rendirse.
#:
#: Con 31 caracteres y 6 posiciones hay unos 900 millones de combinaciones: una
#: colision es practicamente imposible, pero `exam_sessions.access_code` es
#: `unique` en la base y fallar ahi daria un error incomprensible al docente.
MAX_ACCESS_CODE_ATTEMPTS = 10

#: Docente ficticio por defecto cuando la autenticacion esta desactivada.
#:
#: Fijo y no aleatorio para que en desarrollo todas las sesiones pertenezcan al
#: mismo "docente" y el listado funcione. Se puede sustituir por el id de un
#: docente real con la variable DEV_TEACHER_ID, que es lo que permite probar el
#: camino completo contra Supabase antes de que exista el login.
DEFAULT_DEV_TEACHER_ID = UUID("00000000-0000-4000-8000-000000000001")


@dataclass(frozen=True, slots=True)
class CreateExamSessionInput:
    title: str
    starts_at: datetime
    duration_minutes: int
    course_id: UUID | None = None
    description: str | None = None
    entry_tolerance_minutes: int = 10
    preset: SupervisionPreset = SupervisionPreset.STANDARD
    max_attempts: int = 1
    shuffle_questions: bool = True
    shuffle_options: bool = True
    allow_back_navigation: bool = True
    #: Solo se usa con `preset = custom`.
    modules: dict[SupervisionModule, dict[str, Any]] = field(default_factory=dict)


class CreateExamSession:
    """Crea la sesion con un codigo de acceso libre y sus modulos resueltos."""

    def __init__(
        self,
        sessions: ExamSessionRepository,
        dev_teacher_id: UUID = DEFAULT_DEV_TEACHER_ID,
        courses: CourseRepository | None = None,
    ) -> None:
        self._sessions = sessions
        self._dev_teacher_id = dev_teacher_id
        self._courses = courses

    def execute(
        self, data: CreateExamSessionInput, *, actor: AuthenticatedUser | None = None
    ) -> ExamSession:
        """Crea la sesion y devuelve la entidad completa.

        Raises:
            AuthorizationError: si quien pide no es docente.
            InvalidExamSessionError: si los datos violan una regla de dominio.
        """
        teacher_id = self._authorize(actor)
        self._check_course(data.course_id, teacher_id)

        session = ExamSession.create(
            teacher_id=teacher_id,
            title=data.title,
            starts_at=data.starts_at,
            duration_minutes=data.duration_minutes,
            access_code=self._free_access_code(),
            course_id=data.course_id,
            description=data.description,
            entry_tolerance_minutes=data.entry_tolerance_minutes,
            preset=data.preset,
            max_attempts=data.max_attempts,
            shuffle_questions=data.shuffle_questions,
            shuffle_options=data.shuffle_options,
            allow_back_navigation=data.allow_back_navigation,
            modules=data.modules,
        )

        self._sessions.save(session)
        return session

    def _authorize(self, actor: AuthenticatedUser | None) -> UUID:
        if actor is None:
            # Modo sin autenticacion, que solo se permite en local y en pruebas.
            return self._dev_teacher_id

        if not actor.is_teacher:
            raise AuthorizationError("Solo un docente puede crear una sesion de examen")

        return actor.id

    def _check_course(self, course_id: UUID | None, teacher_id: UUID) -> None:
        """Un examen solo se asocia a un curso del propio docente.

        Sin esto, un `course_id` ajeno o inventado llegaba hasta la base y volvia
        como un error de clave foranea, incomprensible para el docente. Peor: con
        un id ajeno valido, el examen quedaba colgado del curso de otro.
        """
        if course_id is None or self._courses is None:
            return

        course = self._courses.find_by_id(course_id)
        if course is None or course.teacher_id != teacher_id:
            raise AuthorizationError("No tienes acceso a ese curso")

    def _free_access_code(self) -> str:
        for _ in range(MAX_ACCESS_CODE_ATTEMPTS):
            code = generate_access_code()
            if not self._sessions.access_code_exists(code):
                return code

        raise InvalidExamSessionError(
            "No se pudo generar un codigo de acceso libre; intentalo de nuevo"
        )
