"""Pruebas de la política del autoescalador (sin Docker: la lógica es pura)."""

from autoescalador import (
    ENFRIAR_TRAS_BAJAR_S,
    ENFRIAR_TRAS_SUBIR_S,
    VENTANA_BAJAR,
    VENTANA_SUBIR,
    Estado,
    Politica,
)


def estado() -> Estado:
    return Estado(Politica(minimo=2, maximo=5, subir=70, bajar=25))


def test_una_rafaga_corta_no_sube() -> None:
    e = estado()
    assert e.decidir(0, 2, 95) == 2
    assert e.decidir(15, 2, 20) == 2
    assert e.decidir(30, 2, 95) == 2


def test_carga_sostenida_sube_una() -> None:
    e = estado()
    resultados = [e.decidir(t * 15, 2, 90) for t in range(VENTANA_SUBIR)]
    assert resultados[-1] == 3


def test_espera_tras_subir_antes_de_volver_a_subir() -> None:
    e = estado()
    for t in range(VENTANA_SUBIR):
        e.decidir(t * 15, 2, 90)
    e.aplicado(30)
    # Tras subir se olvida lo medido: hacen falta otras 3 mediciones con la
    # réplica nueva, y que pasen 45 s, para volver a subir.
    seguidos = [e.decidir(30 + (i + 1) * 15, 3, 90) for i in range(VENTANA_SUBIR)]
    assert seguidos == [3, 3, 4]
    assert VENTANA_SUBIR * 15 >= ENFRIAR_TRAS_SUBIR_S


def test_no_pasa_del_maximo() -> None:
    e = estado()
    assert all(e.decidir(t * 60, 5, 99) == 5 for t in range(10))


def test_baja_solo_tras_rato_largo_en_calma() -> None:
    e = estado()
    pasos = [e.decidir(ENFRIAR_TRAS_BAJAR_S + t * 15, 4, 10) for t in range(VENTANA_BAJAR)]
    assert pasos[:-1] == [4] * (VENTANA_BAJAR - 1)
    assert pasos[-1] == 3


def test_un_pico_en_la_calma_impide_bajar() -> None:
    e = estado()
    cargas = [10] * (VENTANA_BAJAR - 1) + [40]
    pasos = [e.decidir(ENFRIAR_TRAS_BAJAR_S + t * 15, 4, c) for t, c in enumerate(cargas)]
    assert pasos[-1] == 4


def test_no_baja_del_minimo_y_repone_si_falta() -> None:
    e = estado()
    assert all(e.decidir(1000 + t * 15, 2, 0) == 2 for t in range(VENTANA_BAJAR * 2))
    assert estado().decidir(0, 1, 50) == 2
