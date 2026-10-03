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
from proctoring_api.domain.evidence import EvidenceKind
from proctoring_api.domain.exam_session import (
    ExamSession,
    SessionStatus,
    SupervisionModule,
    SupervisionPreset,
)
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


class EvidenceUploadRequestBody(BaseModel):
    """Cuerpo de `POST /api/v1/evidence/upload-url`."""

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    student_id: UUID
    kind: EvidenceKind
    extension: str = Field(max_length=8, examples=["jpg", "webm"])


class EvidenceUploadResponse(BaseModel):
    """Permiso temporal para subir un archivo.

    El cliente sube a `url` y luego manda el evento con `path` en
    `evidence_path`. El archivo nunca pasa por la API.
    """

    path: str
    url: str
    token: str | None
    expires_in_seconds: int


class ExamSessionRequest(BaseModel):
    """Cuerpo de `POST /api/v1/sessions`."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    duration_minutes: int = Field(gt=0, le=600)
    course_id: UUID | None = None
    description: str | None = Field(default=None, max_length=2000)
    entry_tolerance_minutes: int = Field(default=10, ge=0, le=120)
    preset: SupervisionPreset = SupervisionPreset.STANDARD
    max_attempts: int = Field(default=1, gt=0, le=10)
    shuffle_questions: bool = True
    shuffle_options: bool = True
    allow_back_navigation: bool = True
    #: Solo se usa con `preset = custom`; con los demas manda el preset.
    modules: dict[SupervisionModule, dict[str, Any]] | None = None


class ExamSessionSummary(BaseModel):
    """Sesion en un listado, sin el detalle de los modulos."""

    id: UUID
    title: str
    starts_at: datetime
    duration_minutes: int
    access_code: str
    preset: SupervisionPreset
    status: SessionStatus

    @classmethod
    def from_entity(cls, session: ExamSession) -> ExamSessionSummary:
        return cls(
            id=session.id,
            title=session.title,
            starts_at=session.starts_at,
            duration_minutes=session.duration_minutes,
            access_code=session.access_code,
            preset=session.preset,
            status=session.status,
        )


class ExamSessionResponse(BaseModel):
    """Sesion completa, con los modulos activos y sus umbrales.

    `modules` es el mismo contrato que la app de escritorio y el spike de vision
    usan para saber con que umbrales emitir cada evento.
    """

    id: UUID
    teacher_id: UUID
    course_id: UUID | None
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    entry_tolerance_minutes: int
    access_code: str
    preset: SupervisionPreset
    status: SessionStatus
    max_attempts: int
    shuffle_questions: bool
    shuffle_options: bool
    allow_back_navigation: bool
    modules: dict[SupervisionModule, dict[str, Any]]

    @classmethod
    def from_entity(cls, session: ExamSession) -> ExamSessionResponse:
        return cls(
            id=session.id,
            teacher_id=session.teacher_id,
            course_id=session.course_id,
            title=session.title,
            description=session.description,
            starts_at=session.starts_at,
            ends_at=session.ends_at,
            duration_minutes=session.duration_minutes,
            entry_tolerance_minutes=session.entry_tolerance_minutes,
            access_code=session.access_code,
            preset=session.preset,
            status=session.status,
            max_attempts=session.max_attempts,
            shuffle_questions=session.shuffle_questions,
            shuffle_options=session.shuffle_options,
            allow_back_navigation=session.allow_back_navigation,
            modules=session.modules,
        )


class JoinExamRequest(BaseModel):
    """Cuerpo de `POST /api/v1/sessions/join`."""

    model_config = ConfigDict(extra="forbid")

    access_code: str = Field(min_length=4, max_length=16)


class JoinExamResponse(BaseModel):
    """Lo que el estudiante necesita para prepararse.

    No incluye las preguntas ni las respuestas correctas: eso llega cuando
    empieza el examen, y siempre servido por la API.
    """

    session_id: UUID
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    entry_tolerance_minutes: int
    can_enter_now: bool
    modules: dict[SupervisionModule, dict[str, Any]]


class HealthResponse(BaseModel):
    """Respuesta de `GET /health`."""

    status: str
    env: str
    version: str
    auth: Literal["enabled", "disabled"]


class ErrorResponse(BaseModel):
    """Cuerpo de error del dominio (400)."""

    detail: str
