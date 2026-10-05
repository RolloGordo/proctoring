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

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from proctoring_api.application.use_cases.list_my_exams import MyExam
from proctoring_api.domain.alert import Alert
from proctoring_api.domain.answer import MAX_TEXT_ANSWER_LENGTH, Answer
from proctoring_api.domain.event import MAX_EVIDENCE_PATH_LENGTH, EventType, ProctoringEvent
from proctoring_api.domain.evidence import EvidenceKind
from proctoring_api.domain.exam_session import (
    ExamSession,
    SessionStatus,
    SupervisionModule,
    SupervisionPreset,
)
from proctoring_api.domain.participant import SessionParticipant, VerificationStatus
from proctoring_api.domain.question import ExamQuestion, Question, QuestionType
from proctoring_api.domain.severity import Severity

#: Tope del campo `metadata` de un evento, en bytes de su JSON.
#:
#: La metadata documentada son unas pocas claves (umbrales, nombre de proceso,
#: angulos). 8 KB es holgado para eso y muy por debajo de lo que sirve para
#: tumbar el servicio: sin tope, un cliente puede mandar megabytes en cada uno de
#: los cientos de eventos de un examen, y todo eso acaba en una columna jsonb.
MAX_METADATA_BYTES = 8192
#: Y un tope de claves, porque mil claves diminutas tambien hacen dano.
MAX_METADATA_KEYS = 50


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

    @field_validator("metadata")
    @classmethod
    def _limitar_metadata(cls, valor: dict[str, Any]) -> dict[str, Any]:
        if len(valor) > MAX_METADATA_KEYS:
            raise ValueError(f"metadata admite como maximo {MAX_METADATA_KEYS} claves")

        tamano = len(json.dumps(valor, ensure_ascii=False).encode("utf-8"))
        if tamano > MAX_METADATA_BYTES:
            raise ValueError(
                f"metadata ocupa {tamano} bytes y el maximo es {MAX_METADATA_BYTES}. "
                "La evidencia pesada va a Storage, no al evento."
            )
        return valor


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


class QuestionOptionRequest(BaseModel):
    """Una alternativa al crear una pregunta."""

    model_config = ConfigDict(extra="forbid")

    option_text: str = Field(min_length=1, max_length=1000)
    is_correct: bool = False


class NewQuestionRequest(BaseModel):
    """Una pregunta a crear."""

    model_config = ConfigDict(extra="forbid")

    question_type: QuestionType
    statement: str = Field(min_length=1, max_length=5000)
    points: Decimal = Field(default=Decimal(1), ge=0, le=100)
    options: list[QuestionOptionRequest] = Field(default_factory=list, max_length=10)
    correct_numeric_answer: Decimal | None = None
    numeric_tolerance: Decimal | None = Field(default=None, ge=0)
    correct_text_answer: str | None = Field(default=None, max_length=1000)


class AddQuestionsRequest(BaseModel):
    """Cuerpo de `POST /api/v1/sessions/{id}/questions`."""

    model_config = ConfigDict(extra="forbid")

    questions: list[NewQuestionRequest] = Field(min_length=1, max_length=50)


class QuestionOptionResponse(BaseModel):
    """Alternativa **con** la marca de correcta. Solo para el docente."""

    id: UUID
    position: int
    option_text: str
    is_correct: bool


class QuestionResponse(BaseModel):
    """Pregunta **con** su respuesta correcta. Solo para el docente dueno."""

    id: UUID
    session_id: UUID
    position: int
    question_type: QuestionType
    statement: str
    points: Decimal
    options: list[QuestionOptionResponse]
    correct_numeric_answer: Decimal | None
    numeric_tolerance: Decimal | None
    correct_text_answer: str | None

    @classmethod
    def from_entity(cls, question: Question) -> QuestionResponse:
        return cls(
            id=question.id,
            session_id=question.session_id,
            position=question.position,
            question_type=question.question_type,
            statement=question.statement,
            points=question.points,
            options=[
                QuestionOptionResponse(
                    id=o.id,
                    position=o.position,
                    option_text=o.option_text,
                    is_correct=o.is_correct,
                )
                for o in question.options
            ],
            correct_numeric_answer=question.correct_numeric_answer,
            numeric_tolerance=question.numeric_tolerance,
            correct_text_answer=question.correct_text_answer,
        )


class ExamOptionResponse(BaseModel):
    """Alternativa como la ve el estudiante. **Sin `is_correct`.**"""

    id: UUID
    position: int
    option_text: str


class ExamQuestionResponse(BaseModel):
    """Pregunta como la ve el estudiante mientras rinde.

    No tiene respuesta correcta ni opciones marcadas. Se construye solo desde
    `ExamQuestion`, que tampoco los tiene: el tipo impide el error, no la
    disciplina.
    """

    id: UUID
    position: int
    question_type: QuestionType
    statement: str
    points: Decimal
    options: list[ExamOptionResponse]

    @classmethod
    def from_entity(cls, question: ExamQuestion) -> ExamQuestionResponse:
        return cls(
            id=question.id,
            position=question.position,
            question_type=question.question_type,
            statement=question.statement,
            points=question.points,
            options=[
                ExamOptionResponse(id=o.id, position=o.position, option_text=o.option_text)
                for o in question.options
            ],
        )


class EnrollRequest(BaseModel):
    """Cuerpo de `POST /api/v1/exam/{id}/enroll`."""

    model_config = ConfigDict(extra="forbid")

    #: Sin valor por defecto a proposito: el consentimiento se da, no se asume.
    accepts_supervision: bool


class ParticipantResponse(BaseModel):
    """Estado de un estudiante dentro de una sesion."""

    id: UUID
    session_id: UUID
    student_id: UUID
    attempt: int
    verification_status: VerificationStatus
    consent_at: datetime | None
    verified_at: datetime | None
    started_at: datetime | None
    submitted_at: datetime | None
    can_take_exam: bool

    @classmethod
    def from_entity(cls, participant: SessionParticipant) -> ParticipantResponse:
        return cls(
            id=participant.id,
            session_id=participant.session_id,
            student_id=participant.student_id,
            attempt=participant.attempt,
            verification_status=participant.verification_status,
            consent_at=participant.consent_at,
            verified_at=participant.verified_at,
            started_at=participant.started_at,
            submitted_at=participant.submitted_at,
            can_take_exam=participant.can_take_exam,
        )


class AnswerRequest(BaseModel):
    """Una respuesta del estudiante a una pregunta.

    Qué campo se usa depende del tipo de pregunta, y eso lo valida el dominio:
    aquí solo se comprueba la forma. Mandar dos a la vez responde 400.
    """

    model_config = ConfigDict(extra="forbid")

    question_id: UUID
    selected_option_id: UUID | None = None
    text_answer: str | None = Field(default=None, max_length=MAX_TEXT_ANSWER_LENGTH)
    numeric_answer: Decimal | None = None


class SaveAnswersRequest(BaseModel):
    """Cuerpo de `PUT /api/v1/exam/{session_id}/answers`."""

    model_config = ConfigDict(extra="forbid")

    answers: list[AnswerRequest] = Field(min_length=1, max_length=200)


class AnswerResponse(BaseModel):
    """Una respuesta guardada.

    No lleva `is_correct` ni `points_awarded`: devolverlos al guardar le diría al
    estudiante si acertó mientras rinde, que es justo lo que no puede saber.
    """

    question_id: UUID
    selected_option_id: UUID | None
    text_answer: str | None
    numeric_answer: Decimal | None
    answered_at: datetime

    @classmethod
    def from_entity(cls, answer: Answer) -> AnswerResponse:
        return cls(
            question_id=answer.question_id,
            selected_option_id=answer.selected_option_id,
            text_answer=answer.text_answer,
            numeric_answer=answer.numeric_answer,
            answered_at=answer.answered_at,
        )


class MyExamResponse(BaseModel):
    """Un examen del panel del estudiante.

    Lleva lo que el estudiante necesita para decidir que hacer: cuando es, si
    puede entrar hoy y en que punto esta. No lleva el codigo de acceso: lo tiene
    quien ya entro y no hace falta repetirlo.
    """

    session_id: UUID
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    entry_tolerance_minutes: int
    can_enter_now: bool
    #: Que se va a supervisar: la sala de espera lo muestra antes de que el
    #: estudiante entre, igual que `JoinExamResponse`.
    modules: dict[SupervisionModule, dict[str, Any]]
    verification_status: VerificationStatus
    can_take_exam: bool
    consent_at: datetime | None
    submitted_at: datetime | None
    #: `None` mientras no se califica. Hoy siempre es `None`: la calificacion
    #: automatica es una tarea pendiente (SPEC-003), y mostrar un cero inventado
    #: seria peor que decir que falta.
    score: float | None

    @classmethod
    def from_entity(cls, exam: MyExam) -> MyExamResponse:
        return cls(
            session_id=exam.session.id,
            title=exam.session.title,
            description=exam.session.description,
            starts_at=exam.session.starts_at,
            ends_at=exam.session.ends_at,
            duration_minutes=exam.session.duration_minutes,
            entry_tolerance_minutes=exam.session.entry_tolerance_minutes,
            can_enter_now=exam.can_enter_now,
            modules=exam.session.modules,
            verification_status=exam.participant.verification_status,
            can_take_exam=exam.participant.can_take_exam,
            consent_at=exam.participant.consent_at,
            submitted_at=exam.participant.submitted_at,
            score=exam.participant.score,
        )


class ReviewIdentityRequest(BaseModel):
    """Cuerpo de la revision manual de identidad por el docente."""

    model_config = ConfigDict(extra="forbid")

    approve: bool


class HealthResponse(BaseModel):
    """Respuesta de `GET /health`."""

    status: str
    env: str
    version: str
    auth: Literal["enabled", "disabled"]


class ErrorResponse(BaseModel):
    """Cuerpo de error del dominio (400)."""

    detail: str
