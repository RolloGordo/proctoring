"""Pruebas de caja blanca de las reglas críticas del dominio (27/11/2026).

Se diseñan **mirando el código**: para cada función se cuenta su complejidad
ciclomática V(G) = decisiones + 1 y se escribe un caso por camino independiente
(caminos básicos), más los bucles (cero, una y varias vueltas) y las condiciones
compuestas por separado. Así ninguna rama queda sin ejecutar ni ningún umbral sin
probar justo en su valor.

Funciones elegidas por lo que deciden sobre una persona: la severidad de cada
señal, el riesgo, qué episodios cuentan, qué preguntas le tocan a cada estudiante,
cómo se califica y el límite de peticiones.

Corre con el entorno de la API (`services/api`). Docstring: `ID | técnica | camino`.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "api" / "src"))

from proctoring_api.adapters.inbound.http.rate_limit import Limite, VentanaDeslizante  # noqa: E402
from proctoring_api.domain.answer import Answer  # noqa: E402
from proctoring_api.domain.event import EventType, ProctoringEvent, one_per_episode  # noqa: E402
from proctoring_api.domain.grading import ExamScore, grade_answer, normalize_text, score_exam  # noqa: E402
from proctoring_api.domain.question import Question, QuestionOption, QuestionType  # noqa: E402
from proctoring_api.domain.question_bank import draw_questions  # noqa: E402
from proctoring_api.domain.risk import (  # noqa: E402
    HIGH_FROM,
    MAX_POINTS_PER_SIGNAL,
    MAX_SCORE,
    MEDIUM_FROM,
    RiskLevel,
    assess_risk,
    risk_level,
)
from proctoring_api.domain.severity import Severity, default_severity  # noqa: E402

AHORA = datetime(2026, 11, 27, 15, 0, tzinfo=UTC)
SESION, ALUMNO, PREGUNTA = uuid4(), uuid4(), uuid4()
T = EventType


def ev(tipo: EventType, ms: int = 0, episodio: object = None) -> ProctoringEvent:
    meta = {} if episodio is None else {"episode_id": episodio}
    return ProctoringEvent.create(session_id=SESION, student_id=ALUMNO, question_id=PREGUNTA, event_type=tipo, started_at=AHORA, duration_ms=ms, metadata=meta)


# =================================================================== default_severity
# V(G) = 17: 11 ramas del match + 6 `if` de duración. Un caso por camino.

CAMINOS_SEVERIDAD = [
    ("C1", T.EXTRA_PERSON, 0, Severity.HIGH),
    ("C2", T.SUSPICIOUS_PROCESS, 0, Severity.HIGH),
    ("C3", T.SCREEN_SHARE, 0, Severity.HIGH),
    ("C4", T.PROHIBITED_OBJECT, 0, Severity.MEDIUM),
    ("C5", T.FRAMING_LOST, 30_000, Severity.MEDIUM),
    ("C6", T.FRAMING_LOST, 29_999, Severity.LOW),
    ("C7", T.COPY_ATTEMPT, 0, Severity.MEDIUM),
    ("C8", T.EXTRA_DISPLAY, 0, Severity.MEDIUM),
    ("C9", T.FOCUS_LOST, 30_000, Severity.HIGH),
    ("C10", T.FOCUS_LOST, 29_999, Severity.MEDIUM),
    ("C11", T.FOCUS_LOST, 5_000, Severity.MEDIUM),
    ("C12", T.FOCUS_LOST, 4_999, Severity.LOW),
    ("C13", T.FACE_ABSENT, 15_000, Severity.HIGH),
    ("C14", T.FACE_ABSENT, 14_999, Severity.MEDIUM),
    ("C15", T.FACE_ABSENT, 4_999, Severity.LOW),
    ("C16", T.GAZE_AWAY, 10_000, Severity.MEDIUM),
    ("C17", T.GAZE_AWAY, 9_999, Severity.LOW),
    ("C18", T.SPEECH_DETECTED, 0, Severity.MEDIUM),
    ("C19", T.IDENTITY_CHECK, 0, Severity.LOW),
]


@pytest.mark.parametrize(("camino", "tipo", "ms", "esperada"), CAMINOS_SEVERIDAD, ids=[c[0] for c in CAMINOS_SEVERIDAD])
def test_cb01_severidad_todos_los_caminos(camino: str, tipo: EventType, ms: int, esperada: Severity) -> None:
    """CB-01 | Caminos básicos | default_severity (V(G)=17): cada rama del match y cada umbral de duración, en el valor exacto y en el anterior."""
    assert default_severity(tipo, ms) is esperada


def test_cb02_severidad_cubre_todo_el_catalogo() -> None:
    """CB-02 | Cobertura de decisiones | Ningún tipo del enum event_type cae fuera del match (no hay camino que devuelva None)."""
    for tipo in EventType:
        assert isinstance(default_severity(tipo, 0), Severity)
        assert isinstance(default_severity(tipo, 10**9), Severity)


# =================================================================== risk_level


@pytest.mark.parametrize(("puntos", "nivel"), [(0, RiskLevel.LOW), (MEDIUM_FROM - 1, RiskLevel.LOW), (MEDIUM_FROM, RiskLevel.MEDIUM), (HIGH_FROM - 1, RiskLevel.MEDIUM), (HIGH_FROM, RiskLevel.HIGH), (MAX_SCORE, RiskLevel.HIGH)])
def test_cb03_nivel_de_riesgo(puntos: int, nivel: RiskLevel) -> None:
    """CB-03 | Caminos básicos | risk_level (V(G)=3): los dos `if` en su límite (15 y 40) y el camino final."""
    assert risk_level(puntos) is nivel


# =================================================================== assess_risk


def test_cb04_riesgo_sin_eventos() -> None:
    """CB-04 | Bucles (0 vueltas) | Sin eventos, el bucle no entra: riesgo 0, nivel bajo y sin señales."""
    r = assess_risk([])
    assert (r.score, r.level, r.signals) == (0, RiskLevel.LOW, ())


def test_cb05_riesgo_una_senal() -> None:
    """CB-05 | Bucles (1 vuelta) | Una señal alta suma 25: riesgo medio con una sola señal en el desglose."""
    r = assess_risk([ev(T.EXTRA_PERSON)])
    assert r.score == 25 and r.level is RiskLevel.MEDIUM and len(r.signals) == 1


def test_cb06_tope_por_senal() -> None:
    """CB-06 | Cobertura de condición (min por señal) | 100 salidas breves (1 punto cada una) se topan en 50: un tipo de señal no pesa más que MAX_POINTS_PER_SIGNAL."""
    r = assess_risk([ev(T.FOCUS_LOST, 1000) for _ in range(100)])
    assert r.signals[0].points == MAX_POINTS_PER_SIGNAL and r.signals[0].count == 100


def test_cb07_tope_total() -> None:
    """CB-07 | Cobertura de condición (min total) | Cuatro tipos de señal alta (4 × 50) se topan en 100."""
    eventos = [ev(t) for t in (T.EXTRA_PERSON, T.SUSPICIOUS_PROCESS, T.SCREEN_SHARE) for _ in range(2)] + [ev(T.FACE_ABSENT, 20_000) for _ in range(2)]
    r = assess_risk(eventos)
    assert sum(s.points for s in r.signals) == 200 and r.score == MAX_SCORE


def test_cb08_desglose_ordenado_y_maxima_severidad() -> None:
    """CB-08 | Caminos básicos | El desglose va de mayor a menor aporte (empate por nombre) y cada señal guarda su severidad máxima."""
    r = assess_risk([ev(T.FOCUS_LOST, 1000), ev(T.FOCUS_LOST, 40_000), ev(T.EXTRA_DISPLAY), ev(T.COPY_ATTEMPT)])
    assert [s.event_type for s in r.signals] == [T.FOCUS_LOST, T.COPY_ATTEMPT, T.EXTRA_DISPLAY]
    assert r.signals[0].max_severity is Severity.HIGH and r.signals[0].points == 26
    assert r.signals[0].total_duration_ms == 41_000


# =================================================================== one_per_episode


def test_cb09_episodio_cuenta_una_vez() -> None:
    """CB-09 | Caminos básicos | Tres informes del mismo episodio cuentan una vez, con el más largo (rama `duration_ms > current`)."""
    a, b, c = ev(T.FACE_ABSENT, 5_000, "e1"), ev(T.FACE_ABSENT, 16_000, "e1"), ev(T.FACE_ABSENT, 9_000, "e1")
    assert one_per_episode([a, b, c]) == [b]
    assert assess_risk([a, b, c]).score == 25


def test_cb10_sin_episodio_pasan_todos() -> None:
    """CB-10 | Caminos básicos | Eventos sin episode_id toman la rama `continue` y pasan todos, en su orden."""
    xs = [ev(T.FOCUS_LOST, 1000), ev(T.FOCUS_LOST, 2000)]
    assert one_per_episode(xs) == xs


def test_cb11_empate_conserva_el_primero() -> None:
    """CB-11 | Cobertura de condición | Con la misma duración, la condición estricta (>) conserva el primer informe."""
    a, b = ev(T.GAZE_AWAY, 12_000, "e"), ev(T.GAZE_AWAY, 12_000, "e")
    assert one_per_episode([a, b]) == [a]


def test_cb12_mismo_episodio_distinto_tipo() -> None:
    """CB-12 | Cobertura de condición | La clave es (tipo, episodio): el mismo id en dos tipos son dos episodios."""
    a, b = ev(T.GAZE_AWAY, 12_000, "e"), ev(T.FACE_ABSENT, 6_000, "e")
    assert one_per_episode([a, b]) == [a, b]


@pytest.mark.parametrize("raro", ["", "x" * 65, 123, ["e"]])
def test_cb13_episode_id_invalido_se_ignora(raro: object) -> None:
    """CB-13 | Cobertura de condición | Un episode_id vacío, de más de 64 caracteres o que no es texto se ignora: cada informe cuenta (no se pierde una señal)."""
    xs = [ev(T.FACE_ABSENT, 6_000, raro), ev(T.FACE_ABSENT, 7_000, raro)]
    assert one_per_episode(xs) == xs


# =================================================================== draw_questions


def preguntas(n: int) -> list[Question]:
    return [
        Question.create(session_id=SESION, position=i, question_type=QuestionType.NUMERIC, statement=f"P{i}", points=Decimal(1), correct_numeric_answer=Decimal(i))
        for i in range(1, n + 1)
    ]


def test_cb14_sin_preguntas() -> None:
    """CB-14 | Caminos básicos | Lista vacía: sale por el primer `if` y devuelve []."""
    assert draw_questions([], session_id=SESION, participant_id=ALUMNO, pool_size=3, shuffle=True) == []


@pytest.mark.parametrize("pool", [None, 0, 8, 20])
def test_cb15_pool_que_no_recorta(pool: int | None) -> None:
    """CB-15 | Cobertura de condición | `pool_size is not None and 0 < pool < len`: con None, 0, igual o mayor al total, cada sub-condición falsa da todas en orden."""
    qs = preguntas(8)
    assert draw_questions(qs, session_id=SESION, participant_id=ALUMNO, pool_size=pool) == sorted(qs, key=lambda q: q.position)


def test_cb16_pool_recorta_y_conserva_orden() -> None:
    """CB-16 | Caminos básicos | Con 0 < pool < total: sortea exactamente pool preguntas y las devuelve en el orden del docente."""
    elegidas = draw_questions(preguntas(8), session_id=SESION, participant_id=ALUMNO, pool_size=3)
    assert len(elegidas) == 3 and [q.position for q in elegidas] == sorted(q.position for q in elegidas)


def test_cb17_mezcla_determinista_por_matricula() -> None:
    """CB-17 | Caminos básicos | Con shuffle: el mismo estudiante recibe siempre el mismo orden (recarga) y otro estudiante uno distinto."""
    qs = preguntas(10)
    uno = [q.id for q in draw_questions(qs, session_id=SESION, participant_id=ALUMNO, shuffle=True)]
    otra_vez = [q.id for q in draw_questions(list(reversed(qs)), session_id=SESION, participant_id=ALUMNO, shuffle=True)]
    otros = {tuple(q.id for q in draw_questions(qs, session_id=SESION, participant_id=uuid4(), shuffle=True)) for _ in range(5)}
    assert uno == otra_vez
    assert len(otros | {tuple(uno)}) > 1


def test_cb18_mezcla_no_altera_la_entrada() -> None:
    """CB-18 | Caminos básicos | Rama shuffle sin pool: baraja una copia; la lista del llamador queda intacta."""
    qs = preguntas(6)
    copia = list(qs)
    draw_questions(qs, session_id=SESION, participant_id=ALUMNO, shuffle=True)
    assert qs == copia


# =================================================================== calificación


def q(tipo: QuestionType, **extra: object) -> Question:
    return Question.create(session_id=SESION, position=1, question_type=tipo, statement="E", points=Decimal(2), **extra)  # type: ignore[arg-type]


def r(preg: Question, **campos: object) -> Answer:
    return Answer(id=uuid4(), participant_id=ALUMNO, question_id=preg.id, answered_at=AHORA, **campos)  # type: ignore[arg-type]


def opciones(*correctas: bool) -> list[tuple[str, bool]]:
    return [(f"o{i}", c) for i, c in enumerate(correctas)]


def test_cb19_desarrollo_queda_para_el_docente() -> None:
    """CB-19 | Caminos básicos | grade_answer, rama MANUAL_TYPES: un desarrollo no se califica solo (None) y deja la nota pendiente."""
    d = q(QuestionType.ESSAY)
    assert grade_answer(d, r(d, text_answer="mi ensayo")).points is None
    assert score_exam([d], [r(d, text_answer="x")]).pending_manual is True


def test_cb20_sin_respuesta_vale_cero() -> None:
    """CB-20 | Caminos básicos | grade_answer con answer None: rama `else False`, cero puntos sin llamar a _is_correct."""
    m = q(QuestionType.MULTIPLE_CHOICE, options=opciones(True, False))
    g = grade_answer(m, None)
    assert g.is_correct is False and g.points == 0


@pytest.mark.parametrize(("elegida", "ok"), [(0, True), (1, False), (None, False)])
def test_cb21_opcion_unica(elegida: int | None, ok: bool) -> None:
    """CB-21 | Cobertura de condición | `chosen is not None and chosen.is_correct`: correcta, incorrecta y opción inexistente."""
    m = q(QuestionType.MULTIPLE_CHOICE, options=opciones(True, False))
    sel = m.options[elegida].id if elegida is not None else uuid4()
    assert grade_answer(m, r(m, selected_option_id=sel)).is_correct is ok


@pytest.mark.parametrize(("marcadas", "ok"), [((0, 1), True), ((0,), False), ((0, 1, 2), False), ((), False)])
def test_cb22_varias_correctas(marcadas: tuple[int, ...], ok: bool) -> None:
    """CB-22 | Cobertura de condición | MULTIPLE_SELECT todo o nada: exactamente las correctas, quedarse corto, marcarlo todo y no marcar nada."""
    m = q(QuestionType.MULTIPLE_SELECT, options=opciones(True, True, False))
    assert grade_answer(m, r(m, selected_option_ids=tuple(m.options[i].id for i in marcadas))).is_correct is ok


def test_cb23_varias_sin_ninguna_correcta() -> None:
    """CB-23 | Cobertura de condición | `bool(correctas)` falso: una pregunta mal armada sin correctas nunca da puntos, ni marcando nada."""
    m = Question(id=uuid4(), session_id=SESION, bank_id=None, position=1, question_type=QuestionType.MULTIPLE_SELECT, statement="E", points=Decimal(2), options=tuple(QuestionOption(id=uuid4(), position=i, option_text=f"o{i}", is_correct=False) for i in range(2)))
    assert grade_answer(m, r(m, selected_option_ids=())).is_correct is False


@pytest.mark.parametrize(("valor", "tol", "ok"), [("10", None, True), ("10.5", "0.5", True), ("10.51", "0.5", False), ("9.5", "0.5", True), (None, None, False)])
def test_cb24_numerica(valor: str | None, tol: str | None, ok: bool) -> None:
    """CB-24 | Caminos básicos | NUMERIC: sin respuesta, exacta sin tolerancia, en el borde superior e inferior de la tolerancia y fuera por 0,01."""
    n = q(QuestionType.NUMERIC, correct_numeric_answer=Decimal("10"), numeric_tolerance=Decimal(tol) if tol else None)
    assert grade_answer(n, r(n, numeric_answer=Decimal(valor) if valor else None)).is_correct is ok


@pytest.mark.parametrize(("texto", "ok"), [("  Árbol   binario ", True), ("ARBOL BINARIO", True), ("año", False), (None, False)])
def test_cb25_completar(texto: str | None, ok: bool) -> None:
    """CB-25 | Caminos básicos | FILL_BLANK con normalize_text: ignora tildes, mayúsculas y espacios; conserva la ñ (año ≠ ano)."""
    f = q(QuestionType.FILL_BLANK, correct_text_answer="árbol binario")
    assert grade_answer(f, r(f, text_answer=texto)).is_correct is ok
    a = q(QuestionType.FILL_BLANK, correct_text_answer="ano")
    assert grade_answer(a, r(a, text_answer="año")).is_correct is False


def test_cb26_normalizar_texto() -> None:
    """CB-26 | Caminos básicos | normalize_text: el bucle de caracteres descarta tildes (combining) salvo la tilde de la ñ."""
    assert normalize_text("  Canción  ÑANDÚ ") == "cancion ñandu"


@pytest.mark.parametrize(("ganado", "maximo", "esperada"), [("0", "0", "0"), ("1", "3", "6.67"), ("1", "8", "2.50"), ("2", "3", "13.33")])
def test_cb27_escala_sobre_20(ganado: str, maximo: str, esperada: str) -> None:
    """CB-27 | Caminos básicos | ExamScore.on_scale: rama `maximum <= 0` (sin dividir por cero) y redondeo HALF_UP a dos decimales."""
    s = ExamScore(earned=Decimal(ganado), maximum=Decimal(maximo), pending_manual=False, by_question={})
    assert s.on_scale(Decimal(20)) == Decimal(esperada)


def test_cb28_score_exam_registra_solo_lo_respondido() -> None:
    """CB-28 | Bucles | score_exam recorre todas las preguntas para el máximo, pero solo registra corrección de las que tienen respuesta."""
    a, b = q(QuestionType.NUMERIC, correct_numeric_answer=Decimal(1)), q(QuestionType.NUMERIC, correct_numeric_answer=Decimal(2))
    s = score_exam([a, b], [r(a, numeric_answer=Decimal(1))])
    assert (s.earned, s.maximum, list(s.by_question)) == (Decimal(2), Decimal(4), [a.id])


# =================================================================== límite de peticiones


def test_cb29_ventana_admite_hasta_el_limite() -> None:
    """CB-29 | Caminos básicos | VentanaDeslizante.admite: rama «hay sitio» las primeras N veces y rama «lleno» en la N+1, con espera ≥ 1 s."""
    v, lim = VentanaDeslizante(), Limite(3, 60)
    with patch("time.monotonic", return_value=1000.0):
        assert [v.admite("k", lim)[0] for _ in range(3)] == [True] * 3
        ok, espera = v.admite("k", lim)
    assert ok is False and 1 <= espera <= 61


def test_cb30_ventana_descarta_lo_viejo() -> None:
    """CB-30 | Bucles | El `while` que descarta marcas fuera de la ventana: pasado el minuto vuelve a admitir."""
    v, lim = VentanaDeslizante(), Limite(2, 60)
    with patch("time.monotonic", return_value=1000.0):
        v.admite("k", lim)
        v.admite("k", lim)
        assert v.admite("k", lim)[0] is False
    with patch("time.monotonic", return_value=1060.5):
        assert v.admite("k", lim)[0] is True


def test_cb31_ventana_por_clave() -> None:
    """CB-31 | Caminos básicos | Cada clave (persona) tiene su ventana: agotar la de una no afecta a otra."""
    v, lim = VentanaDeslizante(), Limite(1, 60)
    with patch("time.monotonic", return_value=5.0):
        assert v.admite("a", lim)[0] is True and v.admite("a", lim)[0] is False
        assert v.admite("b", lim)[0] is True


def test_cb32_semilla_estable() -> None:
    """CB-32 | Caminos básicos | La semilla del sorteo no depende de PYTHONHASHSEED: los mismos ids dan el mismo examen entre procesos."""
    import subprocess

    ids = (UUID("11111111-1111-4111-8111-111111111111"), UUID("22222222-2222-4222-8222-222222222222"))
    codigo = (
        "import sys;sys.path.insert(0,%r);from proctoring_api.domain.question_bank import _semilla;"
        "from uuid import UUID;print(_semilla(UUID(%r),UUID(%r)))" % (str(Path(__file__).resolve().parents[2] / "services" / "api" / "src"), str(ids[0]), str(ids[1]))
    )
    salidas = {subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, env={**__import__("os").environ, "PYTHONHASHSEED": s}, check=True).stdout for s in ("1", "2")}
    assert len(salidas) == 1


def test_cb33_ventana_libera_claves_vencidas() -> None:
    """CB-33 | Cobertura de sentencias | La rama que borra las claves vacías (para que el diccionario no crezca con cada IP) tiene que poder ejecutarse: tras vencer la ventana, las claves de quien no volvió se liberan."""
    v, lim = VentanaDeslizante(), Limite(10, 60)
    with patch("time.monotonic", return_value=0.0):
        for i in range(500):
            v.admite(f"ip-{i}", lim)
    with patch("time.monotonic", return_value=500.0):
        v.admite("ip-nueva", lim)
        v.admite("ip-0", lim)
    vivas = len(v._marcas)
    assert vivas < 500, (
        f"quedan {vivas} claves: el `if not marcas: del ...` va después de `marcas.append(ahora)`, nunca es verdadero, "
        "y las claves de quien ya no vuelve no se liberan nunca"
    )


# =================================================================== casos añadidos tras la mutación
# La primera corrida de mutmut dejó vivos mutantes que estas pruebas no veían.


def test_cb34_pool_de_una_pregunta() -> None:
    """CB-34 | Valor límite (de mutación) | Un pool de exactamente 1 sortea 1 pregunta: el límite inferior de `0 < pool_size` (un `1 <` sobrevivía)."""
    assert len(draw_questions(preguntas(5), session_id=SESION, participant_id=ALUMNO, pool_size=1)) == 1


def test_cb35_desempate_por_id_con_posiciones_iguales() -> None:
    """CB-35 | Caminos básicos (de mutación) | Dos bancos pueden repetir posiciones: con posiciones iguales el orden se desempata por id y no depende del orden de llegada."""
    qs = [
        Question.create(session_id=SESION, position=1, question_type=QuestionType.NUMERIC, statement=f"P{i}", points=Decimal(1), correct_numeric_answer=Decimal(i))
        for i in range(6)
    ]
    for pool in (None, 3):
        a = [q.id for q in draw_questions(qs, session_id=SESION, participant_id=ALUMNO, pool_size=pool)]
        b = [q.id for q in draw_questions(list(reversed(qs)), session_id=SESION, participant_id=ALUMNO, pool_size=pool)]
        assert a == b
    assert [q.id for q in draw_questions(qs, session_id=SESION, participant_id=ALUMNO)] == sorted((q.id for q in qs), key=str)


@pytest.mark.parametrize(("texto", "esperado"), [("São Tomé", "sao tome"), ("ńandu", "nandu"), ("Peña", "peña")])
def test_cb36_solo_la_tilde_de_la_ene(texto: str, esperado: str) -> None:
    """CB-36 | Cobertura de condición (de mutación) | `char == tilde and kept and kept[-1] == 'n'`: la tilde se quita sobre otras letras (ã) y otros acentos sobre la n se quitan (ń); solo sobrevive la de la ñ."""
    assert normalize_text(texto) == esperado


def test_cb37_correccion_por_pregunta() -> None:
    """CB-37 | Caminos básicos (de mutación) | score_exam guarda, para cada pregunta respondida, su corrección (acierto y puntos), no solo la clave."""
    a = q(QuestionType.NUMERIC, correct_numeric_answer=Decimal(1))
    s = score_exam([a], [r(a, numeric_answer=Decimal(1))])
    g = s.by_question[a.id]
    assert g is not None and g.is_correct is True and g.points == Decimal(2)
