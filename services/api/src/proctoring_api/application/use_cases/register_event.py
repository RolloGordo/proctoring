"""Caso de uso: registrar un evento de proctoring."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.event_repository import EventRepository
from proctoring_api.application.ports.job_queue import JobQueue
from proctoring_api.domain.errors import InvalidEventError
from proctoring_api.domain.event import EventType, ProctoringEvent
from proctoring_api.domain.severity import Severity, default_severity

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
    """Valida, persiste y, si hace falta, encola el analisis de audio."""

    def __init__(
        self,
        events: EventRepository,
        job_queue: JobQueue,
        clock: Clock,
    ) -> None:
        self._events = events
        self._job_queue = job_queue
        self._clock = clock

    def execute(self, data: RegisterEventInput) -> RegisterEventOutput:
        """Registra el evento y devuelve su id y su severidad inicial.

        Raises:
            InvalidEventError: si el evento viola una regla de dominio o de
                aplicacion. El adaptador HTTP lo traduce a 400.
        """
        self._reject_if_from_the_future(data.started_at)

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

        # El analisis de audio es lo caro: se encola y la peticion responde ya.
        # Solo despues de guardar, para que el worker siempre encuentre el evento.
        if event.needs_audio_analysis:
            self._job_queue.enqueue_audio_analysis(event.id)

        return RegisterEventOutput(
            id=event.id,
            severity=default_severity(event.event_type, event.duration_ms),
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
