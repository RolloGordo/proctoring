"""Reglas de la entidad `ProctoringEvent`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from proctoring_api.domain.errors import InvalidEventError
from proctoring_api.domain.event import EventType, ProctoringEvent

SESSION = uuid4()
STUDENT = uuid4()
QUESTION = uuid4()
STARTED_AT = datetime(2026, 10, 3, 14, 21, 5, tzinfo=UTC)


def make(**overrides: object) -> ProctoringEvent:
    kwargs: dict[str, object] = {
        "session_id": SESSION,
        "student_id": STUDENT,
        "event_type": EventType.FOCUS_LOST,
        "started_at": STARTED_AT,
    }
    kwargs.update(overrides)
    return ProctoringEvent.create(**kwargs)  # type: ignore[arg-type]


class TestDurationMs:
    def test_accepts_zero(self) -> None:
        assert make(duration_ms=0).duration_ms == 0

    def test_rejects_negative(self) -> None:
        with pytest.raises(InvalidEventError, match="duration_ms"):
            make(duration_ms=-1)


class TestStartedAt:
    def test_rejects_naive_datetime(self) -> None:
        with pytest.raises(InvalidEventError, match="zona horaria"):
            make(started_at=datetime(2026, 10, 3, 14, 21, 5))

    def test_normalises_to_utc(self) -> None:
        lima = timezone(timedelta(hours=-5))
        event = make(started_at=datetime(2026, 10, 3, 9, 21, 5, tzinfo=lima))

        assert event.started_at == STARTED_AT
        assert event.started_at.utcoffset() == timedelta(0)


class TestQuestionId:
    @pytest.mark.parametrize("event_type", [EventType.SPEECH_DETECTED, EventType.GAZE_AWAY])
    def test_required_for_question_dependent_events(self, event_type: EventType) -> None:
        # Sin la pregunta en curso no hay con que comparar la transcripcion, que es
        # el nucleo de la deteccion de IA por voz.
        with pytest.raises(InvalidEventError, match="question_id"):
            make(event_type=event_type, question_id=None)

    @pytest.mark.parametrize("event_type", [EventType.SPEECH_DETECTED, EventType.GAZE_AWAY])
    def test_accepted_when_present(self, event_type: EventType) -> None:
        assert make(event_type=event_type, question_id=QUESTION).question_id == QUESTION

    @pytest.mark.parametrize(
        "event_type",
        [
            EventType.FOCUS_LOST,
            EventType.FACE_ABSENT,
            EventType.EXTRA_PERSON,
            EventType.EXTRA_DISPLAY,
            EventType.SUSPICIOUS_PROCESS,
            EventType.SCREEN_SHARE,
            EventType.IDENTITY_CHECK,
        ],
    )
    def test_optional_for_the_rest(self, event_type: EventType) -> None:
        assert make(event_type=event_type).question_id is None


class TestEvidencePath:
    def test_rejects_blank(self) -> None:
        with pytest.raises(InvalidEventError, match="vacia"):
            make(evidence_path="   ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(InvalidEventError, match="512"):
            make(evidence_path="a" * 513)

    def test_strips_whitespace(self) -> None:
        assert make(evidence_path="  s/e/f.jpg  ").evidence_path == "s/e/f.jpg"


class TestImmutability:
    def test_entity_is_frozen(self) -> None:
        event = make()
        with pytest.raises(AttributeError):
            event.duration_ms = 999  # type: ignore[misc]

    def test_metadata_cannot_be_mutated_through_the_original_dict(self) -> None:
        # El evento es evidencia: una vez creado nadie puede cambiarlo, ni siquiera
        # quien se quedo con la referencia al diccionario que paso.
        original = {"source": "electron_main"}
        event = make(metadata=original)

        original["source"] = "manipulado"

        assert event.metadata["source"] == "electron_main"
        with pytest.raises(TypeError):
            event.metadata["source"] = "manipulado"  # type: ignore[index]


class TestNeedsAudioAnalysis:
    def test_true_only_for_speech_detected(self) -> None:
        speech = make(event_type=EventType.SPEECH_DETECTED, question_id=QUESTION)
        assert speech.needs_audio_analysis is True

    @pytest.mark.parametrize(
        "event_type", [EventType.FOCUS_LOST, EventType.EXTRA_PERSON, EventType.FACE_ABSENT]
    )
    def test_false_for_everything_else(self, event_type: EventType) -> None:
        assert make(event_type=event_type).needs_audio_analysis is False


def test_generates_an_id_when_not_given() -> None:
    assert make().id != make().id


def test_event_type_values_match_the_shared_contract() -> None:
    # Los mismos nueve valores que el enum de PostgreSQL y el de
    # packages/contracts/event.schema.json. Si alguien anade uno aqui sin tocar
    # los otros dos sitios, esta prueba lo caza.
    assert {event_type.value for event_type in EventType} == {
        "focus_lost",
        "gaze_away",
        "face_absent",
        "extra_person",
        "extra_display",
        "suspicious_process",
        "screen_share",
        "speech_detected",
        "identity_check",
    }
