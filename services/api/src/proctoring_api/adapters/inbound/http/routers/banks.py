"""Endpoints de bancos de preguntas."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status

from proctoring_api.adapters.inbound.http.dependencies import (
    AddQuestionsToBankDep,
    AttachBankDep,
    CreateBankDep,
    CurrentUserDep,
    DetachBankDep,
    ImportQtiDep,
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
    QtiImportResponse,
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


#: Tope del archivo subido. El importador aplica el mismo limite, pero aqui se
#: mira el `Content-Length` **antes** de leer el cuerpo: con solo la comprobacion
#: de dentro, un archivo de 500 MB se cargaria entero en memoria para despues
#: rechazarlo.
MAX_QTI_BYTES = 1_000_000


@router.post(
    "/question-banks/{bank_id}/import/qti",
    status_code=status.HTTP_201_CREATED,
    response_model=QtiImportResponse,
    summary="Importar un archivo QTI 2.1 a un banco (solo su docente)",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "El archivo no es QTI 2.1 legible"},
        413: {"model": ErrorResponse, "description": "El archivo pasa de 1 MB"},
    },
)
async def import_qti(
    bank_id: UUID,
    request: Request,
    use_case: ImportQtiDep,
    current_user: CurrentUserDep,
    dry_run: bool = False,
) -> QtiImportResponse:
    """Sube el XML que exporto tu plataforma y sus preguntas caen en el banco.

    El cuerpo de la peticion **es** el archivo (`Content-Type: application/xml`).
    No va en un formulario: es un unico documento y asi no hace falta analizar
    multipart para nada.

    Con `?dry_run=true` no se guarda nada y se devuelve lo que entraria. Sirve
    para mirar el resultado antes de meter cuarenta preguntas en el banco.

    La respuesta trae **tres** listas: lo importado, lo que se quedo fuera y de
    que hay que avisar. Un item que no se entiende no aborta el lote; vuelve en
    `skipped` con su motivo. Pero si una pregunta viola una regla del dominio no
    se guarda **ninguna**: importar cuarenta no puede dejar veintinueve a medias.
    """
    declarado = request.headers.get("content-length")
    if declarado is not None and declarado.isdigit() and int(declarado) > MAX_QTI_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"El archivo pasa del limite de {MAX_QTI_BYTES // 1000} KB",
        )

    xml = await request.body()
    if len(xml) > MAX_QTI_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"El archivo pasa del limite de {MAX_QTI_BYTES // 1000} KB",
        )

    resultado = use_case.execute(bank_id, xml, actor=current_user, dry_run=dry_run)
    return QtiImportResponse.from_result(resultado, dry_run=dry_run)
