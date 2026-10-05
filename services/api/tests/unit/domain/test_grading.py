"""Calificación automática: qué cuenta como acierto y qué se deja al docente."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from proctoring_api.domain.answer import Answer
from proctoring_api.domain.grading import grade_answer, normalize_text, score_exam
from proctoring_api.domain.question import Question, QuestionType

NOW = datetime(2026, 10, 5, 15, 0, tzinfo=UTC)
PARTICIPANTE = uuid4()


def pregunta(tipo: QuestionType, puntos: int = 2, **extra: object) -> Question:
    return Question.create(
        session_id=uuid4(),
        position=1,
        question_type=tipo,
        statement="Enunciado",
        points=Decimal(puntos),
        **extra,  # type: ignore[arg-type]
    )


def respuesta(q: Question, **campos: object) -> Answer:
    return Answer(
        id=uuid4(),
        participant_id=PARTICIPANTE,
        question_id=q.id,
        answered_at=NOW,
        **campos,  # type: ignore[arg-type]
    )


def opcion_multiple() -> Question:
    return pregunta(
        QuestionType.MULTIPLE_CHOICE,
        options=[("Correcta", True), ("Incorrecta", False), ("Otra", False)],
    )


class TestOpciones:
    def test_acierta_si_elige_la_correcta(self) -> None:
        q = opcion_multiple()

        resultado = grade_answer(q, respuesta(q, selected_option_id=q.options[0].id))

        assert resultado.is_correct is True
        assert resultado.points == Decimal(2)

    def test_falla_si_elige_otra_y_gana_cero(self) -> None:
        q = opcion_multiple()

        resultado = grade_answer(q, respuesta(q, selected_option_id=q.options[1].id))

        assert resultado.is_correct is False
        assert resultado.points == Decimal(0)

    def test_verdadero_o_falso(self) -> None:
        q = pregunta(QuestionType.TRUE_FALSE, options=[("Verdadero", False), ("Falso", True)])

        assert grade_answer(q, respuesta(q, selected_option_id=q.options[1].id)).is_correct is True
        assert grade_answer(q, respuesta(q, selected_option_id=q.options[0].id)).is_correct is False

    def test_con_varias_correctas_vale_cualquiera_de_ellas(self) -> None:
        # El dominio admite varias (hara falta al importar QTI); una respuesta
        # guardada apunta a una sola opcion.
        q = pregunta(
            QuestionType.MULTIPLE_CHOICE,
            options=[("A", True), ("B", True), ("C", False)],
        )

        assert grade_answer(q, respuesta(q, selected_option_id=q.options[1].id)).is_correct is True


class TestNumericas:
    def test_acierta_con_el_valor_exacto(self) -> None:
        q = pregunta(QuestionType.NUMERIC, correct_numeric_answer=Decimal("10"))

        assert grade_answer(q, respuesta(q, numeric_answer=Decimal("10"))).is_correct is True

    def test_diez_y_diez_punto_cero_son_lo_mismo(self) -> None:
        q = pregunta(QuestionType.NUMERIC, correct_numeric_answer=Decimal("10"))

        assert grade_answer(q, respuesta(q, numeric_answer=Decimal("10.0"))).is_correct is True

    def test_sin_tolerancia_un_valor_cercano_no_vale(self) -> None:
        q = pregunta(QuestionType.NUMERIC, correct_numeric_answer=Decimal("10"))

        assert grade_answer(q, respuesta(q, numeric_answer=Decimal("10.01"))).is_correct is False

    def test_con_tolerancia_vale_dentro_del_margen_en_ambos_sentidos(self) -> None:
        q = pregunta(
            QuestionType.NUMERIC,
            correct_numeric_answer=Decimal("10"),
            numeric_tolerance=Decimal("0.5"),
        )

        assert grade_answer(q, respuesta(q, numeric_answer=Decimal("10.5"))).is_correct is True
        assert grade_answer(q, respuesta(q, numeric_answer=Decimal("9.5"))).is_correct is True
        assert grade_answer(q, respuesta(q, numeric_answer=Decimal("10.51"))).is_correct is False


class TestCompletar:
    @pytest.mark.parametrize("escrito", ["hexagonal", "Hexagonal", "  HEXAGONAL  ", "hexagonal "])
    def test_ignora_mayusculas_y_espacios_de_sobra(self, escrito: str) -> None:
        q = pregunta(QuestionType.FILL_BLANK, correct_text_answer="hexagonal")

        assert grade_answer(q, respuesta(q, text_answer=escrito)).is_correct is True

    def test_los_espacios_de_en_medio_se_colapsan_pero_no_se_inventan(self) -> None:
        q = pregunta(QuestionType.FILL_BLANK, correct_text_answer="puertos y adaptadores")

        assert (
            grade_answer(q, respuesta(q, text_answer="puertos   y  adaptadores")).is_correct is True
        )
        # Pegar dos palabras no es lo mismo que separarlas.
        assert grade_answer(q, respuesta(q, text_answer="puertosy adaptadores")).is_correct is False

    def test_ignora_las_tildes(self) -> None:
        # Olvidar una tilde en un teclado ajeno no mide lo que se quiere medir.
        q = pregunta(QuestionType.FILL_BLANK, correct_text_answer="arquitectura")

        assert grade_answer(q, respuesta(q, text_answer="Arquitéctura")).is_correct is True

    def test_la_enie_se_conserva(self) -> None:
        # `año` y `ano` son palabras distintas.
        q = pregunta(QuestionType.FILL_BLANK, correct_text_answer="año")

        assert grade_answer(q, respuesta(q, text_answer="año")).is_correct is True
        assert grade_answer(q, respuesta(q, text_answer="AÑO")).is_correct is True
        assert grade_answer(q, respuesta(q, text_answer="ano")).is_correct is False

    def test_una_palabra_distinta_falla(self) -> None:
        q = pregunta(QuestionType.FILL_BLANK, correct_text_answer="hexagonal")

        assert grade_answer(q, respuesta(q, text_answer="monolitica")).is_correct is False


class TestDesarrollo:
    def test_no_se_califica_solo_y_no_es_un_cero(self) -> None:
        q = pregunta(QuestionType.ESSAY, puntos=5)

        resultado = grade_answer(q, respuesta(q, text_answer="Mi respuesta"))

        assert resultado.is_correct is None
        assert resultado.points is None

    def test_tampoco_si_no_lo_respondio(self) -> None:
        q = pregunta(QuestionType.ESSAY, puntos=5)

        assert grade_answer(q, None).points is None


def test_una_pregunta_sin_responder_vale_cero() -> None:
    q = opcion_multiple()

    resultado = grade_answer(q, None)

    assert resultado.is_correct is False
    assert resultado.points == Decimal(0)


class TestExamenCompleto:
    def test_suma_lo_ganado_y_el_maximo(self) -> None:
        a = opcion_multiple()
        b = pregunta(QuestionType.NUMERIC, puntos=3, correct_numeric_answer=Decimal(7))

        nota = score_exam(
            [a, b],
            [
                respuesta(a, selected_option_id=a.options[0].id),
                respuesta(b, numeric_answer=Decimal(8)),
            ],
        )

        assert nota.earned == Decimal(2)
        assert nota.maximum == Decimal(5)
        assert nota.pending_manual is False

    def test_con_un_desarrollo_la_nota_es_parcial(self) -> None:
        a = opcion_multiple()
        ensayo = pregunta(QuestionType.ESSAY, puntos=5)

        nota = score_exam(
            [a, ensayo],
            [
                respuesta(a, selected_option_id=a.options[0].id),
                respuesta(ensayo, text_answer="Texto"),
            ],
        )

        assert nota.earned == Decimal(2)
        # El maximo incluye el desarrollo: la nota es "2 de 7, y falta uno".
        assert nota.maximum == Decimal(7)
        assert nota.pending_manual is True

    def test_solo_registra_las_preguntas_que_se_contestaron(self) -> None:
        a = opcion_multiple()
        b = opcion_multiple()

        nota = score_exam([a, b], [respuesta(a, selected_option_id=a.options[0].id)])

        assert set(nota.by_question) == {a.id}
        assert nota.maximum == Decimal(4)

    def test_un_examen_sin_preguntas_vale_cero(self) -> None:
        nota = score_exam([], [])

        assert nota.earned == Decimal(0)
        assert nota.maximum == Decimal(0)


class TestNormalizar:
    def test_conserva_la_enie_y_quita_el_resto_de_tildes(self) -> None:
        assert normalize_text("  Ñandú   ESPAÑA ") == "ñandu españa"
