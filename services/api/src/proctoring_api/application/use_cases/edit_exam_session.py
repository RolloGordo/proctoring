"""Corregir, cancelar y borrar un examen.

Faltaba lo más básico: un docente que se equivocaba al crear un examen no podía
deshacerlo. Las tres operaciones viven juntas porque comparten la pregunta que
decide qué se puede hacer: **si alguien ya entró**.

- Nadie ha entrado todavía → se puede cambiar todo, y se puede borrar de verdad.
- Alguien ya entró → se cancela, no se borra, y hay campos que se congelan.

Borrar un examen con participantes se llevaría por delante sus eventos, alertas
y respuestas, que son justamente la evidencia que este sistema existe para
conservar. Por eso cancelar no es un borrado disimulado: es la operación
correcta, y el estudiante que llega con su código recibe una explicación en vez
de un error.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.course_repository import CourseRepository
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.ports.participant_repository import ParticipantRepository
from proctoring_api.application.session_access import ensure_teacher_owns_session
from proctoring_api.domain.errors import AuthorizationError, DomainError
from proctoring_api.domain.exam_session import (
    ExamSession,
    InvalidExamSessionError,
    SupervisionPreset,
)
from proctoring_api.domain.user import AuthenticatedUser


class ExamInUseError(DomainError):
    """Se intentó algo que ya no se puede porque el examen está en marcha."""


@dataclass(frozen=True, slots=True)
class ExamSessionChanges:
    """Lo que el docente quiere cambiar.

    `None` significa "no lo toques". Para *vaciar* un campo opcional están los
    `clear_*`: sin ellos no habría forma de quitarle la descripción a un examen
    que ya la tiene, porque `None` ya significa otra cosa.
    """

    title: str | None = None
    starts_at: datetime | None = None
    duration_minutes: int | None = None
    entry_tolerance_minutes: int | None = None
    description: str | None = None
    course_id: UUID | None = None
    preset: SupervisionPreset | None = None
    max_score: Decimal | None = None
    question_pool_size: int | None = None
    shuffle_questions: bool | None = None
    shuffle_options: bool | None = None
    allow_back_navigation: bool | None = None
    clear_description: bool = False
    clear_course: bool = False
    clear_pool_size: bool = False

    def touches_the_exam_itself(self) -> bool:
        """Si cambia de qué va el examen, no solo cómo se presenta.

        Estos son los campos que no se pueden mover con gente dentro: cambiar la
        escala o cuántas preguntas tocan a mitad de un examen dejaría a unos
        calificados con una regla y a otros con otra.
        """
        return (
            any(
                valor is not None
                for valor in (
                    self.max_score,
                    self.question_pool_size,
                    self.shuffle_questions,
                    self.shuffle_options,
                )
            )
            or self.clear_pool_size
        )


class UpdateExamSession:
    """Corrige un examen ya creado."""

    def __init__(
        self,
        sessions: ExamSessionRepository,
        participants: ParticipantRepository | None = None,
        courses: CourseRepository | None = None,
    ) -> None:
        self._sessions = sessions
        self._participants = participants
        self._courses = courses

    def execute(
        self,
        session_id: UUID,
        changes: ExamSessionChanges,
        *,
        actor: AuthenticatedUser | None = None,
    ) -> ExamSession:
        """Guarda los cambios y devuelve el examen corregido.

        Raises:
            AuthorizationError: si el examen no es de ese docente, o el curso al
                que se quiere mover tampoco.
            ExamInUseError: si se cambia la escala o el sorteo con estudiantes ya
                dentro.
            InvalidExamSessionError: si el resultado viola una regla, o si el
                examen está cancelado.
        """
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo un docente edita sus examenes")
        ensure_teacher_owns_session(self._sessions, session_id, actor)
        sesion = self._require(session_id)

        if changes.course_id is not None and not changes.clear_course:
            self._check_course(changes.course_id, sesion.teacher_id)

        if changes.touches_the_exam_itself() and self._anyone_inside(session_id):
            raise ExamInUseError(
                "Ya hay estudiantes en este examen: no se puede cambiar la nota maxima "
                "ni como se sortean las preguntas. El titulo, la descripcion y la "
                "duracion si se pueden cambiar."
            )

        corregida = sesion.with_changes(
            title=changes.title,
            starts_at=changes.starts_at,
            duration_minutes=changes.duration_minutes,
            entry_tolerance_minutes=changes.entry_tolerance_minutes,
            description=changes.description,
            course_id=changes.course_id,
            preset=changes.preset,
            max_score=changes.max_score,
            question_pool_size=changes.question_pool_size,
            shuffle_questions=changes.shuffle_questions,
            shuffle_options=changes.shuffle_options,
            allow_back_navigation=changes.allow_back_navigation,
            clear_description=changes.clear_description,
            clear_course=changes.clear_course,
            clear_pool_size=changes.clear_pool_size,
        )
        self._sessions.save(corregida)
        return corregida

    def _require(self, session_id: UUID) -> ExamSession:
        """La sesion, o el mismo error que una ajena.

        `ensure_teacher_owns_session` no comprueba nada cuando la autenticacion
        esta desactivada, asi que sin esto un id inventado llegaria mas abajo.
        Una inexistente y una ajena responden igual a proposito.
        """
        sesion = self._sessions.find_by_id(session_id)
        if sesion is None:
            raise AuthorizationError("No tienes acceso a esta sesion de examen")
        return sesion

    def _anyone_inside(self, session_id: UUID) -> bool:
        if self._participants is None:
            return False
        return bool(self._participants.list_by_session(session_id))

    def _check_course(self, course_id: UUID, teacher_id: UUID) -> None:
        """Mover un examen al curso de otro lo dejaría colgando de ese curso."""
        if self._courses is None:
            return
        curso = self._courses.find_by_id(course_id)
        if curso is None or curso.teacher_id != teacher_id:
            raise AuthorizationError("No tienes acceso a ese curso")


class CancelExamSession:
    """Retira un examen sin borrar nada."""

    def __init__(self, sessions: ExamSessionRepository, clock: Clock) -> None:
        self._sessions = sessions
        self._clock = clock

    def execute(self, session_id: UUID, *, actor: AuthenticatedUser | None = None) -> ExamSession:
        """Marca el examen como cancelado.

        A partir de aquí su código de acceso deja de servir, pero el estudiante
        que lo use recibe "lo canceló tu docente" y no un error cualquiera.

        Raises:
            AuthorizationError: si el examen no es de ese docente.
            InvalidExamSessionError: si ya estaba cancelado.
        """
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo un docente cancela sus examenes")
        ensure_teacher_owns_session(self._sessions, session_id, actor)
        sesion = self._sessions.find_by_id(session_id)
        if sesion is None:
            raise AuthorizationError("No tienes acceso a esta sesion de examen")

        cancelada = sesion.cancelled(self._clock.now())
        self._sessions.save(cancelada)
        return cancelada


class DeleteExamSession:
    """Borra un examen de verdad, y solo cuando no se lleva nada por delante."""

    def __init__(
        self,
        sessions: ExamSessionRepository,
        participants: ParticipantRepository | None = None,
    ) -> None:
        self._sessions = sessions
        self._participants = participants

    def execute(self, session_id: UUID, *, actor: AuthenticatedUser | None = None) -> None:
        """Borra el examen.

        Solo si **nadie entró**. Ese es el caso que el docente necesita: acaba de
        crear un examen con la fecha mal y quiere que desaparezca. En cuanto hay
        un participante hay evidencia, y entonces lo que corresponde es cancelar.

        Raises:
            AuthorizationError: si el examen no es de ese docente.
            ExamInUseError: si ya hay estudiantes.
        """
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo un docente borra sus examenes")
        ensure_teacher_owns_session(self._sessions, session_id, actor)
        if self._sessions.find_by_id(session_id) is None:
            raise AuthorizationError("No tienes acceso a esta sesion de examen")

        if self._participants is not None and self._participants.list_by_session(session_id):
            raise ExamInUseError(
                "Este examen ya tiene estudiantes, asi que no se borra: cancelalo. "
                "Borrarlo se llevaria sus eventos, alertas y respuestas, que son la "
                "evidencia del examen."
            )

        self._sessions.delete(session_id)


__all__ = [
    "CancelExamSession",
    "DeleteExamSession",
    "ExamInUseError",
    "ExamSessionChanges",
    "InvalidExamSessionError",
    "UpdateExamSession",
]
