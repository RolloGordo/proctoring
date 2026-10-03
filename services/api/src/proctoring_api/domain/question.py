"""Preguntas de un examen y sus opciones.

**La regla que manda en todo este módulo:** la respuesta correcta no puede llegar
nunca al estudiante. Vive en `question_options.is_correct`,
`questions.correct_numeric_answer` y `questions.correct_text_answer`, y la API es
el único camino por el que un estudiante lee preguntas — RLS no le da acceso
directo a esas tablas a propósito.

Por eso existen dos representaciones y no un campo opcional: `Question` para el
docente y `ExamQuestion` para el estudiante. Un `bool` que a veces se omite se
olvida de omitir; un tipo que **no tiene** el campo no puede filtrarse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from proctoring_api.domain.errors import DomainError

MAX_STATEMENT_LENGTH = 5000
MAX_OPTION_LENGTH = 1000
MAX_OPTIONS = 10
MIN_OPTIONS = 2


class InvalidQuestionError(DomainError):
    """Una pregunta no cumple las reglas del dominio."""


class QuestionType(StrEnum):
    """Mismos valores que el enum `question_type` de PostgreSQL."""

    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    NUMERIC = "numeric"
    FILL_BLANK = "fill_blank"
    ESSAY = "essay"


#: Tipos que se responden eligiendo entre opciones.
CHOICE_TYPES = frozenset({QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE})


@dataclass(frozen=True, slots=True)
class QuestionOption:
    """Una alternativa. **Incluye si es la correcta: nunca sale hacia el estudiante.**"""

    id: UUID
    position: int
    option_text: str
    is_correct: bool


@dataclass(frozen=True, slots=True)
class ExamOption:
    """La misma alternativa, como la ve el estudiante.

    No tiene `is_correct`. No es que se omita: no existe.
    """

    id: UUID
    position: int
    option_text: str


@dataclass(frozen=True, slots=True)
class Question:
    """Una pregunta con su respuesta correcta. Solo para el docente."""

    id: UUID
    session_id: UUID
    position: int
    question_type: QuestionType
    statement: str
    points: Decimal
    options: tuple[QuestionOption, ...] = ()
    correct_numeric_answer: Decimal | None = None
    numeric_tolerance: Decimal | None = None
    correct_text_answer: str | None = None
    source_format: str | None = None

    @classmethod
    def create(
        cls,
        *,
        session_id: UUID,
        position: int,
        question_type: QuestionType,
        statement: str,
        points: Decimal = Decimal(1),
        options: list[tuple[str, bool]] | None = None,
        correct_numeric_answer: Decimal | None = None,
        numeric_tolerance: Decimal | None = None,
        correct_text_answer: str | None = None,
        source_format: str | None = None,
        question_id: UUID | None = None,
    ) -> Question:
        """Crea una pregunta validada.

        Raises:
            InvalidQuestionError: si viola alguna regla del dominio.
        """
        clean_statement = statement.strip()
        if not clean_statement:
            raise InvalidQuestionError("El enunciado no puede estar vacio")
        if len(clean_statement) > MAX_STATEMENT_LENGTH:
            raise InvalidQuestionError(f"El enunciado supera los {MAX_STATEMENT_LENGTH} caracteres")

        if position <= 0:
            raise InvalidQuestionError("La posicion debe ser mayor que cero")
        if points < 0:
            raise InvalidQuestionError("El puntaje no puede ser negativo")

        built = _build_options(question_type, options or [])
        _check_answer_fields(
            question_type, correct_numeric_answer, numeric_tolerance, correct_text_answer
        )

        return cls(
            id=question_id if question_id is not None else uuid4(),
            session_id=session_id,
            position=position,
            question_type=question_type,
            statement=clean_statement,
            points=points,
            options=built,
            correct_numeric_answer=correct_numeric_answer,
            numeric_tolerance=numeric_tolerance,
            correct_text_answer=(correct_text_answer or "").strip() or None,
            source_format=source_format,
        )

    def for_student(self) -> ExamQuestion:
        """La misma pregunta sin nada que revele la respuesta.

        Es el **único** camino por el que una pregunta llega al estudiante.
        """
        return ExamQuestion(
            id=self.id,
            position=self.position,
            question_type=self.question_type,
            statement=self.statement,
            points=self.points,
            options=tuple(
                ExamOption(id=o.id, position=o.position, option_text=o.option_text)
                for o in self.options
            ),
        )


@dataclass(frozen=True, slots=True)
class ExamQuestion:
    """Una pregunta como la ve el estudiante mientras rinde.

    No tiene `correct_numeric_answer`, ni `correct_text_answer`, ni opciones con
    `is_correct`. Construirla solo es posible desde `Question.for_student()`.
    """

    id: UUID
    position: int
    question_type: QuestionType
    statement: str
    points: Decimal
    options: tuple[ExamOption, ...] = field(default_factory=tuple)


def _build_options(
    question_type: QuestionType, options: list[tuple[str, bool]]
) -> tuple[QuestionOption, ...]:
    if question_type not in CHOICE_TYPES:
        if options:
            raise InvalidQuestionError(
                f"Una pregunta de tipo {question_type.value} no lleva opciones"
            )
        return ()

    if len(options) < MIN_OPTIONS:
        raise InvalidQuestionError(
            f"Una pregunta de tipo {question_type.value} necesita al menos {MIN_OPTIONS} opciones"
        )
    if len(options) > MAX_OPTIONS:
        raise InvalidQuestionError(f"Como maximo {MAX_OPTIONS} opciones por pregunta")
    if question_type is QuestionType.TRUE_FALSE and len(options) != 2:
        raise InvalidQuestionError("Una pregunta de verdadero o falso lleva exactamente 2 opciones")

    textos = [texto.strip() for texto, _ in options]
    if any(not texto for texto in textos):
        raise InvalidQuestionError("Ninguna opcion puede estar vacia")
    if any(len(texto) > MAX_OPTION_LENGTH for texto in textos):
        raise InvalidQuestionError(f"Una opcion supera los {MAX_OPTION_LENGTH} caracteres")
    if len({texto.casefold() for texto in textos}) != len(textos):
        raise InvalidQuestionError("Hay opciones repetidas")

    # Sin correcta, la pregunta no se puede calificar. Sin incorrectas, no mide
    # nada: ambas cosas son errores del docente que conviene avisar al crearla y
    # no al terminar el examen.
    correctas = sum(1 for _, correcta in options if correcta)
    if correctas == 0:
        raise InvalidQuestionError("Hay que marcar al menos una opcion correcta")
    if correctas == len(options):
        raise InvalidQuestionError("No todas las opciones pueden ser correctas")

    # El texto se toma ya limpio de `textos`; la marca, de la entrada original.
    return tuple(
        QuestionOption(id=uuid4(), position=indice, option_text=texto, is_correct=correcta)
        for indice, (texto, (_, correcta)) in enumerate(zip(textos, options, strict=True), start=1)
    )


def _check_answer_fields(
    question_type: QuestionType,
    correct_numeric_answer: Decimal | None,
    numeric_tolerance: Decimal | None,
    correct_text_answer: str | None,
) -> None:
    if question_type is QuestionType.NUMERIC:
        if correct_numeric_answer is None:
            raise InvalidQuestionError("Una pregunta numerica necesita su respuesta correcta")
        if numeric_tolerance is not None and numeric_tolerance < 0:
            raise InvalidQuestionError("La tolerancia no puede ser negativa")
    elif correct_numeric_answer is not None:
        raise InvalidQuestionError(
            f"Una pregunta de tipo {question_type.value} no lleva respuesta numerica"
        )

    if question_type is QuestionType.FILL_BLANK:
        if not (correct_text_answer or "").strip():
            raise InvalidQuestionError("Una pregunta de completar necesita su respuesta correcta")
    elif correct_text_answer is not None and correct_text_answer.strip():
        raise InvalidQuestionError(
            f"Una pregunta de tipo {question_type.value} no lleva respuesta de texto"
        )
