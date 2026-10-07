"""Corregir y borrar una pregunta ya creada.

Faltaba lo obvio: el docente escribía un enunciado con una errata o le ponía 2
puntos a algo que vale 5, y no había forma de arreglarlo sin rehacer el examen.

Una pregunta se puede corregir mientras **nadie la haya respondido**. Después no,
porque cambiarle la respuesta correcta a una pregunta ya contestada reescribiría
la nota de quien la respondió bien, sin que nadie se entere. Lo mismo al borrar.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from proctoring_api.application.ports.answer_repository import AnswerRepository
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.ports.question_bank_repository import QuestionBankRepository
from proctoring_api.application.ports.question_repository import QuestionRepository
from proctoring_api.application.session_access import ensure_teacher_owns_session
from proctoring_api.application.use_cases.manage_banks import ensure_teacher_owns_bank
from proctoring_api.domain.errors import AuthorizationError, DomainError
from proctoring_api.domain.question import InvalidQuestionError, Question
from proctoring_api.domain.user import AuthenticatedUser


class QuestionAlreadyAnsweredError(DomainError):
    """Alguien ya respondió esta pregunta, así que ya no se toca."""


@dataclass(frozen=True, slots=True)
class QuestionChanges:
    """Lo que se quiere cambiar. `None` es "no lo toques".

    Las opciones se envían **enteras** o no se envían: cambiar una sola dejaría
    al resto con posiciones inconsistentes, y el tipo de pregunta no cambia
    nunca —una de opción múltiple convertida en numérica no es una corrección,
    es otra pregunta.
    """

    statement: str | None = None
    points: Decimal | None = None
    options: list[tuple[str, bool]] | None = None
    correct_numeric_answer: Decimal | None = None
    numeric_tolerance: Decimal | None = None
    correct_text_answer: str | None = None


class _QuestionAccess:
    """Lo que comparten corregir y borrar: llegar a la pregunta con permiso."""

    def __init__(
        self,
        questions: QuestionRepository,
        sessions: ExamSessionRepository | None = None,
        banks: QuestionBankRepository | None = None,
        answers: AnswerRepository | None = None,
    ) -> None:
        self._questions = questions
        self._sessions = sessions
        self._banks = banks
        self._answers = answers

    def _authorized(self, question_id: UUID, actor: AuthenticatedUser | None) -> Question:
        """La pregunta, si quien pregunta es su docente.

        Una pregunta cuelga de un examen **o** de un banco, así que la
        comprobación va por el camino que corresponda. Una inexistente y una
        ajena responden lo mismo: distinguirlas permitiría averiguar qué
        preguntas existen.
        """
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo un docente edita las preguntas")

        pregunta = self._questions.find_by_id(question_id)
        if pregunta is None:
            raise AuthorizationError("No tienes acceso a esta pregunta")

        # El mensaje se unifica: `ensure_teacher_owns_session` dice "no tienes
        # acceso a esta sesion" y el de arriba "a esta pregunta". Con dos mensajes
        # distintos, tantear ids revelaria cuales existen de verdad.
        try:
            if pregunta.session_id is not None:
                ensure_teacher_owns_session(self._sessions, pregunta.session_id, actor)
            elif pregunta.bank_id is not None and self._banks is not None:
                ensure_teacher_owns_bank(self._banks, pregunta.bank_id, actor)
        except AuthorizationError:
            raise AuthorizationError("No tienes acceso a esta pregunta") from None

        return pregunta

    def _ensure_untouched(self, question_id: UUID) -> None:
        """Nadie la ha respondido todavía.

        Sin esto, cambiar la alternativa correcta de una pregunta ya contestada
        reescribiría en silencio la nota de quien la respondió bien.
        """
        if self._answers is None:
            return
        if self._answers.count_by_question(question_id):
            raise QuestionAlreadyAnsweredError(
                "Algun estudiante ya respondio esta pregunta, asi que no se puede "
                "cambiar ni borrar. Cambiarla ahora reescribiria su nota."
            )


class UpdateQuestion(_QuestionAccess):
    """Corrige el enunciado, los puntos o las alternativas de una pregunta."""

    def execute(
        self,
        question_id: UUID,
        changes: QuestionChanges,
        *,
        actor: AuthenticatedUser | None = None,
    ) -> Question:
        """Devuelve la pregunta corregida.

        Se reconstruye con `Question.create` en vez de escribir los campos a
        mano: si editar saltara las validaciones, se podría llegar por la puerta
        de atrás a una pregunta de opción múltiple sin ninguna correcta, que
        `create` nunca habría aceptado.

        Raises:
            AuthorizationError: si la pregunta no es de ese docente, o no existe.
            QuestionAlreadyAnsweredError: si alguien ya la respondió.
            InvalidQuestionError: si el resultado viola una regla.
        """
        pregunta = self._authorized(question_id, actor)
        self._ensure_untouched(question_id)

        opciones = (
            changes.options
            if changes.options is not None
            else [(o.option_text, o.is_correct) for o in pregunta.options]
        )

        corregida = Question.create(
            question_id=pregunta.id,
            session_id=pregunta.session_id,
            bank_id=pregunta.bank_id,
            position=pregunta.position,
            question_type=pregunta.question_type,
            statement=changes.statement if changes.statement is not None else pregunta.statement,
            points=changes.points if changes.points is not None else pregunta.points,
            options=opciones,
            correct_numeric_answer=(
                changes.correct_numeric_answer
                if changes.correct_numeric_answer is not None
                else pregunta.correct_numeric_answer
            ),
            numeric_tolerance=(
                changes.numeric_tolerance
                if changes.numeric_tolerance is not None
                else pregunta.numeric_tolerance
            ),
            correct_text_answer=(
                changes.correct_text_answer
                if changes.correct_text_answer is not None
                else pregunta.correct_text_answer
            ),
            source_format=pregunta.source_format,
        )

        self._questions.save_many([corregida])
        return corregida


class DeleteQuestion(_QuestionAccess):
    """Quita una pregunta de su examen o de su banco."""

    def execute(self, question_id: UUID, *, actor: AuthenticatedUser | None = None) -> None:
        """Borra la pregunta.

        **No renumera las que quedan.** Las posiciones dejan huecos (1, 2, 4) y
        eso está bien: el orden se conserva, que es lo único que `position`
        promete, y renumerar cambiaría el identificador de posición de preguntas
        que nadie tocó.

        Raises:
            AuthorizationError: si la pregunta no es de ese docente, o no existe.
            QuestionAlreadyAnsweredError: si alguien ya la respondió.
        """
        self._authorized(question_id, actor)
        self._ensure_untouched(question_id)
        self._questions.delete(question_id)


__all__ = [
    "DeleteQuestion",
    "InvalidQuestionError",
    "QuestionAlreadyAnsweredError",
    "QuestionChanges",
    "UpdateQuestion",
]
