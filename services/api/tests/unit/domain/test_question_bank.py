"""Banco de preguntas y, sobre todo, que el sorteo sea el mismo cada vez."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from proctoring_api.domain.question import Question, QuestionType
from proctoring_api.domain.question_bank import (
    MAX_NAME_LENGTH,
    InvalidQuestionBankError,
    QuestionBank,
    draw_questions,
)

NOW = datetime(2026, 10, 6, 15, 0, tzinfo=UTC)
SESION = UUID("3f1a7c20-9b4e-4d2a-8f6c-1e2d3a4b5c60")
ANA = UUID("7b2e4d10-5c6f-4a8b-9d0e-2f3a4b5c6d71")
LUIS = UUID("1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d")


def banco_de(cantidad: int) -> list[Question]:
    """`cantidad` preguntas con ids estables, para poder comparar entre llamadas."""
    return [
        Question.create(
            session_id=None,
            bank_id=SESION,
            position=i,
            question_type=QuestionType.ESSAY,
            statement=f"Pregunta {i}",
            points=Decimal(1),
            question_id=UUID(int=i),
        )
        for i in range(1, cantidad + 1)
    ]


class TestCrearBanco:
    def test_se_crea_con_nombre_y_sin_curso(self) -> None:
        banco = QuestionBank.create(teacher_id=uuid4(), name="  Bases de datos  ", created_at=NOW)

        assert banco.name == "Bases de datos"
        # Sin curso: sirve para todos los del docente.
        assert banco.course_id is None

    def test_se_puede_atar_a_un_curso(self) -> None:
        curso = uuid4()

        banco = QuestionBank.create(
            teacher_id=uuid4(), name="Parciales", created_at=NOW, course_id=curso
        )

        assert banco.course_id == curso

    def test_un_nombre_vacio_se_rechaza(self) -> None:
        with pytest.raises(InvalidQuestionBankError, match="nombre"):
            QuestionBank.create(teacher_id=uuid4(), name="   ", created_at=NOW)

    def test_un_nombre_enorme_se_rechaza(self) -> None:
        with pytest.raises(InvalidQuestionBankError, match="supera"):
            QuestionBank.create(
                teacher_id=uuid4(), name="a" * (MAX_NAME_LENGTH + 1), created_at=NOW
            )

    def test_exige_zona_horaria(self) -> None:
        with pytest.raises(InvalidQuestionBankError, match="zona horaria"):
            QuestionBank.create(
                teacher_id=uuid4(),
                name="Banco",
                created_at=datetime(2026, 10, 6, 15, 0),
            )


class TestElSorteoEsSiempreElMismo:
    """Lo que pasa si no lo es: el estudiante recarga y pierde el examen."""

    def test_el_mismo_estudiante_recibe_siempre_lo_mismo(self) -> None:
        preguntas = banco_de(100)

        primera = draw_questions(preguntas, session_id=SESION, participant_id=ANA, pool_size=20)
        segunda = draw_questions(preguntas, session_id=SESION, participant_id=ANA, pool_size=20)

        assert [q.id for q in primera] == [q.id for q in segunda]

    def test_tambien_con_el_orden_barajado(self) -> None:
        preguntas = banco_de(100)

        primera = draw_questions(
            preguntas, session_id=SESION, participant_id=ANA, pool_size=20, shuffle=True
        )
        segunda = draw_questions(
            preguntas, session_id=SESION, participant_id=ANA, pool_size=20, shuffle=True
        )

        assert [q.id for q in primera] == [q.id for q in segunda]

    def test_no_depende_del_orden_en_que_lleguen_de_la_base(self) -> None:
        # Un repositorio puede devolverlas en otro orden; el sorteo no puede
        # cambiar por eso.
        preguntas = banco_de(50)

        normal = draw_questions(preguntas, session_id=SESION, participant_id=ANA, pool_size=10)
        revueltas = draw_questions(
            list(reversed(preguntas)), session_id=SESION, participant_id=ANA, pool_size=10
        )

        assert [q.id for q in normal] == [q.id for q in revueltas]

    def test_dos_estudiantes_reciben_conjuntos_distintos(self) -> None:
        preguntas = banco_de(100)

        de_ana = {
            q.id
            for q in draw_questions(preguntas, session_id=SESION, participant_id=ANA, pool_size=20)
        }
        de_luis = {
            q.id
            for q in draw_questions(preguntas, session_id=SESION, participant_id=LUIS, pool_size=20)
        }

        assert de_ana != de_luis

    def test_el_mismo_estudiante_en_otro_examen_recibe_otro_conjunto(self) -> None:
        preguntas = banco_de(100)
        otra_sesion = uuid4()

        aqui = {
            q.id
            for q in draw_questions(preguntas, session_id=SESION, participant_id=ANA, pool_size=20)
        }
        alla = {
            q.id
            for q in draw_questions(
                preguntas, session_id=otra_sesion, participant_id=ANA, pool_size=20
            )
        }

        assert aqui != alla


class TestCuantasRecibe:
    def test_entrega_exactamente_las_pedidas(self) -> None:
        assert (
            len(draw_questions(banco_de(100), session_id=SESION, participant_id=ANA, pool_size=20))
            == 20
        )

    def test_sin_tope_entrega_todas(self) -> None:
        assert len(draw_questions(banco_de(30), session_id=SESION, participant_id=ANA)) == 30

    def test_pedir_mas_de_las_que_hay_entrega_todas_sin_fallar(self) -> None:
        # Un examen no puede quedarse sin preguntas porque el docente puso un
        # numero mayor que su banco.
        assert (
            len(draw_questions(banco_de(5), session_id=SESION, participant_id=ANA, pool_size=20))
            == 5
        )

    def test_pedir_exactamente_las_que_hay_las_entrega_todas(self) -> None:
        assert (
            len(draw_questions(banco_de(20), session_id=SESION, participant_id=ANA, pool_size=20))
            == 20
        )

    def test_un_banco_vacio_no_revienta(self) -> None:
        assert draw_questions([], session_id=SESION, participant_id=ANA, pool_size=20) == []

    def test_nunca_repite_una_pregunta(self) -> None:
        elegidas = draw_questions(
            banco_de(100), session_id=SESION, participant_id=ANA, pool_size=20
        )

        assert len({q.id for q in elegidas}) == 20


class TestElOrden:
    def test_sin_barajar_se_respeta_la_posicion(self) -> None:
        elegidas = draw_questions(banco_de(10), session_id=SESION, participant_id=ANA)

        assert [q.position for q in elegidas] == sorted(q.position for q in elegidas)

    def test_tras_sortear_tambien(self) -> None:
        # Sortear y barajar son dos decisiones distintas: el docente puede querer
        # una sin la otra.
        elegidas = draw_questions(
            banco_de(100), session_id=SESION, participant_id=ANA, pool_size=20
        )

        assert [q.position for q in elegidas] == sorted(q.position for q in elegidas)

    def test_barajar_cambia_el_orden_pero_no_el_conjunto(self) -> None:
        preguntas = banco_de(30)

        en_orden = draw_questions(preguntas, session_id=SESION, participant_id=ANA)
        barajadas = draw_questions(preguntas, session_id=SESION, participant_id=ANA, shuffle=True)

        assert {q.id for q in en_orden} == {q.id for q in barajadas}
        assert [q.id for q in en_orden] != [q.id for q in barajadas]

    def test_barajar_no_muta_la_lista_que_recibe(self) -> None:
        preguntas = banco_de(20)
        antes = [q.id for q in preguntas]

        draw_questions(preguntas, session_id=SESION, participant_id=ANA, shuffle=True)

        assert [q.id for q in preguntas] == antes
