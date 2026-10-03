"""Reglas de la sesion de examen."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from proctoring_api.domain.exam_session import (
    ACCESS_CODE_ALPHABET,
    ACCESS_CODE_LENGTH,
    PRESET_MODULES,
    ExamSession,
    InvalidExamSessionError,
    SessionStatus,
    SupervisionModule,
    SupervisionPreset,
    generate_access_code,
    modules_for,
)

TEACHER = uuid4()
STARTS_AT = datetime(2026, 10, 10, 14, 0, tzinfo=UTC)


def make(**overrides: object) -> ExamSession:
    kwargs: dict[str, object] = {
        "teacher_id": TEACHER,
        "title": "Examen parcial de Taller Integrador",
        "starts_at": STARTS_AT,
        "duration_minutes": 90,
    }
    kwargs.update(overrides)
    return ExamSession.create(**kwargs)  # type: ignore[arg-type]


class TestTitle:
    def test_is_trimmed(self) -> None:
        assert make(title="  Parcial  ").title == "Parcial"

    @pytest.mark.parametrize("title", ["", "   ", "\n"])
    def test_rejects_blank(self, title: str) -> None:
        with pytest.raises(InvalidExamSessionError, match="titulo"):
            make(title=title)

    def test_rejects_too_long(self) -> None:
        with pytest.raises(InvalidExamSessionError, match="titulo"):
            make(title="x" * 201)


class TestNumbers:
    @pytest.mark.parametrize("duration", [0, -30])
    def test_rejects_non_positive_duration(self, duration: int) -> None:
        with pytest.raises(InvalidExamSessionError, match="duracion"):
            make(duration_minutes=duration)

    def test_rejects_negative_tolerance(self) -> None:
        with pytest.raises(InvalidExamSessionError, match="tolerancia"):
            make(entry_tolerance_minutes=-1)

    def test_rejects_non_positive_attempts(self) -> None:
        with pytest.raises(InvalidExamSessionError, match="intentos"):
            make(max_attempts=0)


class TestStartsAt:
    def test_rejects_naive_datetime(self) -> None:
        with pytest.raises(InvalidExamSessionError, match="zona horaria"):
            make(starts_at=datetime(2026, 10, 10, 14, 0))

    def test_ends_at_is_derived(self) -> None:
        assert make(duration_minutes=90).ends_at == STARTS_AT + timedelta(minutes=90)


class TestAccessCode:
    def test_has_the_expected_shape(self) -> None:
        code = generate_access_code()

        assert len(code) == ACCESS_CODE_LENGTH
        assert all(character in ACCESS_CODE_ALPHABET for character in code)

    def test_avoids_ambiguous_characters(self) -> None:
        # El estudiante lo teclea leyendolo de una pizarra: confundir un cero con
        # una o es la forma mas tonta de perder cinco minutos al empezar.
        for ambiguous in "O0I1L":
            assert ambiguous not in ACCESS_CODE_ALPHABET

    def test_codes_differ(self) -> None:
        assert len({generate_access_code() for _ in range(50)}) > 45

    def test_is_generated_when_not_given(self) -> None:
        assert len(make().access_code) == ACCESS_CODE_LENGTH


class TestPresets:
    def test_a_preset_resolves_its_modules(self) -> None:
        session = make(preset=SupervisionPreset.STANDARD)

        assert set(session.modules) == PRESET_MODULES[SupervisionPreset.STANDARD]

    def test_strict_includes_the_ai_voice_module(self) -> None:
        # Es el diferencial del proyecto: tiene que estar en el nivel mas alto.
        assert SupervisionModule.AI_VOICE in modules_for(SupervisionPreset.STRICT)

    def test_basic_does_not(self) -> None:
        assert SupervisionModule.AI_VOICE not in modules_for(SupervisionPreset.BASIC)

    def test_each_level_adds_to_the_previous(self) -> None:
        basic = PRESET_MODULES[SupervisionPreset.BASIC]
        standard = PRESET_MODULES[SupervisionPreset.STANDARD]
        strict = PRESET_MODULES[SupervisionPreset.STRICT]

        assert basic < standard < strict

    def test_modules_carry_their_thresholds(self) -> None:
        # Son el mismo contrato que usan la app y el spike de vision para saber
        # cuando emitir un evento.
        modules = modules_for(SupervisionPreset.STANDARD)

        assert modules[SupervisionModule.FOCUS_LOSS] == {"min_duration_ms": 5000}
        assert modules[SupervisionModule.GAZE] == {
            "yaw_degrees": 25,
            "min_duration_ms": 3000,
        }

    def test_a_preset_ignores_modules_sent_by_hand(self) -> None:
        # Si no, `preset` mentiria sobre lo que la sesion hace de verdad.
        session = make(
            preset=SupervisionPreset.BASIC,
            modules={SupervisionModule.AI_VOICE: {}},
        )

        assert SupervisionModule.AI_VOICE not in session.modules

    def test_custom_uses_what_it_is_given(self) -> None:
        session = make(
            preset=SupervisionPreset.CUSTOM,
            modules={SupervisionModule.GAZE: {"yaw_degrees": 30}},
        )

        assert session.modules == {SupervisionModule.GAZE: {"yaw_degrees": 30}}

    def test_custom_without_modules_is_rejected(self) -> None:
        # Un examen que no vigila nada no es un examen supervisado.
        with pytest.raises(InvalidExamSessionError, match="custom"):
            make(preset=SupervisionPreset.CUSTOM)


class TestEntryWindow:
    def test_accepts_entry_at_the_start(self) -> None:
        assert make().accepts_entry_at(STARTS_AT)

    def test_accepts_entry_within_tolerance(self) -> None:
        # Llegar dos minutos tarde no deberia costar el examen.
        assert make(entry_tolerance_minutes=10).accepts_entry_at(STARTS_AT + timedelta(minutes=9))

    def test_rejects_entry_after_tolerance(self) -> None:
        assert not make(entry_tolerance_minutes=10).accepts_entry_at(
            STARTS_AT + timedelta(minutes=11)
        )

    def test_rejects_entry_before_the_start(self) -> None:
        assert not make().accepts_entry_at(STARTS_AT - timedelta(minutes=1))

    def test_never_accepts_entry_after_the_exam_ended(self) -> None:
        # Tolerancia mayor que la duracion: la ventana no puede pasarse del final.
        session = make(duration_minutes=5, entry_tolerance_minutes=60)

        assert not session.accepts_entry_at(STARTS_AT + timedelta(minutes=6))


def test_a_new_session_is_scheduled() -> None:
    assert make().status is SessionStatus.SCHEDULED


def test_each_session_gets_its_own_id() -> None:
    assert make().id != make().id
