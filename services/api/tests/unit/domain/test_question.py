"""Reglas de la pregunta."""

from __future__ import annotations

from dataclasses import fields
from decimal import Decimal
from uuid import uuid4

import pytest

from proctoring_api.domain.question import (
    ExamOption,
    ExamQuestion,
    InvalidQuestionError,
    Question,
    QuestionType,
)

SESSION = uuid4()


def make(**overrides: object) -> Question:
    kwargs: dict[str, object] = {
        "session_id": SESSION,
        "position": 1,
        "question_type": QuestionType.MULTIPLE_CHOICE,
        "statement": "¿Qué hace RLS en PostgreSQL?",
        "options": [("Filtra filas por usuario", True), ("Comprime la base", False)],
    }
    kwargs.update(overrides)
    return Question.create(**kwargs)  # type: ignore[arg-type]


class TestLaRespuestaNoSeFiltra:
    """Lo más importante de este módulo."""

    def test_la_vista_del_estudiante_no_tiene_el_campo(self) -> None:
        # No es que se omita: el tipo no lo declara. Un bool que a veces se
        # omite se olvida de omitir.
        assert "is_correct" not in {f.name for f in fields(ExamOption)}
        for campo in ("correct_numeric_answer", "correct_text_answer"):
            assert campo not in {f.name for f in fields(ExamQuestion)}

    def test_for_student_conserva_lo_que_el_estudiante_necesita(self) -> None:
        pregunta = make()
        examen = pregunta.for_student()

        assert examen.id == pregunta.id
        assert examen.statement == pregunta.statement
        assert [o.option_text for o in examen.options] == [o.option_text for o in pregunta.options]

    def test_ni_una_pregunta_numerica_filtra_su_respuesta(self) -> None:
        pregunta = make(
            question_type=QuestionType.NUMERIC,
            options=[],
            correct_numeric_answer=Decimal("42.5"),
        )

        serializada = str(pregunta.for_student())

        assert "42.5" not in serializada


class TestEnunciado:
    @pytest.mark.parametrize("statement", ["", "   ", "\n\t"])
    def test_rechaza_vacio(self, statement: str) -> None:
        with pytest.raises(InvalidQuestionError, match="enunciado"):
            make(statement=statement)

    def test_recorta_espacios(self) -> None:
        assert make(statement="  ¿Qué es RLS?  ").statement == "¿Qué es RLS?"

    def test_rechaza_demasiado_largo(self) -> None:
        with pytest.raises(InvalidQuestionError, match="5000"):
            make(statement="x" * 5001)


class TestOpciones:
    def test_necesita_al_menos_dos(self) -> None:
        with pytest.raises(InvalidQuestionError, match="al menos 2"):
            make(options=[("Solo una", True)])

    def test_necesita_una_correcta(self) -> None:
        # Sin correcta no se puede calificar.
        with pytest.raises(InvalidQuestionError, match="al menos una opcion correcta"):
            make(options=[("A", False), ("B", False)])

    def test_no_pueden_ser_todas_correctas(self) -> None:
        # Si todas valen, la pregunta no mide nada.
        with pytest.raises(InvalidQuestionError, match="No todas"):
            make(options=[("A", True), ("B", True)])

    def test_rechaza_repetidas(self) -> None:
        with pytest.raises(InvalidQuestionError, match="repetidas"):
            make(options=[("Madrid", True), ("  madrid  ", False)])

    def test_rechaza_vacias(self) -> None:
        with pytest.raises(InvalidQuestionError, match="vacia"):
            make(options=[("Correcta", True), ("   ", False)])

    def test_numera_desde_uno(self) -> None:
        pregunta = make(options=[("A", True), ("B", False), ("C", False)])

        assert [o.position for o in pregunta.options] == [1, 2, 3]

    def test_un_ensayo_no_lleva_opciones(self) -> None:
        with pytest.raises(InvalidQuestionError, match="no lleva opciones"):
            make(question_type=QuestionType.ESSAY, options=[("A", True), ("B", False)])

    def test_verdadero_o_falso_lleva_exactamente_dos(self) -> None:
        with pytest.raises(InvalidQuestionError, match="exactamente 2"):
            make(
                question_type=QuestionType.TRUE_FALSE,
                options=[("Sí", True), ("No", False), ("Quizá", False)],
            )


class TestRespuestasDeOtrosTipos:
    def test_numerica_necesita_su_respuesta(self) -> None:
        with pytest.raises(InvalidQuestionError, match="numerica necesita"):
            make(question_type=QuestionType.NUMERIC, options=[])

    def test_completar_necesita_su_respuesta(self) -> None:
        with pytest.raises(InvalidQuestionError, match="completar necesita"):
            make(question_type=QuestionType.FILL_BLANK, options=[])

    def test_una_de_opcion_multiple_no_lleva_respuesta_numerica(self) -> None:
        # Guardarla ahí sería un dato muerto que nadie califica.
        with pytest.raises(InvalidQuestionError, match="no lleva respuesta numerica"):
            make(correct_numeric_answer=Decimal(5))

    def test_tolerancia_no_negativa(self) -> None:
        with pytest.raises(InvalidQuestionError, match="tolerancia"):
            make(
                question_type=QuestionType.NUMERIC,
                options=[],
                correct_numeric_answer=Decimal(5),
                numeric_tolerance=Decimal(-1),
            )


class TestNumeros:
    def test_posicion_positiva(self) -> None:
        with pytest.raises(InvalidQuestionError, match="posicion"):
            make(position=0)

    def test_puntaje_no_negativo(self) -> None:
        with pytest.raises(InvalidQuestionError, match="puntaje"):
            make(points=Decimal(-1))

    def test_puntaje_cero_es_valido(self) -> None:
        # Una pregunta de práctica que no suma puntos es legítima.
        assert make(points=Decimal(0)).points == Decimal(0)


def test_los_tipos_coinciden_con_el_enum_de_postgresql() -> None:
    assert {t.value for t in QuestionType} == {
        "multiple_choice",
        "true_false",
        "numeric",
        "fill_blank",
        "essay",
    }
