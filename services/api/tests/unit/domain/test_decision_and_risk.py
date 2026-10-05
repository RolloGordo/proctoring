"""La decisión del docente y el riesgo desglosado por señal."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from proctoring_api.domain.decision import (
    MAX_JUSTIFICATION_LENGTH,
    MIN_JUSTIFICATION_LENGTH,
    Decision,
    DecisionType,
    InvalidDecisionError,
)
from proctoring_api.domain.event import EventType, ProctoringEvent
from proctoring_api.domain.risk import (
    HIGH_FROM,
    MAX_POINTS_PER_SIGNAL,
    MAX_SCORE,
    MEDIUM_FROM,
    RiskLevel,
    assess_risk,
)
from proctoring_api.domain.severity import Severity

NOW = datetime(2026, 10, 5, 15, 0, tzinfo=UTC)


def decidir(justificacion: str, **extra: object) -> Decision:
    return Decision.create(
        session_id=uuid4(),
        student_id=uuid4(),
        teacher_id=uuid4(),
        decision=DecisionType.DISMISSED,
        justification=justificacion,
        decided_at=NOW,
        **extra,  # type: ignore[arg-type]
    )


class TestDecision:
    def test_se_registra_con_una_justificacion_suficiente(self) -> None:
        decision = decidir("El monitor extra es el habitual del estudiante.")

        assert decision.decision is DecisionType.DISMISSED
        assert decision.justification == "El monitor extra es el habitual del estudiante."

    def test_la_justificacion_se_guarda_sin_espacios_de_sobra(self) -> None:
        assert decidir("   Tenia otra explicacion.   ").justification == "Tenia otra explicacion."

    def test_una_justificacion_corta_no_justifica_nada(self) -> None:
        with pytest.raises(InvalidDecisionError, match="al menos"):
            decidir("ok")

    def test_el_minimo_exacto_vale_y_uno_menos_no(self) -> None:
        assert decidir("a" * MIN_JUSTIFICATION_LENGTH)
        with pytest.raises(InvalidDecisionError):
            decidir("a" * (MIN_JUSTIFICATION_LENGTH - 1))

    def test_los_espacios_no_cuentan_para_el_minimo(self) -> None:
        # Diez espacios no son una justificacion. Igual que la restriccion de la
        # base de datos, que mide el texto sin los espacios de los extremos.
        with pytest.raises(InvalidDecisionError):
            decidir(" " * 20)

    def test_no_admite_un_ensayo(self) -> None:
        with pytest.raises(InvalidDecisionError, match="supera"):
            decidir("a" * (MAX_JUSTIFICATION_LENGTH + 1))

    def test_exige_zona_horaria(self) -> None:
        with pytest.raises(InvalidDecisionError, match="zona horaria"):
            Decision.create(
                session_id=uuid4(),
                student_id=uuid4(),
                teacher_id=uuid4(),
                decision=DecisionType.CONFIRMED,
                justification="Evidencia suficiente en la linea de tiempo.",
                decided_at=datetime(2026, 10, 5, 15, 0),
            )

    def test_las_tres_decisiones_existen_y_ninguna_es_automatica(self) -> None:
        # El sistema ofrece las tres; no empuja hacia ninguna.
        assert {d.value for d in DecisionType} == {"confirmed", "dismissed", "retake"}


def evento(tipo: EventType, duracion_ms: int = 0) -> ProctoringEvent:
    return ProctoringEvent.create(
        session_id=uuid4(),
        student_id=uuid4(),
        question_id=None,
        event_type=tipo,
        started_at=NOW,
        duration_ms=duracion_ms,
    )


class TestRiesgo:
    def test_sin_senales_el_riesgo_es_cero_y_bajo(self) -> None:
        riesgo = assess_risk([])

        assert riesgo.score == 0
        assert riesgo.level is RiskLevel.LOW
        assert riesgo.signals == ()

    def test_una_salida_breve_casi_no_pesa(self) -> None:
        riesgo = assess_risk([evento(EventType.FOCUS_LOST, 1_000)])

        assert riesgo.score == 1
        assert riesgo.level is RiskLevel.LOW

    def test_una_senal_alta_ya_es_riesgo_medio(self) -> None:
        riesgo = assess_risk([evento(EventType.SUSPICIOUS_PROCESS)])

        assert riesgo.score >= MEDIUM_FROM
        assert riesgo.level is RiskLevel.MEDIUM

    def test_dos_tipos_distintos_de_senal_alta_son_riesgo_alto(self) -> None:
        riesgo = assess_risk([evento(EventType.SUSPICIOUS_PROCESS), evento(EventType.EXTRA_PERSON)])

        assert riesgo.score >= HIGH_FROM
        assert riesgo.level is RiskLevel.HIGH

    def test_repetir_una_senal_leve_no_llega_a_pesar_como_una_grave(self) -> None:
        # Cien parpadeos de la ventana no son un acceso remoto.
        muchas = [evento(EventType.FOCUS_LOST, 1_000) for _ in range(100)]

        riesgo = assess_risk(muchas)

        assert riesgo.signals[0].points == MAX_POINTS_PER_SIGNAL
        assert riesgo.score == MAX_POINTS_PER_SIGNAL

    def test_el_total_nunca_pasa_de_cien(self) -> None:
        todo = [
            evento(EventType.SUSPICIOUS_PROCESS),
            evento(EventType.SUSPICIOUS_PROCESS),
            evento(EventType.SUSPICIOUS_PROCESS),
            evento(EventType.EXTRA_PERSON),
            evento(EventType.EXTRA_PERSON),
            evento(EventType.SCREEN_SHARE),
            evento(EventType.SCREEN_SHARE),
        ]

        assert assess_risk(todo).score == MAX_SCORE

    def test_el_desglose_explica_de_donde_sale_cada_punto(self) -> None:
        riesgo = assess_risk(
            [
                evento(EventType.SUSPICIOUS_PROCESS),
                evento(EventType.FOCUS_LOST, 2_000),
                evento(EventType.FOCUS_LOST, 40_000),
            ]
        )

        por_tipo = {s.event_type: s for s in riesgo.signals}
        focus = por_tipo[EventType.FOCUS_LOST]
        assert focus.count == 2
        assert focus.total_duration_ms == 42_000
        # Una salida leve (1) y una larga (alta, 25).
        assert focus.points == 26
        assert focus.max_severity is Severity.HIGH
        # El total es la suma de lo que cada senal aporta: nada oculto.
        assert riesgo.score == sum(s.points for s in riesgo.signals)

    def test_el_desglose_va_de_la_senal_que_mas_pesa_a_la_que_menos(self) -> None:
        riesgo = assess_risk(
            [evento(EventType.FOCUS_LOST, 1_000), evento(EventType.SUSPICIOUS_PROCESS)]
        )

        assert [s.event_type for s in riesgo.signals] == [
            EventType.SUSPICIOUS_PROCESS,
            EventType.FOCUS_LOST,
        ]

    def test_hablar_en_voz_alta_no_sube_el_riesgo_por_si_solo(self) -> None:
        # speech_detected es siempre leve: solo la IA, comparando con el enunciado,
        # puede escalarlo. Leer en voz alta para concentrarse es legitimo.
        con_pregunta = ProctoringEvent.create(
            session_id=uuid4(),
            student_id=uuid4(),
            question_id=uuid4(),
            event_type=EventType.SPEECH_DETECTED,
            started_at=NOW,
            duration_ms=8_000,
        )

        riesgo = assess_risk([con_pregunta])

        assert riesgo.level is RiskLevel.LOW
