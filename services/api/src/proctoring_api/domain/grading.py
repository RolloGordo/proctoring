"""Calificación automática de un examen.

Corrige lo que se puede corregir sin criterio: opción múltiple, verdadero o
falso, numéricas y completar. **Los desarrollos no se califican solos**: esa
nota es del docente. El sistema lo dice en vez de inventar un puntaje, y por eso
el resultado distingue lo ganado de lo que falta por revisar.

Todo aquí es puro: recibe preguntas y respuestas y devuelve notas, sin base de
datos ni reloj. Así se prueba con casos límite sin montar nada.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from proctoring_api.domain.answer import Answer
from proctoring_api.domain.question import Question, QuestionType

#: Tipos que corrige una persona.
MANUAL_TYPES = frozenset({QuestionType.ESSAY})


@dataclass(frozen=True, slots=True)
class GradedAnswer:
    """El resultado de corregir una respuesta.

    `is_correct` y `points` son `None` cuando la corrige el docente: no es un
    cero, es que todavía no hay nota.
    """

    is_correct: bool | None
    points: Decimal | None


@dataclass(frozen=True, slots=True)
class ExamScore:
    """La nota de un examen entregado."""

    #: Puntos ganados en lo que se corrige solo.
    earned: Decimal
    #: Puntos de todo el examen, desarrollos incluidos.
    maximum: Decimal
    #: Si hay preguntas que el docente todavía tiene que calificar. Mientras
    #: sea verdadero, `earned` es parcial.
    pending_manual: bool
    #: Corrección de cada pregunta que el estudiante contestó.
    by_question: dict[UUID, GradedAnswer]


def normalize_text(value: str) -> str:
    """Deja un texto listo para compararlo con la respuesta esperada.

    Ignora mayúsculas, tildes y espacios de sobra: penalizar a alguien por
    olvidar una tilde en un examen escrito en un teclado ajeno no mide lo que se
    quiere medir. **La ñ se conserva**, porque `año` y `ano` son palabras
    distintas.
    """
    decomposed = unicodedata.normalize("NFD", value.casefold())
    kept: list[str] = []
    for char in decomposed:
        if unicodedata.combining(char):
            if char == "̃" and kept and kept[-1] == "n":
                kept.append(char)
            continue
        kept.append(char)
    return " ".join(unicodedata.normalize("NFC", "".join(kept)).split())


def grade_answer(question: Question, answer: Answer | None) -> GradedAnswer:
    """Corrige una respuesta contra su pregunta.

    Una pregunta sin responder vale cero, salvo los desarrollos, que no tienen
    nota automática de ningún modo.
    """
    if question.question_type in MANUAL_TYPES:
        return GradedAnswer(is_correct=None, points=None)

    correct = _is_correct(question, answer) if answer is not None else False
    return GradedAnswer(is_correct=correct, points=question.points if correct else Decimal(0))


def score_exam(questions: Sequence[Question], answers: Sequence[Answer]) -> ExamScore:
    """Califica un examen completo."""
    by_question_id = {answer.question_id: answer for answer in answers}

    earned = Decimal(0)
    maximum = Decimal(0)
    pending_manual = False
    graded: dict[UUID, GradedAnswer] = {}

    for question in questions:
        maximum += question.points
        answer = by_question_id.get(question.id)
        result = grade_answer(question, answer)

        if result.points is None:
            pending_manual = True
        else:
            earned += result.points

        # Solo se registran las respuestas que existen: no hay fila que
        # actualizar para una pregunta que el estudiante dejó en blanco.
        if answer is not None:
            graded[question.id] = result

    return ExamScore(
        earned=earned, maximum=maximum, pending_manual=pending_manual, by_question=graded
    )


def _is_correct(question: Question, answer: Answer) -> bool:
    kind = question.question_type

    if kind in (QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE):
        chosen = next((o for o in question.options if o.id == answer.selected_option_id), None)
        return chosen is not None and chosen.is_correct

    if kind is QuestionType.NUMERIC:
        if answer.numeric_answer is None or question.correct_numeric_answer is None:
            return False
        tolerance = question.numeric_tolerance or Decimal(0)
        return abs(answer.numeric_answer - question.correct_numeric_answer) <= tolerance

    if kind is QuestionType.FILL_BLANK:
        if answer.text_answer is None or question.correct_text_answer is None:
            return False
        return normalize_text(answer.text_answer) == normalize_text(question.correct_text_answer)

    return False
