"""Caso de uso: crear una sesion de examen."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

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

#: Docente ficticio que se usa cuando la autenticacion esta desactivada.
#:
#: Es fijo y no aleatorio para que en desarrollo todas las sesiones pertenezcan
#: al mismo "docente" y el listado funcione. Con `EVENT_REPOSITORY=supabase` este
#: id no existe en `profiles` y el insert falla por la clave foranea, que es el
#: aviso correcto: contra la base de verdad hay que autenticarse.
DEV_TEACHER_ID = UUID("00000000-0000-4000-8000-000000000001")


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

    def __init__(self, sessions: ExamSessionRepository) -> None:
        self._sessions = sessions

    def execute(
        self, data: CreateExamSessionInput, *, actor: AuthenticatedUser | None = None
    ) -> ExamSession:
        """Crea la sesion y devuelve la entidad completa.

        Raises:
            AuthorizationError: si quien pide no es docente.
            InvalidExamSessionError: si los datos violan una regla de dominio.
        """
        teacher_id = self._authorize(actor)

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
            return DEV_TEACHER_ID

        if not actor.is_teacher:
            raise AuthorizationError("Solo un docente puede crear una sesion de examen")

        return actor.id

    def _free_access_code(self) -> str:
        for _ in range(MAX_ACCESS_CODE_ATTEMPTS):
            code = generate_access_code()
            if not self._sessions.access_code_exists(code):
                return code

        raise InvalidExamSessionError(
            "No se pudo generar un codigo de acceso libre; intentalo de nuevo"
        )
