"""Revisión de un caso y decisión del docente."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from proctoring_api.application.ports.alert_repository import AlertRepository
from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.decision_repository import DecisionRepository
from proctoring_api.application.ports.event_repository import EventRepository
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.ports.participant_repository import ParticipantRepository
from proctoring_api.application.ports.profile_repository import ProfileRepository
from proctoring_api.application.session_access import ensure_teacher_owns_session
from proctoring_api.application.use_cases.create_exam_session import DEFAULT_DEV_TEACHER_ID
from proctoring_api.domain.alert import Alert
from proctoring_api.domain.decision import Decision, DecisionType
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.event import ProctoringEvent
from proctoring_api.domain.participant import SessionParticipant
from proctoring_api.domain.risk import RiskAssessment, assess_risk
from proctoring_api.domain.user import AuthenticatedUser, ProfileSummary


@dataclass(frozen=True, slots=True)
class CaseFile:
    """Todo lo que el docente necesita para decidir sobre un estudiante."""

    participant: SessionParticipant
    profile: ProfileSummary | None
    events: Sequence[ProctoringEvent]
    alerts: Sequence[Alert]
    #: Del más reciente al más antiguo. La primera es la vigente.
    decisions: Sequence[Decision]
    risk: RiskAssessment


class ReviewStudentCase:
    """Reúne la evidencia de un estudiante en un examen.

    Es la pantalla donde el docente **mira antes de decidir**: la línea de tiempo
    de señales, las alertas, el riesgo con su desglose y lo que ya se decidió.
    """

    def __init__(
        self,
        events: EventRepository,
        alerts: AlertRepository,
        sessions: ExamSessionRepository,
        participants: ParticipantRepository,
        profiles: ProfileRepository,
        decisions: DecisionRepository,
    ) -> None:
        self._events = events
        self._alerts = alerts
        self._sessions = sessions
        self._participants = participants
        self._profiles = profiles
        self._decisions = decisions

    def execute(
        self, session_id: UUID, student_id: UUID, *, actor: AuthenticatedUser | None = None
    ) -> CaseFile:
        """Raises:
        AuthorizationError: si no es un docente, si la sesion no es suya, o si
            ese estudiante no participo en ella. Se responde lo mismo en los
            tres casos para no revelar que sesiones o estudiantes existen.
        """
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo el docente revisa un caso")
        ensure_teacher_owns_session(self._sessions, session_id, actor)

        participante = self._participants.find(session_id, student_id)
        if participante is None:
            raise AuthorizationError("No tienes acceso a este caso")

        eventos = self._events.list_by_session(session_id, student_id)
        perfiles = self._profiles.get_summaries([student_id])
        return CaseFile(
            participant=participante,
            profile=perfiles.get(student_id),
            events=eventos,
            alerts=self._alerts.list_by_session(session_id, student_id),
            decisions=self._decisions.list_by_session(session_id, student_id),
            risk=assess_risk(eventos),
        )


class RecordDecision:
    """El docente decide sobre un caso, con justificación obligatoria.

    No anula nada ni cambia el examen del estudiante: **registra** lo que el
    docente decidió y por qué. Es un auditor, no un juez.
    """

    def __init__(
        self,
        decisions: DecisionRepository,
        sessions: ExamSessionRepository,
        participants: ParticipantRepository,
        clock: Clock,
        dev_teacher_id: UUID = DEFAULT_DEV_TEACHER_ID,
    ) -> None:
        self._decisions = decisions
        self._sessions = sessions
        self._participants = participants
        self._clock = clock
        self._dev_teacher_id = dev_teacher_id

    def execute(
        self,
        session_id: UUID,
        student_id: UUID,
        decision: DecisionType,
        justification: str,
        *,
        actor: AuthenticatedUser | None = None,
    ) -> Decision:
        """Raises:
        AuthorizationError: si no es un docente, si la sesion no es suya o si el
            estudiante no participo en ella.
        InvalidDecisionError: si la justificacion es demasiado corta.
        """
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo el docente decide sobre un caso")
        ensure_teacher_owns_session(self._sessions, session_id, actor)

        if self._participants.find(session_id, student_id) is None:
            raise AuthorizationError("No tienes acceso a este caso")

        # Se valida y se construye ANTES de guardar: una justificacion corta no
        # deja ninguna decision a medias.
        registrada = Decision.create(
            session_id=session_id,
            student_id=student_id,
            teacher_id=actor.id if actor is not None else self._dev_teacher_id,
            decision=decision,
            justification=justification,
            decided_at=self._clock.now(),
        )
        self._decisions.save(registrada)
        return registrada


class ListSessionDecisions:
    """Las decisiones de una sesión, para ver cuáles casos ya se resolvieron."""

    def __init__(
        self, decisions: DecisionRepository, sessions: ExamSessionRepository | None = None
    ) -> None:
        self._decisions = decisions
        self._sessions = sessions

    def execute(
        self, session_id: UUID, *, actor: AuthenticatedUser | None = None
    ) -> Sequence[Decision]:
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo el docente ve las decisiones")
        ensure_teacher_owns_session(self._sessions, session_id, actor)
        return self._decisions.list_by_session(session_id)
