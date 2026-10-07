"""Endpoints de bancos de preguntas."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Response, status

from proctoring_api.adapters.inbound.http.dependencies import (
    AddQuestionsToBankDep,
    AttachBankDep,
    CreateBankDep,
    CurrentUserDep,
    DetachBankDep,
    ListBankQuestionsDep,
    ListBanksDep,
    ListSessionBanksDep,
)
from proctoring_api.adapters.inbound.http.schemas import (
    AddQuestionsRequest,
    AttachBankRequest,
    AttachBankResponse,
    CreateQuestionBankRequest,
    ErrorResponse,
    QuestionBankResponse,
    QuestionResponse,
)
from proctoring_api.application.use_cases.manage_banks import BankSummary

router = APIRouter(prefix="/api/v1", tags=["question-banks"])

AUTH_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse, "description": "Token ausente o invalido"},
    403: {"model": ErrorResponse, "description": "No puedes hacer esto"},
}


@router.post(
    "/question-banks",
    status_code=status.HTTP_201_CREATED,
    response_model=QuestionBankResponse,
    summary="Crear un banco de preguntas (solo docente)",
    responses=AUTH_RESPONSES,
)
def create_bank(
    payload: CreateQuestionBankRequest, use_case: CreateBankDep, current_user: CurrentUserDep
) -> QuestionBankResponse:
    """Crea un banco del docente que lo pide.

    `course_id` es opcional: un banco sin curso sirve para todos sus examenes.
    """
    bank = use_case.execute(
        payload.name,
        course_id=payload.course_id,
        description=payload.description,
        actor=current_user,
    )
    return QuestionBankResponse.from_entity(BankSummary(bank=bank, question_count=0))


@router.get(
    "/question-banks",
    response_model=list[QuestionBankResponse],
    summary="Mis bancos (solo docente)",
    responses=AUTH_RESPONSES,
)
def list_banks(use_case: ListBanksDep, current_user: CurrentUserDep) -> list[QuestionBankResponse]:
    """Los bancos del docente, con cuantas preguntas tiene cada uno.

    El docente sale del token: no hay parametro con el que pedir los de otro.
    """
    return [QuestionBankResponse.from_entity(b) for b in use_case.execute(actor=current_user)]


@router.get(
    "/question-banks/{bank_id}/questions",
    response_model=list[QuestionResponse],
    summary="Preguntas de un banco, con sus respuestas (solo su docente)",
    responses=AUTH_RESPONSES,
)
def list_bank_questions(
    bank_id: UUID, use_case: ListBankQuestionsDep, current_user: CurrentUserDep
) -> list[QuestionResponse]:
    """Un banco ajeno y uno inexistente responden lo mismo."""
    return [QuestionResponse.from_entity(q) for q in use_case.execute(bank_id, actor=current_user)]


@router.post(
    "/question-banks/{bank_id}/questions",
    status_code=status.HTTP_201_CREATED,
    response_model=list[QuestionResponse],
    summary="Anadir preguntas a un banco (solo su docente)",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "Alguna pregunta viola una regla"},
    },
)
def add_bank_questions(
    bank_id: UUID,
    payload: AddQuestionsRequest,
    use_case: AddQuestionsToBankDep,
    current_user: CurrentUserDep,
) -> list[QuestionResponse]:
    """Anade preguntas al final del banco.

    Es tambien el destino de la importacion QTI: el parser produce esta misma
    forma. Si una del lote es invalida **no se guarda ninguna**, para que importar
    cuarenta no deje veintinueve a medias.
    """
    nuevas = [p.to_input() for p in payload.questions]
    creadas = use_case.execute(bank_id, nuevas, actor=current_user)
    return [QuestionResponse.from_entity(q) for q in creadas]


@router.get(
    "/sessions/{session_id}/banks",
    response_model=list[QuestionBankResponse],
    summary="De que bancos extrae un examen (solo su docente)",
    responses=AUTH_RESPONSES,
)
def list_session_banks(
    session_id: UUID, use_case: ListSessionBanksDep, current_user: CurrentUserDep
) -> list[QuestionBankResponse]:
    bancos = use_case.execute(session_id, actor=current_user)
    return [QuestionBankResponse.from_entity(b) for b in bancos]


@router.post(
    "/sessions/{session_id}/banks",
    response_model=AttachBankResponse,
    summary="Atar un banco a un examen (solo su docente)",
    responses=AUTH_RESPONSES,
)
def attach_bank(
    session_id: UUID,
    payload: AttachBankRequest,
    use_case: AttachBankDep,
    current_user: CurrentUserDep,
) -> AttachBankResponse:
    """A partir de aqui el examen extrae de ese banco.

    Hace falta ser dueno **del examen y del banco**: sin lo segundo, un docente
    podria atar el banco de otro al suyo y leerlo entero por la puerta de atras.

    Idempotente: atar dos veces devuelve `already_attached: true`.
    """
    nuevo = use_case.execute(session_id, payload.bank_id, actor=current_user)
    return AttachBankResponse(bank_id=payload.bank_id, already_attached=not nuevo)


@router.delete(
    "/sessions/{session_id}/banks/{bank_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitar un banco de un examen (solo su docente)",
    responses=AUTH_RESPONSES,
)
def detach_bank(
    session_id: UUID, bank_id: UUID, use_case: DetachBankDep, current_user: CurrentUserDep
) -> Response:
    """Quita el banco del examen. **Las preguntas del banco no se tocan.**"""
    use_case.execute(session_id, bank_id, actor=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
