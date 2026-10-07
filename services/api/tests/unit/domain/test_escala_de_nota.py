"""La nota se reparte sobre la escala del examen.

En Perú se califica sobre 20, pero el docente pone a cada pregunta los puntos que
quiera: 2 a una difícil y 1 a una fácil. Repartir proporcionalmente es lo que le
evita hacer cuentas para que sumen exactamente 20.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from proctoring_api.domain.grading import ExamScore

VEINTE = Decimal(20)


def nota(ganados: str, total: str, escala: Decimal = VEINTE) -> Decimal:
    marcador = ExamScore(
        earned=Decimal(ganados),
        maximum=Decimal(total),
        pending_manual=False,
        by_question={},
    )
    return marcador.on_scale(escala)


def test_todo_bien_es_la_nota_maxima() -> None:
    assert nota("10", "10") == Decimal(20)


def test_nada_bien_es_cero() -> None:
    assert nota("0", "10") == Decimal(0)


def test_la_mitad_es_la_mitad_de_la_escala() -> None:
    assert nota("5", "10") == Decimal(10)


def test_los_puntos_desiguales_se_reparten_proporcionalmente() -> None:
    """Dos preguntas de 2 puntos y una de 1; acierta las dos de 2."""
    assert nota("4", "5") == Decimal(16)


def test_se_redondea_a_dos_decimales() -> None:
    """13.33 y no 13: un tercio de la nota es un tercio, no se tira el resto."""
    assert nota("1", "3") == Decimal("6.67")


def test_el_redondeo_es_el_de_siempre_no_el_del_banquero() -> None:
    """Python redondea 0.5 al par más cercano por defecto, que sorprende a
    cualquiera que compruebe una nota a mano."""
    # 2.5 sobre 20 con máximo 4 -> 12.5, exacto. Buscamos un caso con .005:
    assert nota("1", "8", Decimal(1)) == Decimal("0.13")  # 0.125 -> 0.13, no 0.12


def test_una_escala_distinta_de_veinte_tambien_funciona() -> None:
    """La escala es del examen, no una constante escondida."""
    assert nota("5", "10", Decimal(100)) == Decimal(50)
    assert nota("5", "10", Decimal(5)) == Decimal("2.50")


def test_un_examen_sin_puntos_no_divide_por_cero() -> None:
    """Todas las preguntas valen cero, o no hay preguntas."""
    assert nota("0", "0") == Decimal(0)


def test_la_nota_nunca_pasa_de_la_escala() -> None:
    for ganados, total in (("1", "1"), ("7", "7"), ("3", "10")):
        assert nota(ganados, total) <= VEINTE


@pytest.mark.parametrize("escala", [Decimal(20), Decimal(10), Decimal(100), Decimal("12.5")])
def test_cero_siempre_es_cero_en_cualquier_escala(escala: Decimal) -> None:
    assert nota("0", "10", escala) == Decimal(0)


def test_una_nota_parcial_sigue_siendo_parcial() -> None:
    """Con desarrollos sin corregir, lo ganado es parcial: la escala no inventa
    los puntos que faltan."""
    marcador = ExamScore(
        earned=Decimal(5),
        maximum=Decimal(10),
        pending_manual=True,
        by_question={},
    )

    assert marcador.on_scale(VEINTE) == Decimal(10)
    assert marcador.pending_manual is True
