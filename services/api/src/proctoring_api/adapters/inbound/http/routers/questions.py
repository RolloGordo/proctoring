"""Endpoints de preguntas.

Hay **dos** endpoints de lectura a propósito, no uno con un parámetro:

- `GET /api/v1/sessions/{id}/questions` → docente dueño, **con** respuestas.
- `GET /api/v1/exam/{id}/questions` → estudiante, **sin** respuestas.

Separarlos significa que no existe ninguna ruta por la que un estudiante pueda
pedir las respuestas correctas, ni aunque se equivoque alguien al tocar un
parámetro. Y cada uno devuelve un tipo distinto: el del estudiante no tiene
dónde guardar la respuesta.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from proctoring_api.adapters.inbound.http.dependencies import (
    AddQuestionsDep,
    CurrentUserDep,
    GetExamQuestionsDep,
    ListSessionQuestionsDep,
)
from proctoring_api.adapters.inbound.http.schemas import (
    AddQuestionsRequest,
    ErrorResponse,
    ExamQuestionResponse,
    QuestionResponse,
)

router = APIRouter(prefix="/api/v1", tags=["questions"])

AUTH_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse, "description": "Token ausente o invalido"},
    403: {"model": ErrorResponse, "description": "No puedes hacer esto"},
}


@router.post(
    "/sessions/{session_id}/questions",
    status_code=status.HTTP_201_CREATED,
    response_model=list[QuestionResponse],
    summary="Anadir preguntas a un examen (solo docente)",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "Viola una regla de dominio"},
        422: {"description": "El cuerpo no cumple el contrato"},
    },
)
def add_questions(
    session_id: UUID,
    payload: AddQuestionsRequest,
    use_case: AddQuestionsDep,
    current_user: CurrentUserDep,
) -> list[QuestionResponse]:
    """Anade preguntas al final del examen.

    Las preguntas se validan **todas** antes de guardar ninguna: si la tercera
    esta mal, el docente no se queda con dos sueltas y un error.
    """
    creadas = use_case.execute(
        session_id,
        [pregunta.to_input() for pregunta in payload.questions],
        actor=current_user,
    )
    return [QuestionResponse.from_entity(pregunta) for pregunta in creadas]


@router.get(
    "/sessions/{session_id}/questions",
    response_model=list[QuestionResponse],
    summary="Preguntas con sus respuestas correctas (solo docente)",
    responses=AUTH_RESPONSES,
)
def list_session_questions(
    session_id: UUID,
    use_case: ListSessionQuestionsDep,
    current_user: CurrentUserDep,
) -> list[QuestionResponse]:
    """Banco de preguntas del examen, con las respuestas correctas.

    Solo el docente dueno de la sesion. Un estudiante recibe 403 aunque este
    matriculado en ese examen.
    """
    return [
        QuestionResponse.from_entity(pregunta)
        for pregunta in use_case.execute(session_id, actor=current_user)
    ]


@router.get(
    "/exam/{session_id}/questions",
    response_model=list[ExamQuestionResponse],
    summary="Preguntas del examen para rendirlo (sin respuestas)",
    responses=AUTH_RESPONSES,
)
def get_exam_questions(
    session_id: UUID,
    use_case: GetExamQuestionsDep,
    current_user: CurrentUserDep,
) -> list[ExamQuestionResponse]:
    """El examen tal como lo ve el estudiante.

    Sin respuestas correctas y solo mientras el examen esta abierto: sin esa
    comprobacion, un estudiante podria descargar las preguntas la noche anterior.
    """
    return [
        ExamQuestionResponse.from_entity(pregunta)
        for pregunta in use_case.execute(session_id, actor=current_user)
    ]
