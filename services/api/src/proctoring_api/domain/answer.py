"""Respuestas del estudiante a las preguntas de un examen.

Este módulo valida la **forma** de una respuesta, no su corrección: que una
pregunta de opción múltiple se responda eligiendo una de sus opciones y no
escribiendo texto, que una numérica traiga un número, que un desarrollo no venga
vacío. Calificar es otra cosa y pasa después, con la `Question` completa, que
vive solo del lado del docente.

Por eso la validación recibe una `ExamQuestion`: es la vista de la pregunta que
**no** tiene la respuesta correcta. Así el dominio de las respuestas no puede
filtrar lo que no debe ni aunque alguien se equivoque al usarlo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from proctoring_api.domain.errors import DomainError
from proctoring_api.domain.question import CHOICE_TYPES, ExamQuestion, QuestionType

#: Tope de un desarrollo. Generoso para un ensayo, pero finito: el cuerpo de la
#: peticion llega a la base de datos y no hay razon para aceptar megabytes.
MAX_TEXT_ANSWER_LENGTH = 10_000


class InvalidAnswerError(DomainError):
    """La respuesta no corresponde al tipo de pregunta."""


@dataclass(frozen=True, slots=True)
class Answer:
    """Lo que el estudiante respondió a una pregunta.

    Se identifica por `(participant_id, question_id)`, igual que la restricción
    única de la tabla `answers`: responder otra vez la misma pregunta
    **sobrescribe**, no acumula.
    """

    id: UUID
    participant_id: UUID
    question_id: UUID
    answered_at: datetime
    selected_option_id: UUID | None = None
    text_answer: str | None = None
    numeric_answer: Decimal | None = None

    @classmethod
    def create(
        cls,
        *,
        question: ExamQuestion,
        participant_id: UUID,
        answered_at: datetime,
        selected_option_id: UUID | None = None,
        text_answer: str | None = None,
        numeric_answer: Decimal | None = None,
        answer_id: UUID | None = None,
    ) -> Answer:
        """Crea una respuesta validada contra el tipo de su pregunta.

        Raises:
            InvalidAnswerError: si la respuesta no corresponde al tipo de
                pregunta, si está vacía o si la opción elegida no es de esa
                pregunta.
        """
        if answered_at.tzinfo is None:
            raise InvalidAnswerError("La hora de la respuesta necesita zona horaria")

        limpio = (text_answer or "").strip() or None

        if question.question_type in CHOICE_TYPES:
            _check_choice(question, selected_option_id, limpio, numeric_answer)
        elif question.question_type is QuestionType.NUMERIC:
            _check_numeric(selected_option_id, limpio, numeric_answer)
        else:
            _check_text(question.question_type, selected_option_id, limpio, numeric_answer)

        return cls(
            id=answer_id if answer_id is not None else uuid4(),
            participant_id=participant_id,
            question_id=question.id,
            answered_at=answered_at,
            selected_option_id=selected_option_id,
            text_answer=limpio,
            numeric_answer=numeric_answer,
        )


def _check_choice(
    question: ExamQuestion,
    selected_option_id: UUID | None,
    text_answer: str | None,
    numeric_answer: Decimal | None,
) -> None:
    if selected_option_id is None:
        raise InvalidAnswerError("Esta pregunta se responde eligiendo una opcion")
    if text_answer is not None or numeric_answer is not None:
        raise InvalidAnswerError("Esta pregunta solo admite una opcion, no texto ni numeros")
    # La opcion tiene que ser de ESTA pregunta: mandar el id de una opcion de
    # otra pregunta guardaria una respuesta que despues nadie podria calificar.
    if selected_option_id not in {opcion.id for opcion in question.options}:
        raise InvalidAnswerError("Esa opcion no pertenece a esta pregunta")


def _check_numeric(
    selected_option_id: UUID | None,
    text_answer: str | None,
    numeric_answer: Decimal | None,
) -> None:
    if numeric_answer is None:
        raise InvalidAnswerError("Esta pregunta se responde con un numero")
    if selected_option_id is not None or text_answer is not None:
        raise InvalidAnswerError("Esta pregunta solo admite un numero")
    if not numeric_answer.is_finite():
        raise InvalidAnswerError("Ese numero no es valido")


def _check_text(
    question_type: QuestionType,
    selected_option_id: UUID | None,
    text_answer: str | None,
    numeric_answer: Decimal | None,
) -> None:
    if text_answer is None:
        raise InvalidAnswerError("Esta pregunta se responde escribiendo")
    if selected_option_id is not None or numeric_answer is not None:
        raise InvalidAnswerError(
            f"Una pregunta de tipo {question_type.value} se responde solo con texto"
        )
    if len(text_answer) > MAX_TEXT_ANSWER_LENGTH:
        raise InvalidAnswerError(f"La respuesta supera los {MAX_TEXT_ANSWER_LENGTH} caracteres")
