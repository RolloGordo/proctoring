"""Endpoints de eventos de proctoring.

El router solo traduce: JSON -> DTO, llama al caso de uso, DTO -> JSON. Toda la
regla de negocio vive en `application/` y en `domain/`.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, status

from proctoring_api.adapters.inbound.http.dependencies import (
    ListSessionEventsDep,
    RegisterEventDep,
)
from proctoring_api.adapters.inbound.http.schemas import (
    ErrorResponse,
    EventCreatedResponse,
    EventRequest,
    EventResponse,
)
from proctoring_api.application.use_cases.register_event import RegisterEventInput
from proctoring_api.domain.severity import default_severity

router = APIRouter(prefix="/api/v1", tags=["events"])


@router.post(
    "/events",
    status_code=status.HTTP_201_CREATED,
    response_model=EventCreatedResponse,
    summary="Registrar un evento de proctoring",
    responses={
        400: {"model": ErrorResponse, "description": "Viola una regla de dominio"},
        422: {"description": "El cuerpo no cumple el contrato"},
    },
)
def register_event(
    payload: EventRequest,
    use_case: RegisterEventDep,
) -> EventCreatedResponse:
    """Registra una senal detectada durante un examen.

    Responde al instante. Si el evento es `speech_detected`, el analisis de audio
    queda encolado para `services/ai` y su resultado llega despues por otra via.
    """
    result = use_case.execute(
        RegisterEventInput(
            session_id=payload.session_id,
            student_id=payload.student_id,
            event_type=payload.event_type,
            started_at=payload.started_at,
            question_id=payload.question_id,
            duration_ms=payload.duration_ms,
            metadata=payload.metadata,
            evidence_path=payload.evidence_path,
        )
    )
    return EventCreatedResponse(id=result.id, severity=result.severity)


@router.get(
    "/sessions/{session_id}/events",
    response_model=list[EventResponse],
    summary="Eventos de una sesion",
)
def list_session_events(
    session_id: UUID,
    use_case: ListSessionEventsDep,
    student_id: UUID | None = Query(default=None, description="Filtrar por estudiante"),
) -> list[EventResponse]:
    """Linea de tiempo de senales de una sesion, en orden cronologico.

    Es lo que alimenta la pantalla de revision del docente.
    """
    events = use_case.execute(session_id, student_id)
    return [
        EventResponse.from_entity(event, default_severity(event.event_type, event.duration_ms))
        for event in events
    ]
