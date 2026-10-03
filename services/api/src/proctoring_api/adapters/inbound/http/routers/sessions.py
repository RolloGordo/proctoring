"""Endpoints de sesiones de examen."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from proctoring_api.adapters.inbound.http.dependencies import (
    CreateExamSessionDep,
    CurrentUserDep,
    GetExamSessionDep,
    ListTeacherSessionsDep,
)
from proctoring_api.adapters.inbound.http.schemas import (
    ErrorResponse,
    ExamSessionRequest,
    ExamSessionResponse,
    ExamSessionSummary,
)
from proctoring_api.application.use_cases.create_exam_session import CreateExamSessionInput

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

AUTH_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse, "description": "Token ausente o invalido"},
    403: {"model": ErrorResponse, "description": "No puedes hacer esto"},
}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ExamSessionResponse,
    summary="Crear una sesion de examen",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "Viola una regla de dominio"},
        422: {"description": "El cuerpo no cumple el contrato"},
    },
)
def create_exam_session(
    payload: ExamSessionRequest,
    use_case: CreateExamSessionDep,
    current_user: CurrentUserDep,
) -> ExamSessionResponse:
    """Programa un examen y devuelve su codigo de acceso.

    El `preset` decide que modulos de deteccion se activan y con que umbrales.
    Con `custom` hay que enviarlos a mano en `modules`.

    El `access_code` se genera aqui y es lo que el estudiante teclea para entrar.
    """
    session = use_case.execute(
        CreateExamSessionInput(
            title=payload.title,
            starts_at=payload.starts_at,
            duration_minutes=payload.duration_minutes,
            course_id=payload.course_id,
            description=payload.description,
            entry_tolerance_minutes=payload.entry_tolerance_minutes,
            preset=payload.preset,
            max_attempts=payload.max_attempts,
            shuffle_questions=payload.shuffle_questions,
            shuffle_options=payload.shuffle_options,
            allow_back_navigation=payload.allow_back_navigation,
            modules=payload.modules or {},
        ),
        actor=current_user,
    )
    return ExamSessionResponse.from_entity(session)


@router.get(
    "",
    response_model=list[ExamSessionSummary],
    summary="Mis sesiones de examen",
    responses=AUTH_RESPONSES,
)
def list_my_sessions(
    use_case: ListTeacherSessionsDep,
    current_user: CurrentUserDep,
) -> list[ExamSessionSummary]:
    """Sesiones del docente que pregunta, de la mas proxima a la mas antigua.

    El id del docente sale del token, no de un parametro: asi no hay forma de
    pedir las de otro.
    """
    return [
        ExamSessionSummary.from_entity(session) for session in use_case.execute(actor=current_user)
    ]


@router.get(
    "/{session_id}",
    response_model=ExamSessionResponse,
    summary="Detalle de una sesion",
    responses=AUTH_RESPONSES,
)
def get_exam_session(
    session_id: UUID,
    use_case: GetExamSessionDep,
    current_user: CurrentUserDep,
) -> ExamSessionResponse:
    """Sesion con sus modulos y umbrales.

    Una sesion ajena y una inexistente responden lo mismo (403), para no
    permitir averiguar que sesiones existen.
    """
    return ExamSessionResponse.from_entity(use_case.execute(session_id, actor=current_user))
