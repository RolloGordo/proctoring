"""Endpoints de eventos de proctoring.

El router solo traduce: JSON -> DTO, llama al caso de uso, DTO -> JSON. Toda la
regla de negocio y de autorizacion vive en `application/` y en `domain/`.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, status

from proctoring_api.adapters.inbound.http.dependencies import (
    CurrentUserDep,
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

AUTH_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse, "description": "Token ausente o invalido"},
    403: {"model": ErrorResponse, "description": "No puedes hacer esto"},
}


@router.post(
    "/events",
    status_code=status.HTTP_201_CREATED,
    response_model=EventCreatedResponse,
    summary="Registrar un evento de proctoring",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "Viola una regla de dominio"},
        422: {"description": "El cuerpo no cumple el contrato"},
    },
)
def register_event(
    payload: EventRequest,
    use_case: RegisterEventDep,
    current_user: CurrentUserDep,
) -> EventCreatedResponse:
    """Registra una senal detectada durante un examen.

    Lo llama el cliente del estudiante, que solo puede reportar eventos **sobre si
    mismo**: el `student_id` del cuerpo tiene que coincidir con el del token.

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
        ),
        actor=current_user,
    )
    return EventCreatedResponse(id=result.id, severity=result.severity)


@router.get(
    "/sessions/{session_id}/events",
    response_model=list[EventResponse],
    summary="Eventos de una sesion",
    responses=AUTH_RESPONSES,
)
def list_session_events(
    session_id: UUID,
    use_case: ListSessionEventsDep,
    current_user: CurrentUserDep,
    student_id: UUID | None = Query(default=None, description="Filtrar por estudiante"),
) -> list[EventResponse]:
    """Linea de tiempo de senales de una sesion, en orden cronologico.

    Es lo que alimenta la pantalla de revision del docente. Un estudiante solo ve
    los suyos: el filtro que pida se ignora y se fuerza a su propio id.
    """
    events = use_case.execute(session_id, actor=current_user, student_id=student_id)
    return [
        EventResponse.from_entity(event, default_severity(event.event_type, event.duration_ms))
        for event in events
    ]
