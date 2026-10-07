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

from proctoring_api.application.use_cases.ai_jobs import AudioJob, FaceJob
from proctoring_api.application.use_cases.edit_exam_session import ExamSessionChanges
from proctoring_api.application.use_cases.list_my_exams import MyExam
from proctoring_api.application.use_cases.manage_banks import BankSummary
from proctoring_api.application.use_cases.manage_courses import (
    CourseMember,
    MyCourse,
    TeacherCourse,
)
from proctoring_api.application.use_cases.manage_enrollment import ParticipantEntry
from proctoring_api.application.use_cases.manage_questions import NewQuestion
from proctoring_api.application.use_cases.review_case import CaseFile
from proctoring_api.domain.alert import Alert
from proctoring_api.domain.answer import MAX_TEXT_ANSWER_LENGTH, Answer
from proctoring_api.domain.audio_analysis import AudioAnalysis
from proctoring_api.domain.decision import Decision, DecisionType
from proctoring_api.domain.event import MAX_EVIDENCE_PATH_LENGTH, EventType, ProctoringEvent
from proctoring_api.domain.evidence import EvidenceKind
from proctoring_api.domain.exam_session import (
    DEFAULT_MAX_SCORE,
    ExamSession,
    SessionStatus,
    SupervisionModule,
    SupervisionPreset,
)
from proctoring_api.domain.identity import IdentityCheck, IdentityResult
from proctoring_api.domain.participant import SessionParticipant, VerificationStatus
from proctoring_api.domain.question import ExamQuestion, Question, QuestionType
from proctoring_api.domain.risk import RiskAssessment, RiskLevel
from proctoring_api.domain.severity import Severity, default_severity

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
    #: Cuantas preguntas recibe cada estudiante. Solo aplica con bancos
    #: atados; sin ellos el examen usa sus propias preguntas, todas.
    question_pool_size: int | None = Field(default=None, gt=0, le=500)
    #: Sobre cuanto se califica. 20 por defecto, que es la escala peruana.
    max_score: Decimal = Field(default=DEFAULT_MAX_SCORE, gt=0, le=100)
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
    question_pool_size: int | None
    max_score: Decimal
    cancelled_at: datetime | None
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
            question_pool_size=session.question_pool_size,
            max_score=session.max_score,
            cancelled_at=session.cancelled_at,
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

    def to_input(self) -> NewQuestion:
        """La misma pregunta como la espera la capa de aplicacion.

        Vive aqui y no en el router porque ahora hay dos destinos —un examen y un
        banco— y la conversion tiene que ser la misma para los dos.
        """
        return NewQuestion(
            question_type=self.question_type,
            statement=self.statement,
            points=self.points,
            options=[(o.option_text, o.is_correct) for o in self.options],
            correct_numeric_answer=self.correct_numeric_answer,
            numeric_tolerance=self.numeric_tolerance,
            correct_text_answer=self.correct_text_answer,
        )


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
    #: Uno de los dos esta puesto: la pregunta es de un examen o de un banco.
    session_id: UUID | None
    bank_id: UUID | None = None
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
            bank_id=question.bank_id,
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
    score: float | None
    #: Quien es. Solo lo llena la sala de espera del docente; en el resto de
    #: rutas el estudiante ya sabe quien es.
    student_name: str | None = None
    student_email: str | None = None

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
            score=participant.score,
        )

    @classmethod
    def from_entry(cls, entry: ParticipantEntry) -> ParticipantResponse:
        """El participante con su nombre y correo."""
        response = cls.from_entity(entry.participant)
        if entry.profile is not None:
            response.student_name = entry.profile.full_name
            response.student_email = entry.profile.email
        return response


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
    #: Puntos ganados en lo que se corrige solo. `None` si aun no hay nota:
    #: nunca un cero inventado, porque sin calificacion es mejor decir que falta.
    score: float | None
    #: Sobre cuanto se califica el examen, para mostrar "13.5 de 20".
    max_score: float | None
    #: Si hay desarrollos que el docente todavia no califica. Mientras sea
    #: verdadero, `score` es parcial.
    pending_manual_review: bool
    #: Si el docente retiro el examen.
    cancelled: bool

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
            max_score=exam.max_score,
            pending_manual_review=exam.pending_manual_review,
            cancelled=exam.cancelled,
        )


class CreateCourseRequest(BaseModel):
    """Cuerpo de `POST /api/v1/courses`."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    section: str | None = Field(default=None, max_length=40)


class CourseResponse(BaseModel):
    """Un curso del docente."""

    id: UUID
    name: str
    section: str | None
    created_at: datetime
    student_count: int

    @classmethod
    def from_entity(cls, item: TeacherCourse) -> CourseResponse:
        return cls(
            id=item.course.id,
            name=item.course.name,
            section=item.course.section,
            created_at=item.course.created_at,
            student_count=item.student_count,
        )


class EnrollStudentRequest(BaseModel):
    """Cuerpo de `POST /api/v1/courses/{id}/students`."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def _looks_like_an_email(cls, value: str) -> str:
        clean = value.strip()
        # Lo justo para no mandar basura a la base: la comprobacion de verdad es
        # que exista un estudiante con ese correo.
        if clean.count("@") != 1 or clean.startswith("@") or clean.endswith("@"):
            raise ValueError("Escribe un correo valido")
        return clean


class CourseMemberResponse(BaseModel):
    """Un estudiante matriculado en un curso."""

    student_id: UUID
    email: str | None
    full_name: str | None
    enrolled_at: datetime

    @classmethod
    def from_entity(cls, member: CourseMember) -> CourseMemberResponse:
        return cls(
            student_id=member.student_id,
            email=member.profile.email if member.profile else None,
            full_name=member.profile.full_name if member.profile else None,
            enrolled_at=member.enrolled_at,
        )


class EnrollStudentResponse(BaseModel):
    student: CourseMemberResponse
    already_enrolled: bool


class MyCourseExamResponse(BaseModel):
    """Un examen de una clase, tal como lo ve el estudiante: cuando es y nada mas.

    No lleva el codigo de acceso: para rendirlo hace falta que el docente se lo de.
    """

    session_id: UUID
    title: str
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int


class MyCourseResponse(BaseModel):
    """Una clase del estudiante, con los examenes que le tocan."""

    id: UUID
    name: str
    section: str | None
    exams: list[MyCourseExamResponse]

    @classmethod
    def from_entity(cls, item: MyCourse) -> MyCourseResponse:
        return cls(
            id=item.course.id,
            name=item.course.name,
            section=item.course.section,
            exams=[
                MyCourseExamResponse(
                    session_id=e.id,
                    title=e.title,
                    starts_at=e.starts_at,
                    ends_at=e.ends_at,
                    duration_minutes=e.duration_minutes,
                )
                for e in item.exams
            ],
        )


class DecisionRequest(BaseModel):
    """Cuerpo de `POST /api/v1/sessions/{id}/students/{id}/decision`."""

    model_config = ConfigDict(extra="forbid")

    decision: DecisionType
    #: El minimo se valida en el dominio (400 con un mensaje que explica que
    #: hacer), no aqui (422 con un mensaje de campo).
    justification: str = Field(max_length=2000)


class DecisionResponse(BaseModel):
    """Una decision registrada."""

    id: UUID
    session_id: UUID
    student_id: UUID
    teacher_id: UUID
    decision: DecisionType
    justification: str
    decided_at: datetime

    @classmethod
    def from_entity(cls, decision: Decision) -> DecisionResponse:
        return cls(
            id=decision.id,
            session_id=decision.session_id,
            student_id=decision.student_id,
            teacher_id=decision.teacher_id,
            decision=decision.decision,
            justification=decision.justification,
            decided_at=decision.decided_at,
        )


class SignalRiskResponse(BaseModel):
    """Lo que un tipo de senal aporta al riesgo."""

    event_type: EventType
    count: int
    total_duration_ms: int
    points: int
    max_severity: Severity


class RiskResponse(BaseModel):
    """El riesgo de un estudiante, con su desglose por senal.

    Es un **auditor**: dice cuanta atencion merece el caso y por que. No es un
    veredicto, y por eso lleva el desglose y no solo el numero.
    """

    score: int
    level: RiskLevel
    signals: list[SignalRiskResponse]

    @classmethod
    def from_entity(cls, risk: RiskAssessment) -> RiskResponse:
        return cls(
            score=risk.score,
            level=risk.level,
            signals=[
                SignalRiskResponse(
                    event_type=s.event_type,
                    count=s.count,
                    total_duration_ms=s.total_duration_ms,
                    points=s.points,
                    max_severity=s.max_severity,
                )
                for s in risk.signals
            ],
        )


class CaseResponse(BaseModel):
    """Todo lo que el docente necesita para decidir sobre un estudiante."""

    participant: ParticipantResponse
    events: list[EventResponse]
    alerts: list[AlertResponse]
    decisions: list[DecisionResponse]
    risk: RiskResponse

    @classmethod
    def from_entity(cls, case: CaseFile) -> CaseResponse:
        participant = ParticipantResponse.from_entity(case.participant)
        if case.profile is not None:
            participant.student_name = case.profile.full_name
            participant.student_email = case.profile.email
        return cls(
            participant=participant,
            events=[
                EventResponse.from_entity(e, default_severity(e.event_type, e.duration_ms))
                for e in case.events
            ],
            alerts=[AlertResponse.from_entity(a) for a in case.alerts],
            decisions=[DecisionResponse.from_entity(d) for d in case.decisions],
            risk=RiskResponse.from_entity(case.risk),
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


# ---------------------------------------------------------------------------
# Servicio de IA (endpoints internos)
#
# Son el contrato con `services/ai`. El worker mide y manda numeros; la API
# decide que significan. Ver `application/use_cases/ai_jobs.py`.
# ---------------------------------------------------------------------------


class AudioJobResponse(BaseModel):
    """El trabajo de audio servido al worker, con todo lo que necesita."""

    event_id: UUID
    session_id: UUID
    student_id: UUID
    question_id: UUID | None
    #: El enunciado con el que comparar. `None` si la pregunta ya no existe.
    question_statement: str | None
    audio_path: str
    audio_bucket: str
    #: Con que se va a comparar lo medido. El worker los registra, no decide con ellos.
    similarity_threshold: float
    synthetic_threshold: float

    @classmethod
    def from_entity(cls, job: AudioJob) -> AudioJobResponse:
        return cls(
            event_id=job.event_id,
            session_id=job.session_id,
            student_id=job.student_id,
            question_id=job.question_id,
            question_statement=job.question_statement,
            audio_path=job.audio_path,
            audio_bucket=job.audio_bucket,
            similarity_threshold=job.similarity_threshold,
            synthetic_threshold=job.synthetic_threshold,
        )


class AudioMeasurementRequest(BaseModel):
    """Lo que el worker midio. Todo opcional: un analisis puede fallar a medias."""

    model_config = ConfigDict(extra="forbid")

    transcript: str | None = Field(default=None, max_length=10_000)
    similarity: float | None = Field(default=None, ge=0, le=1)
    synthetic_voice_score: float | None = Field(default=None, ge=0, le=1)
    processing_ms: int | None = Field(default=None, ge=0)
    #: Que modelos lo produjeron. Sin esto, un numero de hoy no se puede comparar
    #: con el de la semana que viene.
    model_versions: dict[str, Any] = Field(default_factory=dict)


class AudioAnalysisResponse(BaseModel):
    """Lo guardado, y si el docente fue avisado."""

    event_id: UUID
    transcript: str | None
    similarity: float | None
    synthetic_voice_score: float | None
    processing_ms: int | None
    processed_at: datetime
    #: `True` solo si se cumplieron **las dos** condiciones. Lo decide la API.
    alerted: bool

    @classmethod
    def from_entity(cls, analysis: AudioAnalysis, alerted: bool) -> AudioAnalysisResponse:
        return cls(
            event_id=analysis.event_id,
            transcript=analysis.transcript,
            similarity=analysis.similarity,
            synthetic_voice_score=analysis.synthetic_voice_score,
            processing_ms=analysis.processing_ms,
            processed_at=analysis.processed_at,
            alerted=alerted,
        )


class FaceJobResponse(BaseModel):
    """El trabajo de verificacion facial servido al worker."""

    participant_id: UUID
    session_id: UUID
    student_id: UUID
    reference_path: str
    reference_bucket: str
    #: Embedding ya calculado, si lo hay: evita recalcularlo en cada examen.
    reference_embedding: list[float] | None
    capture_path: str
    capture_bucket: str
    similarity_threshold: float

    @classmethod
    def from_entity(cls, job: FaceJob) -> FaceJobResponse:
        return cls(
            participant_id=job.participant_id,
            session_id=job.session_id,
            student_id=job.student_id,
            reference_path=job.reference_path,
            reference_bucket=job.reference_bucket,
            reference_embedding=job.reference_embedding,
            capture_path=job.capture_path,
            capture_bucket=job.capture_bucket,
            similarity_threshold=job.similarity_threshold,
        )


class FaceMeasurementRequest(BaseModel):
    """Lo que midio el modelo al comparar dos caras."""

    model_config = ConfigDict(extra="forbid")

    similarity: float | None = Field(default=None, ge=0, le=1)
    #: `True` cuando no se pudo medir: sin cara, con varias, o imagen ilegible.
    #: **No es lo mismo que "no coincide"**, y el docente tiene que distinguirlo.
    inconclusive: bool = False
    latency_ms: int | None = Field(default=None, ge=0)
    model_version: str | None = Field(default=None, max_length=120)
    reference_embedding: list[float] | None = Field(default=None, max_length=1024)


class IdentityCheckResponse(BaseModel):
    """El resultado aplicado: que concluyo y como quedo el participante."""

    result: IdentityResult
    similarity: float | None
    threshold: float
    latency_ms: int | None
    #: Si el estudiante ya puede rendir. Un fallo **no expulsa**: queda esperando
    #: a que el docente lo admita a mano.
    can_take_exam: bool
    verification_status: VerificationStatus

    @classmethod
    def from_entity(
        cls, check: IdentityCheck, participant: SessionParticipant
    ) -> IdentityCheckResponse:
        return cls(
            result=check.result,
            similarity=check.similarity,
            threshold=check.threshold,
            latency_ms=check.latency_ms,
            can_take_exam=participant.can_take_exam,
            verification_status=participant.verification_status,
        )


class RegisterReferenceFaceRequest(BaseModel):
    """Cuerpo de `POST /api/v1/me/reference-face`."""

    model_config = ConfigDict(extra="forbid")

    #: Ruta devuelta por `POST /api/v1/evidence/upload-url` con `kind=reference_face`.
    storage_path: str = Field(min_length=1, max_length=512)


class RequestIdentityCheckRequest(BaseModel):
    """Cuerpo de `POST /api/v1/exam/{session_id}/identity/check`."""

    model_config = ConfigDict(extra="forbid")

    #: Ruta de la captura recien tomada, ya subida con una URL firmada.
    capture_path: str = Field(min_length=1, max_length=512)


# ---------------------------------------------------------------------------
# Bancos de preguntas
# ---------------------------------------------------------------------------


class CreateQuestionBankRequest(BaseModel):
    """Cuerpo de `POST /api/v1/question-banks`."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    #: Opcional: un banco sin curso sirve para todos los examenes del docente.
    course_id: UUID | None = None
    description: str | None = Field(default=None, max_length=1000)


class QuestionBankResponse(BaseModel):
    """Un banco con cuantas preguntas tiene."""

    id: UUID
    name: str
    course_id: UUID | None
    description: str | None
    created_at: datetime
    question_count: int

    @classmethod
    def from_entity(cls, item: BankSummary) -> QuestionBankResponse:
        return cls(
            id=item.bank.id,
            name=item.bank.name,
            course_id=item.bank.course_id,
            description=item.bank.description,
            created_at=item.bank.created_at,
            question_count=item.question_count,
        )


class AttachBankRequest(BaseModel):
    """Cuerpo de `POST /api/v1/sessions/{id}/banks`."""

    model_config = ConfigDict(extra="forbid")

    bank_id: UUID


class AttachBankResponse(BaseModel):
    bank_id: UUID
    #: `True` si ya estaba atado. Atar dos veces no es un error.
    already_attached: bool


class UpdateExamSessionRequest(BaseModel):
    """Cuerpo de `PATCH /api/v1/sessions/{id}`.

    Todo es opcional: lo que no se envia no se toca. Para **vaciar** un campo
    opcional hay un `clear_*`, porque `null` ya significa "no lo cambies" y con
    un solo mecanismo no habria forma de quitarle la descripcion a un examen que
    ya la tiene.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    starts_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=600)
    entry_tolerance_minutes: int | None = Field(default=None, ge=0, le=120)
    description: str | None = Field(default=None, max_length=2000)
    course_id: UUID | None = None
    preset: SupervisionPreset | None = None
    max_score: Decimal | None = Field(default=None, gt=0, le=100)
    question_pool_size: int | None = Field(default=None, gt=0, le=500)
    shuffle_questions: bool | None = None
    shuffle_options: bool | None = None
    allow_back_navigation: bool | None = None
    clear_description: bool = False
    clear_course: bool = False
    #: Vuelve a "todas las preguntas del banco".
    clear_pool_size: bool = False

    def to_changes(self) -> ExamSessionChanges:
        return ExamSessionChanges(
            title=self.title,
            starts_at=self.starts_at,
            duration_minutes=self.duration_minutes,
            entry_tolerance_minutes=self.entry_tolerance_minutes,
            description=self.description,
            course_id=self.course_id,
            preset=self.preset,
            max_score=self.max_score,
            question_pool_size=self.question_pool_size,
            shuffle_questions=self.shuffle_questions,
            shuffle_options=self.shuffle_options,
            allow_back_navigation=self.allow_back_navigation,
            clear_description=self.clear_description,
            clear_course=self.clear_course,
            clear_pool_size=self.clear_pool_size,
        )


class UpdateQuestionRequest(BaseModel):
    """Cuerpo de `PATCH /api/v1/questions/{id}`.

    Corregir el enunciado o los puntos de una pregunta ya creada. Las opciones se
    envian **enteras** o no se envian: cambiar una sola dejaria al resto con
    posiciones inconsistentes.
    """

    model_config = ConfigDict(extra="forbid")

    statement: str | None = Field(default=None, min_length=1, max_length=5000)
    points: Decimal | None = Field(default=None, ge=0, le=100)
    options: list[QuestionOptionRequest] | None = None
    correct_numeric_answer: Decimal | None = None
    numeric_tolerance: Decimal | None = Field(default=None, ge=0)
    correct_text_answer: str | None = Field(default=None, max_length=1000)
