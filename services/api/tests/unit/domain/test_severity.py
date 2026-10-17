"""Regla pura de severidad por defecto."""

from __future__ import annotations

import pytest

from proctoring_api.domain.event import EventType
from proctoring_api.domain.severity import Severity, default_severity


class TestFocusLost:
    @pytest.mark.parametrize(
        ("duration_ms", "expected"),
        [
            (0, Severity.LOW),
            (4_999, Severity.LOW),
            (5_000, Severity.MEDIUM),
            (29_999, Severity.MEDIUM),
            (30_000, Severity.HIGH),
        ],
    )
    def test_escalates_with_duration(self, duration_ms: int, expected: Severity) -> None:
        assert default_severity(EventType.FOCUS_LOST, duration_ms) is expected


class TestFaceAbsent:
    @pytest.mark.parametrize(
        ("duration_ms", "expected"),
        [
            (4_999, Severity.LOW),
            (5_000, Severity.MEDIUM),
            (15_000, Severity.HIGH),
        ],
    )
    def test_escalates_with_duration(self, duration_ms: int, expected: Severity) -> None:
        assert default_severity(EventType.FACE_ABSENT, duration_ms) is expected


class TestGazeAway:
    @pytest.mark.parametrize(
        ("duration_ms", "expected"),
        [(9_999, Severity.LOW), (10_000, Severity.MEDIUM)],
    )
    def test_escalates_with_duration(self, duration_ms: int, expected: Severity) -> None:
        assert default_severity(EventType.GAZE_AWAY, duration_ms) is expected


@pytest.mark.parametrize(
    "event_type",
    [EventType.EXTRA_PERSON, EventType.SUSPICIOUS_PROCESS, EventType.SCREEN_SHARE],
)
def test_unambiguous_signals_are_high_regardless_of_duration(
    event_type: EventType,
) -> None:
    assert default_severity(event_type, 0) is Severity.HIGH
    assert default_severity(event_type, 60_000) is Severity.HIGH


def test_extra_display_is_medium() -> None:
    # Un segundo monitor puede ser el entorno habitual del estudiante: se reporta,
    # no se condena.
    assert default_severity(EventType.EXTRA_DISPLAY, 0) is Severity.MEDIUM


def test_speech_detected_is_always_low() -> None:
    """Hablar en voz alta no es trampa.

    Es el caso negativo que define el diferencial del proyecto: solo el servicio
    de IA puede elevar esto, y solo si la transcripcion se parece al enunciado
    **y** hay una segunda voz sintetica. Marcarlo alto aqui seria acusar a quien
    lee en voz alta para concentrarse.
    """
    assert default_severity(EventType.SPEECH_DETECTED, 0) is Severity.LOW
    assert default_severity(EventType.SPEECH_DETECTED, 120_000) is Severity.LOW


def test_identity_check_is_low() -> None:
    assert default_severity(EventType.IDENTITY_CHECK, 0) is Severity.LOW


def test_every_event_type_has_a_severity() -> None:
    # Si alguien anade un EventType y olvida el caso en default_severity, el match
    # devuelve None y esto falla.
    for event_type in EventType:
        assert isinstance(default_severity(event_type, 0), Severity)
