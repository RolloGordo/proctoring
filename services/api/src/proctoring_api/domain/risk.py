"""Nivel de riesgo de un estudiante en un examen, desglosado por señal.

El sistema **no decide**: calcula cuánta atención merece un caso y **por qué**. El
desglose importa más que el número, porque un docente que ve "riesgo 62" sin saber
de dónde sale no puede confiar en él ni discutirlo. Cada punto se explica con una
señal concreta.

La regla es deliberadamente simple y legible:

- cada señal suma puntos según su severidad (la de `severity.py`);
- un mismo **tipo** de señal no puede aportar más de `MAX_POINTS_PER_SIGNAL`: diez
  salidas breves de la ventana no deben pesar como un acceso remoto;
- el total no pasa de 100.

**Los números son un punto de partida razonado, no un resultado medido.** La meta
del proyecto es accuracy >= 80 % y FPR < 20 % por módulo, y eso se consigue
calibrando estos pesos con datos reales. Por eso viven aquí, en un solo sitio,
puros y con pruebas propias: cambiarlos tiene que ser barato.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from proctoring_api.domain.event import EventType, ProctoringEvent
from proctoring_api.domain.severity import Severity, default_severity

#: Cuánto suma una señal según su severidad. Una señal leve casi no pesa; una alta
#: (otra persona, control remoto) pesa lo bastante como para no pasar inadvertida.
SEVERITY_POINTS: dict[Severity, int] = {
    Severity.LOW: 1,
    Severity.MEDIUM: 8,
    Severity.HIGH: 25,
}

#: Tope por tipo de señal. Sin él, repetir una señal leve cientos de veces (un
#: parpadeo de la ventana) llegaría a pesar como un hallazgo grave.
MAX_POINTS_PER_SIGNAL = 50

MAX_SCORE = 100

#: Desde donde el riesgo deja de ser bajo. Con los pesos de arriba, una sola señal
#: alta (25) ya es riesgo medio, y dos tipos distintos de señal alta (50) son alto.
MEDIUM_FROM = 15
HIGH_FROM = 40


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class SignalRisk:
    """Lo que un tipo de señal aporta al riesgo."""

    event_type: EventType
    count: int
    total_duration_ms: int
    points: int
    #: La severidad más alta que alcanzó este tipo de señal.
    max_severity: Severity


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """El riesgo de un estudiante, con su desglose."""

    score: int
    level: RiskLevel
    #: De la señal que más aporta a la que menos. Vacío si no hay señales.
    signals: tuple[SignalRisk, ...]


def risk_level(score: int) -> RiskLevel:
    if score >= HIGH_FROM:
        return RiskLevel.HIGH
    if score >= MEDIUM_FROM:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def assess_risk(events: Sequence[ProctoringEvent]) -> RiskAssessment:
    """Calcula el riesgo a partir de los eventos de un estudiante en una sesión."""
    order = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2}
    grouped: dict[EventType, list[tuple[Severity, int]]] = {}
    for event in events:
        severity = default_severity(event.event_type, event.duration_ms)
        grouped.setdefault(event.event_type, []).append((severity, event.duration_ms))

    signals: list[SignalRisk] = []
    for event_type, items in grouped.items():
        raw_points = sum(SEVERITY_POINTS[severity] for severity, _ in items)
        signals.append(
            SignalRisk(
                event_type=event_type,
                count=len(items),
                total_duration_ms=sum(duration for _, duration in items),
                points=min(raw_points, MAX_POINTS_PER_SIGNAL),
                max_severity=max((s for s, _ in items), key=lambda s: order[s]),
            )
        )

    signals.sort(key=lambda s: (-s.points, s.event_type.value))
    score = min(sum(s.points for s in signals), MAX_SCORE)
    return RiskAssessment(score=score, level=risk_level(score), signals=tuple(signals))
