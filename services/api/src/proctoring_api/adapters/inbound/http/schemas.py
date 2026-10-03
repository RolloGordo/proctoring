"""Modelos Pydantic de peticion y respuesta.

Son la frontera HTTP: traducen JSON a los DTO de la capa de aplicacion y las
entidades a JSON. **Aqui no hay logica de negocio.**

Division de responsabilidades en la validacion:

- Lo que falla aqui responde **422**: forma incorrecta (tipo equivocado, enum
  desconocido, `duration_ms` negativo, clave de mas).
- Lo que falla en el dominio responde **400**: la forma es correcta pero viola una
  regla de negocio (por ejemplo `gaze_away` sin `question_id`).

Los campos reflejan `packages/contracts/event.schema.json`, que es la fuente de
verdad compartida con la app de escritorio y el servicio de IA.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from proctoring_api.domain.alert import Alert
from proctoring_api.domain.event import MAX_EVIDENCE_PATH_LENGTH, EventType, ProctoringEvent
from proctoring_api.domain.severity import Severity


class EventRequest(BaseModel):
    """Cuerpo de `POST /api/v1/events`."""

    # extra="forbid" replica additionalProperties: false del contrato. Una clave mal
    # escrita falla de inmediato en vez de perderse en silencio.
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    student_id: UUID
    event_type: EventType
    started_at: datetime
    question_id: UUID | None = None
    duration_ms: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence_path: str | None = Field(default=None, max_length=MAX_EVIDENCE_PATH_LENGTH)


class EventCreatedResponse(BaseModel):
    """Respuesta de `POST /api/v1/events` (201)."""

    id: UUID
    severity: Severity


class EventResponse(BaseModel):
    """Un evento tal como se devuelve al docente."""

    id: UUID
    session_id: UUID
    student_id: UUID
    question_id: UUID | None
    event_type: EventType
    started_at: datetime
    duration_ms: int
    metadata: dict[str, Any]
    evidence_path: str | None
    severity: Severity

    @classmethod
    def from_entity(cls, event: ProctoringEvent, severity: Severity) -> EventResponse:
        return cls(
            id=event.id,
            session_id=event.session_id,
            student_id=event.student_id,
            question_id=event.question_id,
            event_type=event.event_type,
            started_at=event.started_at,
            duration_ms=event.duration_ms,
            metadata=dict(event.metadata),
            evidence_path=event.evidence_path,
            severity=severity,
        )


class AlertResponse(BaseModel):
    """Una alerta tal como la ve el docente.

    Es la misma forma que llega por Supabase Realtime, para que la web pueda usar
    el mismo tipo en la carga inicial y en los avisos en vivo.
    """

    id: UUID
    event_id: UUID
    session_id: UUID
    student_id: UUID
    severity: Severity
    reason: str
    created_at: datetime

    @classmethod
    def from_entity(cls, alert: Alert) -> AlertResponse:
        return cls(
            id=alert.id,
            event_id=alert.event_id,
            session_id=alert.session_id,
            student_id=alert.student_id,
            severity=alert.severity,
            reason=alert.reason,
            created_at=alert.created_at,
        )


class HealthResponse(BaseModel):
    """Respuesta de `GET /health`."""

    status: str
    env: str
    version: str
    auth: Literal["enabled", "disabled"]


class ErrorResponse(BaseModel):
    """Cuerpo de error del dominio (400)."""

    detail: str
