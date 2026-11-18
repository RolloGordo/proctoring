"""Entidad `ProctoringEvent` y su tipo.

El evento es la unidad de evidencia del sistema. Una vez registrado **no se
modifica ni se borra** (RLS en Supabase solo permite insert y select), asi que
toda la validacion ocurre al construirlo. De ahi que la entidad sea inmutable y
que la unica via de creacion sea `ProctoringEvent.create`.
"""

from __future__ import annotations

import types
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from proctoring_api.domain.errors import InvalidEventError

#: Longitud maxima de la ruta de evidencia (coincide con el contrato compartido).
MAX_EVIDENCE_PATH_LENGTH = 512

#: Clave de `metadata` con la que el cliente agrupa los informes de un episodio.
EPISODE_ID_KEY = "episode_id"
#: Un UUID tiene 36 caracteres; esto deja margen sin aceptar cualquier cosa.
MAX_EPISODE_ID_LENGTH = 64


class EventType(StrEnum):
    """Tipos de senal detectada.

    Los mismos valores que el enum `event_type` de PostgreSQL y que el enum
    de `packages/contracts/event.schema.json`. Si se anade uno, hay que tocar los
    tres sitios y crear una migracion.
    """

    FOCUS_LOST = "focus_lost"
    COPY_ATTEMPT = "copy_attempt"
    GAZE_AWAY = "gaze_away"
    FACE_ABSENT = "face_absent"
    EXTRA_PERSON = "extra_person"
    EXTRA_DISPLAY = "extra_display"
    SUSPICIOUS_PROCESS = "suspicious_process"
    SCREEN_SHARE = "screen_share"
    SPEECH_DETECTED = "speech_detected"
    PROHIBITED_OBJECT = "prohibited_object"
    FRAMING_LOST = "framing_lost"
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
    def episode_id(self) -> str | None:
        """El episodio del que este evento es un informe, si el cliente lo dice.

        Una condicion con duracion (rostro ausente, mirada fuera) se informa
        varias veces mientras dura, siempre con el mismo `episode_id` en
        `metadata`: al cumplir el minimo, al ir cruzando umbrales y al cerrarse
        con la duracion final. Asi el docente recibe la alerta mientras pasa y la
        duracion real llega igual. Ver `one_per_episode`.

        Un valor que no es un texto razonable se ignora: el evento cuenta solo,
        como antes de existir la clave. Perder una senal por una metadata rara
        seria peor que contarla una vez de mas.
        """
        value = self.metadata.get(EPISODE_ID_KEY)
        if isinstance(value, str) and 0 < len(value) <= MAX_EPISODE_ID_LENGTH:
            return value
        return None

    @property
    def needs_audio_analysis(self) -> bool:
        """Si este evento requiere que el servicio de IA lo analice."""
        # El evento de habla también se conserva cuando falla la subida, para
        # que la línea de tiempo no confunda un problema técnico con silencio.
        # Sin fragmento no hay nada que transcribir ni analizar.
        return self.event_type is EventType.SPEECH_DETECTED and self.evidence_path is not None


def one_per_episode(events: Iterable[ProctoringEvent]) -> list[ProctoringEvent]:
    """Un evento por episodio: el informe mas largo de cada uno, en su orden.

    Los informes de un mismo episodio (mismo tipo y mismo `episode_id`) son la
    misma condicion vista en momentos distintos: contarlos todos haria que una
    ausencia de tres minutos pesara como trece. Se queda el de mayor duracion,
    que es el que mejor la describe. Los eventos sin `episode_id` pasan tal cual.
    """
    events = list(events)
    longest: dict[tuple[EventType, str], ProctoringEvent] = {}
    for event in events:
        episode = event.episode_id
        if episode is None:
            continue
        key = (event.event_type, episode)
        current = longest.get(key)
        if current is None or event.duration_ms > current.duration_ms:
            longest[key] = event

    return [
        event
        for event in events
        if event.episode_id is None or longest[(event.event_type, event.episode_id)] is event
    ]
