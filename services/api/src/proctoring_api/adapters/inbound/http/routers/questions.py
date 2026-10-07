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

from fastapi import APIRouter, Response, status

from proctoring_api.adapters.inbound.http.dependencies import (
    AddQuestionsDep,
    CurrentUserDep,
    DeleteQuestionDep,
    GetExamQuestionsDep,
    ListSessionQuestionsDep,
    UpdateQuestionDep,
)
from proctoring_api.adapters.inbound.http.schemas import (
    AddQuestionsRequest,
    ErrorResponse,
    ExamQuestionResponse,
    QuestionResponse,
    UpdateQuestionRequest,
)
from proctoring_api.application.use_cases.edit_questions import QuestionChanges

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


@router.patch(
    "/questions/{question_id}",
    response_model=QuestionResponse,
    summary="Corregir una pregunta (solo su docente)",
    responses={
        **AUTH_RESPONSES,
        400: {
            "model": ErrorResponse,
            "description": "Viola una regla, o alguien ya la respondio",
        },
    },
)
def update_question(
    question_id: UUID,
    payload: UpdateQuestionRequest,
    use_case: UpdateQuestionDep,
    current_user: CurrentUserDep,
) -> QuestionResponse:
    """Cambia el enunciado, los puntos o las alternativas.

    Solo mientras **nadie la haya respondido**: cambiarle la alternativa correcta
    a una pregunta ya contestada reescribiria en silencio la nota de quien la
    respondio bien.

    El tipo de pregunta no se cambia. Una de opcion multiple convertida en
    numerica no es una correccion, es otra pregunta: borrala y crea la nueva.
    """
    corregida = use_case.execute(
        question_id,
        QuestionChanges(
            statement=payload.statement,
            points=payload.points,
            options=(
                [(o.option_text, o.is_correct) for o in payload.options]
                if payload.options is not None
                else None
            ),
            correct_numeric_answer=payload.correct_numeric_answer,
            numeric_tolerance=payload.numeric_tolerance,
            correct_text_answer=payload.correct_text_answer,
        ),
        actor=current_user,
    )
    return QuestionResponse.from_entity(corregida)


@router.delete(
    "/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar una pregunta (solo su docente)",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "Alguien ya la respondio"},
    },
)
def delete_question(
    question_id: UUID,
    use_case: DeleteQuestionDep,
    current_user: CurrentUserDep,
) -> Response:
    """Quita la pregunta de su examen o de su banco.

    Las que quedan **no se renumeran**: las posiciones dejan huecos (1, 2, 4) y
    el orden se conserva, que es lo unico que `position` promete.
    """
    use_case.execute(question_id, actor=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
