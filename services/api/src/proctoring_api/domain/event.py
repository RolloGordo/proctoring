"""Entidad `ProctoringEvent` y su tipo.

El evento es la unidad de evidencia del sistema. Una vez registrado **no se
modifica ni se borra** (RLS en Supabase solo permite insert y select), asi que
toda la validacion ocurre al construirlo. De ahi que la entidad sea inmutable y
que la unica via de creacion sea `ProctoringEvent.create`.
"""

from __future__ import annotations

import types
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from proctoring_api.domain.errors import InvalidEventError

#: Longitud maxima de la ruta de evidencia (coincide con el contrato compartido).
MAX_EVIDENCE_PATH_LENGTH = 512


class EventType(StrEnum):
    """Tipos de senal detectada.

    Los mismos nueve valores que el enum `event_type` de PostgreSQL y que el enum
    de `packages/contracts/event.schema.json`. Si se anade uno, hay que tocar los
    tres sitios y crear una migracion.
    """

    FOCUS_LOST = "focus_lost"
    GAZE_AWAY = "gaze_away"
    FACE_ABSENT = "face_absent"
    EXTRA_PERSON = "extra_person"
    EXTRA_DISPLAY = "extra_display"
    SUSPICIOUS_PROCESS = "suspicious_process"
    SCREEN_SHARE = "screen_share"
    SPEECH_DETECTED = "speech_detected"
    IDENTITY_CHECK = "identity_check"


#: Eventos que no significan nada sin saber en que pregunta estaba el estudiante.
#:
#: - `speech_detected`: el servicio de IA compara la transcripcion con el enunciado
#:   de la pregunta en curso. Sin `question_id` no hay con que comparar y el
#:   diferencial del proyecto no funciona.
#: - `gaze_away`: mirar fuera de pantalla solo es interpretable junto a la pregunta
#:   que se estaba respondiendo.
QUESTION_REQUIRED_EVENTS: frozenset[EventType] = frozenset(
    {EventType.SPEECH_DETECTED, EventType.GAZE_AWAY}
)


@dataclass(frozen=True, slots=True)
class ProctoringEvent:
    """Una senal detectada durante un examen, con su evidencia asociada.

    Construir siempre con `ProctoringEvent.create`: el constructor directo no
    valida nada.
    """

    id: UUID
    session_id: UUID
    student_id: UUID
    question_id: UUID | None
    event_type: EventType
    started_at: datetime
    duration_ms: int
    metadata: Mapping[str, Any]
    evidence_path: str | None

    @classmethod
    def create(
        cls,
        *,
        session_id: UUID,
        student_id: UUID,
        event_type: EventType,
        started_at: datetime,
        question_id: UUID | None = None,
        duration_ms: int = 0,
        metadata: Mapping[str, Any] | None = None,
        evidence_path: str | None = None,
        event_id: UUID | None = None,
    ) -> ProctoringEvent:
        """Crea un evento validado.

        Raises:
            InvalidEventError: si viola alguna regla del dominio.
        """
        if duration_ms < 0:
            raise InvalidEventError(f"duration_ms no puede ser negativo (recibido: {duration_ms})")

        if started_at.tzinfo is None or started_at.utcoffset() is None:
            raise InvalidEventError(
                "started_at debe traer zona horaria; usa ISO-8601 en UTC, "
                "por ejemplo 2026-10-03T14:21:05.120Z"
            )

        if question_id is None and event_type in QUESTION_REQUIRED_EVENTS:
            raise InvalidEventError(
                f"question_id es obligatorio para {event_type.value}: sin la pregunta "
                "en curso el evento no se puede interpretar"
            )

        if evidence_path is not None:
            evidence_path = evidence_path.strip()
            if not evidence_path:
                raise InvalidEventError("evidence_path no puede ser una cadena vacia")
            if len(evidence_path) > MAX_EVIDENCE_PATH_LENGTH:
                raise InvalidEventError(
                    f"evidence_path supera los {MAX_EVIDENCE_PATH_LENGTH} caracteres"
                )

        return cls(
            id=event_id if event_id is not None else uuid4(),
            session_id=session_id,
            student_id=student_id,
            question_id=question_id,
            event_type=event_type,
            # Se normaliza a UTC para que todo el sistema compare horas sin sorpresas.
            started_at=started_at.astimezone(UTC),
            duration_ms=duration_ms,
            # MappingProxyType deja la entidad inmutable de verdad: sin esto, quien
            # tenga la referencia al dict original puede mutar el evento ya guardado.
            metadata=types.MappingProxyType(dict(metadata) if metadata else {}),
            evidence_path=evidence_path,
        )

    @property
    def needs_audio_analysis(self) -> bool:
        """Si este evento requiere que el servicio de IA lo analice."""
        return self.event_type is EventType.SPEECH_DETECTED
