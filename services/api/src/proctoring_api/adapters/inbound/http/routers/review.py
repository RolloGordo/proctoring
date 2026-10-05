"""Endpoints de revisión de un caso y decisión del docente."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from proctoring_api.adapters.inbound.http.dependencies import (
    CurrentUserDep,
    ListDecisionsDep,
    RecordDecisionDep,
    ReviewCaseDep,
)
from proctoring_api.adapters.inbound.http.schemas import (
    CaseResponse,
    DecisionRequest,
    DecisionResponse,
    ErrorResponse,
)

router = APIRouter(prefix="/api/v1", tags=["review"])

AUTH_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse, "description": "Token ausente o invalido"},
    403: {"model": ErrorResponse, "description": "No puedes hacer esto"},
}


@router.get(
    "/sessions/{session_id}/students/{student_id}/case",
    response_model=CaseResponse,
    summary="Revisar el caso de un estudiante (solo docente dueño)",
    responses=AUTH_RESPONSES,
)
def review_case(
    session_id: UUID,
    student_id: UUID,
    use_case: ReviewCaseDep,
    current_user: CurrentUserDep,
) -> CaseResponse:
    """La evidencia reunida: senales, alertas, riesgo con su desglose y decisiones.

    Una sesion ajena, una inexistente y un estudiante que no participo responden
    lo mismo: distinguirlos permitiria averiguar que existe.
    """
    return CaseResponse.from_entity(use_case.execute(session_id, student_id, actor=current_user))


@router.post(
    "/sessions/{session_id}/students/{student_id}/decision",
    status_code=status.HTTP_201_CREATED,
    response_model=DecisionResponse,
    summary="Decidir sobre un caso, con justificación (solo docente dueño)",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "La justificacion es demasiado corta"},
    },
)
def record_decision(
    session_id: UUID,
    student_id: UUID,
    payload: DecisionRequest,
    use_case: RecordDecisionDep,
    current_user: CurrentUserDep,
) -> DecisionResponse:
    """Registra lo que el docente decide y por que.

    **No anula nada**: el sistema es un auditor, no un juez. La decision queda como
    evidencia y no se edita; si el docente cambia de parecer, registra otra.
    """
    return DecisionResponse.from_entity(
        use_case.execute(
            session_id,
            student_id,
            payload.decision,
            payload.justification,
            actor=current_user,
        )
    )


@router.get(
    "/sessions/{session_id}/decisions",
    response_model=list[DecisionResponse],
    summary="Decisiones de una sesión (solo docente dueño)",
    responses=AUTH_RESPONSES,
)
def list_decisions(
    session_id: UUID, use_case: ListDecisionsDep, current_user: CurrentUserDep
) -> list[DecisionResponse]:
    return [
        DecisionResponse.from_entity(d) for d in use_case.execute(session_id, actor=current_user)
    ]
