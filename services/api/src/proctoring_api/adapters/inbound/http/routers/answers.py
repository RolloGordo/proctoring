"""Endpoints de respuestas del estudiante."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from proctoring_api.adapters.inbound.http.dependencies import (
    CurrentUserDep,
    ListMyAnswersDep,
    SaveAnswersDep,
)
from proctoring_api.adapters.inbound.http.schemas import (
    AnswerResponse,
    ErrorResponse,
    SaveAnswersRequest,
)
from proctoring_api.application.use_cases.manage_answers import AnswerInput

router = APIRouter(prefix="/api/v1/exam", tags=["answers"])

AUTH_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse, "description": "Token ausente o invalido"},
    403: {"model": ErrorResponse, "description": "No puedes responder este examen"},
}


@router.put(
    "/{session_id}/answers",
    response_model=list[AnswerResponse],
    summary="Guardar respuestas",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "La respuesta no corresponde a la pregunta"},
    },
)
def save_answers(
    session_id: UUID,
    payload: SaveAnswersRequest,
    use_case: SaveAnswersDep,
    current_user: CurrentUserDep,
) -> list[AnswerResponse]:
    """Guarda lo respondido. Es PUT porque responder otra vez **reemplaza**.

    La pantalla del examen llama aqui cada vez que el estudiante cambia una
    respuesta, no solo al entregar: si el equipo se reinicia a mitad del examen,
    lo respondido tiene que seguir ahi.
    """
    entradas = [
        AnswerInput(
            question_id=respuesta.question_id,
            selected_option_id=respuesta.selected_option_id,
            text_answer=respuesta.text_answer,
            numeric_answer=respuesta.numeric_answer,
        )
        for respuesta in payload.answers
    ]
    return [
        AnswerResponse.from_entity(guardada)
        for guardada in use_case.execute(session_id, entradas, actor=current_user)
    ]


@router.get(
    "/{session_id}/answers",
    response_model=list[AnswerResponse],
    summary="Mis respuestas de este examen",
    responses=AUTH_RESPONSES,
)
def my_answers(
    session_id: UUID,
    use_case: ListMyAnswersDep,
    current_user: CurrentUserDep,
) -> list[AnswerResponse]:
    """Lo ya respondido, para retomar el examen donde se quedo.

    Devuelve solo las respuestas de quien pregunta: la matricula se busca por el
    token, nunca por un id que venga del cliente.
    """
    return [
        AnswerResponse.from_entity(respuesta)
        for respuesta in use_case.execute(session_id, actor=current_user)
    ]
