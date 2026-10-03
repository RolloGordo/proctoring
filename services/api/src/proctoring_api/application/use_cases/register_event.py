"""Caso de uso: registrar un evento de proctoring."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from proctoring_api.application.ports.alert_repository import AlertRepository
from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.event_repository import EventRepository
from proctoring_api.application.ports.job_queue import JobQueue
from proctoring_api.application.ports.question_repository import QuestionRepository
from proctoring_api.domain.alert import Alert, should_alert
from proctoring_api.domain.errors import AuthorizationError, InvalidEventError
from proctoring_api.domain.event import EventType, ProctoringEvent
from proctoring_api.domain.severity import Severity, default_severity
from proctoring_api.domain.user import AuthenticatedUser

#: Margen que se le concede al reloj del cliente.
#:
#: El `started_at` lo pone la maquina del estudiante, que puede ir desajustada unos
#: minutos. Un evento del pasado se acepta siempre (puede venir de un reintento tras
#: quedarse sin red), pero uno del futuro mas alla de este margen esta mal si o si y
#: romperia el orden cronologico de la evidencia, que es justo lo que el docente
#: revisa.
FUTURE_TOLERANCE = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class RegisterEventInput:
    """Datos de entrada, ya con los tipos correctos.

    Es un DTO del dominio de la aplicacion: no sabe nada de HTTP ni de Pydantic.
    """

    session_id: UUID
    student_id: UUID
    event_type: EventType
    started_at: datetime
    question_id: UUID | None = None
    duration_ms: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)
    evidence_path: str | None = None


@dataclass(frozen=True, slots=True)
class RegisterEventOutput:
    """Lo que el cliente necesita saber: que se guardo y con que severidad."""

    id: UUID
    severity: Severity


class RegisterEvent:
    """Autoriza, valida, persiste y, si hace falta, encola el analisis de audio."""

    def __init__(
        self,
        events: EventRepository,
        job_queue: JobQueue,
        clock: Clock,
        alerts: AlertRepository,
        questions: QuestionRepository | None = None,
    ) -> None:
        self._events = events
        self._job_queue = job_queue
        self._clock = clock
        self._alerts = alerts
        # `None` significa que no hay banco de preguntas con el que comprobar
        # (modo memoria en desarrollo). La composicion lo decide en main.py.
        self._questions = questions

    def execute(
        self, data: RegisterEventInput, *, actor: AuthenticatedUser | None = None
    ) -> RegisterEventOutput:
        """Registra el evento y devuelve su id y su severidad inicial.

        `actor` es quien hace la peticion. Es `None` **solo** cuando la
        autenticacion esta desactivada, que la configuracion unicamente permite en
        desarrollo local (ver `Settings.auth_enabled`): con `None` no se comprueba
        nada.

        Raises:
            AuthorizationError: si el actor no puede registrar este evento.
            InvalidEventError: si el evento viola una regla de dominio.
        """
        if actor is not None:
            self._authorize(data, actor)

        self._reject_if_from_the_future(data.started_at)
        self._reject_if_question_is_from_another_session(data)

        event = ProctoringEvent.create(
            session_id=data.session_id,
            student_id=data.student_id,
            question_id=data.question_id,
            event_type=data.event_type,
            started_at=data.started_at,
            duration_ms=data.duration_ms,
            metadata=data.metadata,
            evidence_path=data.evidence_path,
        )

        self._events.save(event)

        severity = default_severity(event.event_type, event.duration_ms)

        # Guardar la alerta ES notificar al docente: la tabla `alerts` esta
        # publicada en Supabase Realtime, asi que la insercion llega sola a su
        # navegador (ADR-0007). Esto es lo que sostiene la meta de avisar en
        # menos de 5 s.
        if should_alert(severity):
            self._alerts.save(Alert.from_event(event, severity, self._clock.now()))

        # El analisis de audio es lo caro: se encola y la peticion responde ya.
        # Solo despues de guardar, para que el worker siempre encuentre el evento.
        if event.needs_audio_analysis:
            self._job_queue.enqueue_audio_analysis(event.id)

        return RegisterEventOutput(id=event.id, severity=severity)

    @staticmethod
    def _authorize(data: RegisterEventInput, actor: AuthenticatedUser) -> None:
        """Solo el propio estudiante puede reportar eventos sobre si mismo.

        Esta comprobacion **no la cubre la base de datos**. RLS si la hace para
        escrituras directas desde el cliente, pero la API escribe con la service
        role key y omite RLS por completo. Si esto no estuviera aqui, cualquiera
        con un token valido podria fabricar evidencia contra otro estudiante, y
        esa evidencia termina delante de un docente que decide sobre una nota.
        """
        if actor.is_teacher:
            raise AuthorizationError(
                "Un docente no registra eventos de proctoring: los reporta el "
                "cliente del estudiante"
            )

        if actor.id != data.student_id:
            raise AuthorizationError("No puedes registrar eventos a nombre de otro estudiante")

    def _reject_if_question_is_from_another_session(self, data: RegisterEventInput) -> None:
        """La pregunta tiene que ser de esta sesion.

        Si no se comprueba, un cliente puede mandar el `question_id` de otro
        examen y el servicio de IA acabaria comparando la transcripcion del
        estudiante con el enunciado equivocado. La similitud saldria mal y la
        deteccion de IA por voz daria un resultado sin sentido, que es justo lo
        que el proyecto mide como falso positivo.
        """
        if data.question_id is None or self._questions is None:
            return

        session_id = self._questions.find_session_id(data.question_id)
        if session_id is None:
            raise InvalidEventError(f"La pregunta {data.question_id} no existe")
        if session_id != data.session_id:
            raise InvalidEventError(
                f"La pregunta {data.question_id} no pertenece a la sesion {data.session_id}"
            )

    def _reject_if_from_the_future(self, started_at: datetime) -> None:
        if started_at.tzinfo is None or started_at.utcoffset() is None:
            # Lo valida tambien la entidad; aqui se comprueba antes porque sin
            # zona horaria no se puede comparar con el reloj.
            raise InvalidEventError(
                "started_at debe traer zona horaria; usa ISO-8601 en UTC, "
                "por ejemplo 2026-10-03T14:21:05.120Z"
            )

        limit = self._clock.now() + FUTURE_TOLERANCE
        if started_at > limit:
            raise InvalidEventError(
                f"started_at esta en el futuro (mas de {int(FUTURE_TOLERANCE.total_seconds())} s "
                "por delante del servidor); revisa el reloj del equipo"
            )
