"""Reglas de forma de una respuesta.

Lo que se prueba aqui es que una respuesta no pueda tener una forma que despues
nadie sepa calificar: una opcion elegida en una pregunta de desarrollo, un
numero en una de completar, o una opcion que es de otra pregunta.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from proctoring_api.domain.answer import MAX_TEXT_ANSWER_LENGTH, Answer, InvalidAnswerError
from proctoring_api.domain.question import Question, QuestionType

NOW = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)


def pregunta_opcion_multiple() -> Question:
    return Question.create(
        session_id=uuid4(),
        position=1,
        question_type=QuestionType.MULTIPLE_CHOICE,
        statement="¿Que hace RLS?",
        options=[("Filtra filas", True), ("Comprime", False)],
    )


def pregunta(tipo: QuestionType, **extra: object) -> Question:
    return Question.create(
        session_id=uuid4(),
        position=1,
        question_type=tipo,
        statement="Enunciado",
        **extra,  # type: ignore[arg-type]
    )


class TestOpciones:
    def test_guarda_la_opcion_elegida(self) -> None:
        q = pregunta_opcion_multiple().for_student()
        elegida = q.options[1].id

        respuesta = Answer.create(
            question=q, participant_id=uuid4(), answered_at=NOW, selected_option_id=elegida
        )

        assert respuesta.selected_option_id == elegida
        assert respuesta.question_id == q.id
        assert respuesta.text_answer is None

    def test_rechaza_una_opcion_de_otra_pregunta(self) -> None:
        q = pregunta_opcion_multiple().for_student()

        with pytest.raises(InvalidAnswerError, match="no pertenece"):
            Answer.create(
                question=q, participant_id=uuid4(), answered_at=NOW, selected_option_id=uuid4()
            )

    def test_rechaza_texto_en_una_pregunta_de_opciones(self) -> None:
        q = pregunta_opcion_multiple().for_student()

        with pytest.raises(InvalidAnswerError):
            Answer.create(
                question=q,
                participant_id=uuid4(),
                answered_at=NOW,
                selected_option_id=q.options[0].id,
                text_answer="a mano",
            )

    def test_rechaza_no_elegir_nada(self) -> None:
        q = pregunta_opcion_multiple().for_student()

        with pytest.raises(InvalidAnswerError, match="eligiendo"):
            Answer.create(question=q, participant_id=uuid4(), answered_at=NOW)


class TestNumericas:
    def test_guarda_el_numero(self) -> None:
        q = pregunta(QuestionType.NUMERIC, correct_numeric_answer=Decimal("42.5")).for_student()

        respuesta = Answer.create(
            question=q,
            participant_id=uuid4(),
            answered_at=NOW,
            numeric_answer=Decimal("40.25"),
        )

        assert respuesta.numeric_answer == Decimal("40.25")

    def test_rechaza_responder_con_texto(self) -> None:
        q = pregunta(QuestionType.NUMERIC, correct_numeric_answer=Decimal(1)).for_student()

        with pytest.raises(InvalidAnswerError, match="numero"):
            Answer.create(
                question=q, participant_id=uuid4(), answered_at=NOW, text_answer="cuarenta"
            )

    def test_rechaza_nan(self) -> None:
        q = pregunta(QuestionType.NUMERIC, correct_numeric_answer=Decimal(1)).for_student()

        with pytest.raises(InvalidAnswerError):
            Answer.create(
                question=q,
                participant_id=uuid4(),
                answered_at=NOW,
                numeric_answer=Decimal("NaN"),
            )


class TestTexto:
    def test_guarda_el_desarrollo_sin_espacios_de_sobra(self) -> None:
        q = pregunta(QuestionType.ESSAY).for_student()

        respuesta = Answer.create(
            question=q, participant_id=uuid4(), answered_at=NOW, text_answer="  mi respuesta  "
        )

        assert respuesta.text_answer == "mi respuesta"

    def test_rechaza_un_desarrollo_vacio(self) -> None:
        q = pregunta(QuestionType.ESSAY).for_student()

        with pytest.raises(InvalidAnswerError, match="escribiendo"):
            Answer.create(question=q, participant_id=uuid4(), answered_at=NOW, text_answer="   ")

    def test_rechaza_un_desarrollo_enorme(self) -> None:
        q = pregunta(QuestionType.ESSAY).for_student()

        with pytest.raises(InvalidAnswerError, match="supera"):
            Answer.create(
                question=q,
                participant_id=uuid4(),
                answered_at=NOW,
                text_answer="a" * (MAX_TEXT_ANSWER_LENGTH + 1),
            )

    def test_completar_acepta_texto(self) -> None:
        q = pregunta(QuestionType.FILL_BLANK, correct_text_answer="hexagonal").for_student()

        respuesta = Answer.create(
            question=q, participant_id=uuid4(), answered_at=NOW, text_answer="hexagonal"
        )

        assert respuesta.text_answer == "hexagonal"


def test_exige_hora_con_zona() -> None:
    q = pregunta(QuestionType.ESSAY).for_student()

    with pytest.raises(InvalidAnswerError, match="zona horaria"):
        Answer.create(
            question=q,
            participant_id=uuid4(),
            answered_at=datetime(2026, 10, 3, 15, 0),
            text_answer="algo",
        )
