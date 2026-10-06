"""Lo que el servicio de IA pide y lo que devuelve.

**Este módulo es el contrato con `services/ai`.** El worker no conoce el esquema
de la base ni las reglas: pide un trabajo, mide, y devuelve lo medido. La API
decide qué significa.

El reparto es deliberado:

| Quién | Qué hace |
|---|---|
| `services/ai` | transcribe, calcula similitud, puntúa la voz, compara caras |
| la API (aquí) | aplica los umbrales de la sesión, decide si hay alerta, escribe la evidencia |

Así la regla que define el proyecto —alertar **solo** si lo dicho se parece al
enunciado **y** hay una segunda voz sintética— vive en un sitio, con pruebas, y se
puede calibrar sin tocar el worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from proctoring_api.application.ports.alert_repository import AlertRepository
from proctoring_api.application.ports.audio_analysis_repository import AudioAnalysisRepository
from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.event_repository import EventRepository
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.ports.job_queue import JobQueue
from proctoring_api.application.ports.participant_repository import ParticipantRepository
from proctoring_api.application.ports.question_repository import QuestionRepository
from proctoring_api.application.ports.reference_face_repository import (
    ReferenceFace,
    ReferenceFaceRepository,
)
from proctoring_api.application.use_cases.manage_enrollment import (
    DEFAULT_DEV_STUDENT_ID,
    ensure_can_take_exam,
)
from proctoring_api.domain.alert import Alert
from proctoring_api.domain.audio_analysis import AiVoiceThresholds, AudioAnalysis
from proctoring_api.domain.errors import AuthorizationError, DomainError
from proctoring_api.domain.event import EventType, ProctoringEvent
from proctoring_api.domain.exam_session import SupervisionModule
from proctoring_api.domain.identity import IdentityCheck, threshold_from_settings
from proctoring_api.domain.participant import SessionParticipant
from proctoring_api.domain.severity import Severity
from proctoring_api.domain.user import AuthenticatedUser


class JobNotFoundError(DomainError):
    """El trabajo pedido no existe o ya no tiene con qué ejecutarse."""


@dataclass(frozen=True, slots=True)
class AudioJob:
    """Todo lo que el worker necesita para analizar un fragmento de audio.

    Viene servido para que el worker **no consulte la base**: si lo hiciera,
    tendría que conocer el esquema y quedarían dos sitios que mantener.
    """

    event_id: UUID
    session_id: UUID
    student_id: UUID
    question_id: UUID | None
    #: El enunciado con el que comparar la transcripción. `None` si la pregunta
    #: ya no existe; entonces no hay nada que comparar.
    question_statement: str | None
    #: Ruta dentro del bucket de audio. El worker la descarga de Storage.
    audio_path: str
    audio_bucket: str
    #: Los umbrales de **esta** sesión. El worker los recibe para poder registrar
    #: con qué se comparó, no para decidir con ellos.
    similarity_threshold: float
    synthetic_threshold: float


@dataclass(frozen=True, slots=True)
class AudioMeasurement:
    """Lo que el worker midió. Todo opcional: un análisis puede fallar a medias."""

    transcript: str | None = None
    similarity: float | None = None
    synthetic_voice_score: float | None = None
    processing_ms: int | None = None
    model_versions: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class AudioAnalysisOutcome:
    analysis: AudioAnalysis
    #: Si se creó una alerta para el docente.
    alerted: bool


class GetAudioJob:
    """Entrega al worker lo que necesita para analizar un evento de habla."""

    def __init__(
        self,
        events: EventRepository,
        sessions: ExamSessionRepository,
        questions: QuestionRepository,
        audio_bucket: str,
    ) -> None:
        self._events = events
        self._sessions = sessions
        self._questions = questions
        self._audio_bucket = audio_bucket

    def execute(self, event_id: UUID) -> AudioJob:
        """Raises:
        JobNotFoundError: si el evento no existe, no es de habla o no trae
            audio. Sin audio no hay nada que transcribir.
        """
        event = self._events.find_by_id(event_id)
        if event is None:
            raise JobNotFoundError("No existe ese evento")
        if event.event_type is not EventType.SPEECH_DETECTED:
            raise JobNotFoundError("Ese evento no es de habla")
        if not event.evidence_path:
            raise JobNotFoundError("Ese evento no trae audio que analizar")

        session = self._sessions.find_by_id(event.session_id)
        thresholds = AiVoiceThresholds.from_settings(
            session.modules.get(SupervisionModule.AI_VOICE) if session else None
        )

        return AudioJob(
            event_id=event.id,
            session_id=event.session_id,
            student_id=event.student_id,
            question_id=event.question_id,
            question_statement=self._statement_of(event),
            audio_path=event.evidence_path,
            audio_bucket=self._audio_bucket,
            similarity_threshold=thresholds.similarity,
            synthetic_threshold=thresholds.synthetic,
        )

    def _statement_of(self, event: ProctoringEvent) -> str | None:
        if event.question_id is None:
            return None
        pregunta = next(
            (
                q
                for q in self._questions.list_by_session(event.session_id)
                if q.id == event.question_id
            ),
            None,
        )
        return pregunta.statement if pregunta else None


class RecordAudioAnalysis:
    """Guarda lo medido y decide si el docente debe enterarse.

    **La decisión vive aquí.** El worker nunca crea alertas: si lo hiciera, la
    regla de las dos condiciones estaría en un proceso aparte, sin las pruebas
    de la API y sin los umbrales de la sesión.
    """

    def __init__(
        self,
        analyses: AudioAnalysisRepository,
        events: EventRepository,
        sessions: ExamSessionRepository,
        alerts: AlertRepository,
        clock: Clock,
    ) -> None:
        self._analyses = analyses
        self._events = events
        self._sessions = sessions
        self._alerts = alerts
        self._clock = clock

    def execute(self, event_id: UUID, measurement: AudioMeasurement) -> AudioAnalysisOutcome:
        """Raises:
        JobNotFoundError: si el evento no existe.
        InvalidAudioAnalysisError: si una medida está fuera de rango.
        """
        event = self._events.find_by_id(event_id)
        if event is None:
            raise JobNotFoundError("No existe ese evento")

        ahora = self._clock.now()
        analysis = AudioAnalysis.create(
            event_id=event_id,
            processed_at=ahora,
            transcript=measurement.transcript,
            similarity=measurement.similarity,
            synthetic_voice_score=measurement.synthetic_voice_score,
            matched_question_id=event.question_id,
            processing_ms=measurement.processing_ms,
            model_versions=measurement.model_versions,
        )
        self._analyses.save(analysis)

        session = self._sessions.find_by_id(event.session_id)
        thresholds = AiVoiceThresholds.from_settings(
            session.modules.get(SupervisionModule.AI_VOICE) if session else None
        )

        # Solo aquí se escala. `speech_detected` nace siempre con severidad baja
        # precisamente para que hablar en voz alta no alerte por sí solo.
        if not analysis.is_ai_consultation(thresholds):
            return AudioAnalysisOutcome(analysis=analysis, alerted=False)

        self._alerts.save(
            Alert(
                id=uuid4(),
                event_id=event.id,
                session_id=event.session_id,
                student_id=event.student_id,
                severity=Severity.HIGH,
                reason=analysis.alert_reason(),
                created_at=ahora,
            )
        )
        return AudioAnalysisOutcome(analysis=analysis, alerted=True)


@dataclass(frozen=True, slots=True)
class FaceJob:
    """Lo que el worker necesita para verificar una identidad."""

    participant_id: UUID
    session_id: UUID
    student_id: UUID
    #: Ruta de la cara registrada una vez por el estudiante.
    reference_path: str
    reference_bucket: str
    #: Embedding ya calculado, si lo hay. Evita recalcularlo en cada examen.
    reference_embedding: list[float] | None
    #: La captura del momento, tomada al entrar al examen.
    capture_path: str
    capture_bucket: str
    similarity_threshold: float


@dataclass(frozen=True, slots=True)
class FaceMeasurement:
    """Lo que midió el modelo al comparar las dos caras."""

    similarity: float | None = None
    #: `True` cuando no se pudo medir: sin cara, con varias, o imagen ilegible.
    inconclusive: bool = False
    latency_ms: int | None = None
    model_version: str | None = None
    #: Embedding de la referencia, para guardarlo y no recalcularlo.
    reference_embedding: list[float] | None = None


@dataclass(frozen=True, slots=True)
class IdentityOutcome:
    participant: SessionParticipant
    check: IdentityCheck


class RecordIdentityCheck:
    """Aplica el resultado de la verificación facial al participante.

    Una verificación fallida **no expulsa**: deja al estudiante esperando, y el
    docente lo admite a mano desde su sala de espera.
    """

    def __init__(
        self,
        participants: ParticipantRepository,
        sessions: ExamSessionRepository,
        events: EventRepository,
        faces: ReferenceFaceRepository,
        clock: Clock,
    ) -> None:
        self._participants = participants
        self._sessions = sessions
        self._events = events
        self._faces = faces
        self._clock = clock

    def execute(
        self, session_id: UUID, student_id: UUID, measurement: FaceMeasurement
    ) -> IdentityOutcome:
        """Raises:
        JobNotFoundError: si ese estudiante no participa en esa sesión.
        """
        participante = self._participants.find(session_id, student_id)
        if participante is None:
            raise JobNotFoundError("Ese estudiante no esta en esta sesion")

        session = self._sessions.find_by_id(session_id)
        umbral = threshold_from_settings(
            session.modules.get(SupervisionModule.FACE_VERIFICATION) if session else None
        )
        check = IdentityCheck.from_similarity(
            measurement.similarity,
            threshold=umbral,
            latency_ms=measurement.latency_ms,
            model_version=measurement.model_version,
            inconclusive=measurement.inconclusive,
        )

        ahora = self._clock.now()
        actualizado = (
            participante.verified(ahora) if check.verified else participante.verification_failed()
        )
        self._participants.save(actualizado)

        # El resultado queda como evidencia, pase o falle: es lo que después
        # sostiene el informe de accuracy y de FAR/FRR.
        self._events.save(
            ProctoringEvent.create(
                session_id=session_id,
                student_id=student_id,
                question_id=None,
                event_type=EventType.IDENTITY_CHECK,
                started_at=ahora,
                duration_ms=measurement.latency_ms or 0,
                metadata=check.as_metadata(),
            )
        )

        # Guardar el embedding ahorra recalcularlo en el siguiente examen.
        if measurement.reference_embedding is not None:
            referencia = self._faces.find(student_id)
            if referencia is not None:
                self._faces.save(
                    ReferenceFace(
                        student_id=referencia.student_id,
                        storage_path=referencia.storage_path,
                        embedding=measurement.reference_embedding,
                        model_version=measurement.model_version,
                        registered_at=referencia.registered_at,
                    )
                )

        return IdentityOutcome(participant=actualizado, check=check)


class ReferenceFaceMissingError(DomainError):
    """El estudiante todavía no registró su cara de referencia."""


class RegisterReferenceFace:
    """El estudiante registra, una vez, la cara con la que se le comparará.

    Solo se guarda **la ruta**: la imagen va directo a Storage con una URL
    firmada, igual que el resto de la evidencia. El embedding lo calcula el
    servicio de IA la primera vez que la usa.
    """

    def __init__(
        self,
        faces: ReferenceFaceRepository,
        clock: Clock,
        dev_student_id: UUID = DEFAULT_DEV_STUDENT_ID,
    ) -> None:
        self._faces = faces
        self._clock = clock
        self._dev_student_id = dev_student_id

    def execute(
        self, storage_path: str, *, actor: AuthenticatedUser | None = None
    ) -> ReferenceFace:
        """Raises:
        AuthorizationError: si lo pide un docente. La cara de referencia es del
            estudiante, y nadie la registra por él.
        """
        if actor is not None and actor.is_teacher:
            raise AuthorizationError("La cara de referencia la registra el propio estudiante")

        quien = actor.id if actor is not None else self._dev_student_id
        # Registrar otra vez **reemplaza**: si alguien cambia de aspecto o la
        # primera foto salió mal, tiene que poder rehacerla.
        face = ReferenceFace(
            student_id=quien,
            storage_path=storage_path,
            embedding=None,
            model_version=None,
            registered_at=self._clock.now(),
        )
        self._faces.save(face)
        return face


class RequestIdentityCheck:
    """El estudiante manda una captura y pide que se verifique su identidad.

    Devuelve en seguida: la comparación la hace el worker y el resultado llega
    por `RecordIdentityCheck`. La sala de espera ya se actualiza sola.
    """

    def __init__(
        self,
        participants: ParticipantRepository,
        faces: ReferenceFaceRepository,
        queue: JobQueue,
        dev_student_id: UUID = DEFAULT_DEV_STUDENT_ID,
    ) -> None:
        self._participants = participants
        self._faces = faces
        self._queue = queue
        self._dev_student_id = dev_student_id

    def execute(
        self, session_id: UUID, capture_path: str, *, actor: AuthenticatedUser | None = None
    ) -> SessionParticipant:
        """Raises:
        AuthorizationError: si lo pide un docente o si no está matriculado.
        ReferenceFaceMissingError: si no registró su cara de referencia.
        """
        if actor is not None and actor.is_teacher:
            raise AuthorizationError("Un docente no verifica su identidad para rendir")

        quien = actor.id if actor is not None else self._dev_student_id
        participante = self._participants.find(session_id, quien)
        if participante is None:
            raise AuthorizationError("No estas matriculado en este examen")
        if not participante.has_consented:
            raise AuthorizationError("Tienes que aceptar la supervision antes de verificarte")

        if self._faces.find(quien) is None:
            raise ReferenceFaceMissingError(
                "Primero registra tu rostro de referencia desde tu panel."
            )

        self._queue.enqueue_face_verification(participante.id, capture_path)
        return participante


class GetFaceJob:
    """Entrega al worker lo que necesita para comparar dos caras."""

    def __init__(
        self,
        participants: ParticipantRepository,
        sessions: ExamSessionRepository,
        faces: ReferenceFaceRepository,
        reference_bucket: str,
        capture_bucket: str,
    ) -> None:
        self._participants = participants
        self._sessions = sessions
        self._faces = faces
        self._reference_bucket = reference_bucket
        self._capture_bucket = capture_bucket

    def execute(self, participant_id: UUID, capture_path: str) -> FaceJob:
        """Raises:
        JobNotFoundError: si la matrícula no existe o el estudiante no tiene
            cara de referencia. Sin referencia no hay con qué comparar.
        """
        participante = self._participants.find_by_id(participant_id)
        if participante is None:
            raise JobNotFoundError("No existe esa matricula")

        referencia = self._faces.find(participante.student_id)
        if referencia is None:
            raise JobNotFoundError("Ese estudiante no tiene cara de referencia")

        session = self._sessions.find_by_id(participante.session_id)
        umbral = threshold_from_settings(
            session.modules.get(SupervisionModule.FACE_VERIFICATION) if session else None
        )

        return FaceJob(
            participant_id=participante.id,
            session_id=participante.session_id,
            student_id=participante.student_id,
            reference_path=referencia.storage_path,
            reference_bucket=self._reference_bucket,
            reference_embedding=referencia.embedding,
            capture_path=capture_path,
            capture_bucket=self._capture_bucket,
            similarity_threshold=umbral,
        )


__all__ = [
    "AudioAnalysisOutcome",
    "AudioJob",
    "AudioMeasurement",
    "FaceJob",
    "FaceMeasurement",
    "GetAudioJob",
    "GetFaceJob",
    "IdentityOutcome",
    "JobNotFoundError",
    "RecordAudioAnalysis",
    "RecordIdentityCheck",
    "ReferenceFaceMissingError",
    "RegisterReferenceFace",
    "RequestIdentityCheck",
    "ensure_can_take_exam",
]
