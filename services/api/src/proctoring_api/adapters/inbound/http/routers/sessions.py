"""Endpoints de sesiones de examen."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Response, status

from proctoring_api.adapters.inbound.http.dependencies import (
    CancelExamSessionDep,
    ClockDep,
    CreateExamSessionDep,
    CurrentUserDep,
    DeleteExamSessionDep,
    GetExamSessionDep,
    JoinExamSessionDep,
    ListTeacherSessionsDep,
    UpdateExamSessionDep,
)
from proctoring_api.adapters.inbound.http.schemas import (
    ErrorResponse,
    ExamSessionRequest,
    ExamSessionResponse,
    ExamSessionSummary,
    JoinExamRequest,
    JoinExamResponse,
    UpdateExamSessionRequest,
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
    clock: ClockDep,
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
            question_pool_size=payload.question_pool_size,
            shuffle_options=payload.shuffle_options,
            allow_back_navigation=payload.allow_back_navigation,
            reveal_code_at_start=payload.reveal_code_at_start,
            max_score=payload.max_score,
            modules=payload.modules or {},
        ),
        actor=current_user,
    )
    return ExamSessionResponse.from_entity(session, clock.now())


@router.get(
    "",
    response_model=list[ExamSessionSummary],
    summary="Mis sesiones de examen",
    responses=AUTH_RESPONSES,
)
def list_my_sessions(
    use_case: ListTeacherSessionsDep,
    current_user: CurrentUserDep,
    clock: ClockDep,
) -> list[ExamSessionSummary]:
    """Sesiones del docente que pregunta, de la mas proxima a la mas antigua.

    El id del docente sale del token, no de un parametro: asi no hay forma de
    pedir las de otro.
    """
    return [
        ExamSessionSummary.from_entity(session, clock.now())
        for session in use_case.execute(actor=current_user)
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
    clock: ClockDep,
) -> ExamSessionResponse:
    """Sesion con sus modulos y umbrales.

    Una sesion ajena y una inexistente responden lo mismo (403), para no
    permitir averiguar que sesiones existen.
    """
    return ExamSessionResponse.from_entity(
        use_case.execute(session_id, actor=current_user), clock.now()
    )


@router.post(
    "/join",
    response_model=JoinExamResponse,
    summary="Entrar a un examen con el codigo de acceso",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "El codigo no corresponde a ningun examen"},
    },
)
def join_exam_session(
    payload: JoinExamRequest,
    use_case: JoinExamSessionDep,
    current_user: CurrentUserDep,
) -> JoinExamResponse:
    """Resuelve el codigo que el docente le dio al estudiante.

    Un codigo mal escrito y uno de otro docente responden lo mismo: distinguirlos
    permitiria tantear codigos hasta dar con uno valido.

    **No matricula todavia.** Crear la fila en session_participants, el
    consentimiento y la verificacion de identidad son SPEC-004.
    """
    resultado = use_case.execute(payload.access_code, actor=current_user)
    sesion = resultado.session
    return JoinExamResponse(
        session_id=sesion.id,
        title=sesion.title,
        description=sesion.description,
        starts_at=sesion.starts_at,
        ends_at=resultado.closes_at,
        duration_minutes=sesion.duration_minutes,
        entry_tolerance_minutes=sesion.entry_tolerance_minutes,
        can_enter_now=resultado.can_enter_now,
        modules=sesion.modules,
    )


@router.patch(
    "/{session_id}",
    response_model=ExamSessionResponse,
    summary="Corregir un examen (solo su docente)",
    responses={
        **AUTH_RESPONSES,
        400: {
            "model": ErrorResponse,
            "description": "Viola una regla, o se cambia la escala con estudiantes dentro",
        },
    },
)
def update_exam_session(
    session_id: UUID,
    payload: UpdateExamSessionRequest,
    use_case: UpdateExamSessionDep,
    current_user: CurrentUserDep,
    clock: ClockDep,
) -> ExamSessionResponse:
    """Cambia lo que el docente se equivocó al crear.

    Solo lo que se envía. Lo que no se toca se queda como estaba; para **vaciar**
    un campo opcional están los `clear_*`.

    Con estudiantes ya dentro, el título, la descripción, la hora y la duración
    se siguen pudiendo cambiar, pero la nota máxima y cómo se sortean las
    preguntas no: moverlas a mitad de un examen dejaría a unos calificados con
    una regla y a otros con otra.
    """
    corregida = use_case.execute(session_id, payload.to_changes(), actor=current_user)
    return ExamSessionResponse.from_entity(corregida, clock.now())


@router.post(
    "/{session_id}/cancel",
    response_model=ExamSessionResponse,
    summary="Cancelar un examen (solo su docente)",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "Ya estaba cancelado"},
    },
)
def cancel_exam_session(
    session_id: UUID,
    use_case: CancelExamSessionDep,
    current_user: CurrentUserDep,
    clock: ClockDep,
) -> ExamSessionResponse:
    """Retira el examen sin borrar nada.

    Su código de acceso deja de servir, pero el estudiante que lo use recibe
    "tu docente canceló este examen" en vez de un error cualquiera. Los eventos,
    las alertas y las respuestas de quien ya entró siguen ahí: son evidencia.
    """
    cancelada = use_case.execute(session_id, actor=current_user)
    return ExamSessionResponse.from_entity(cancelada, clock.now())


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar un examen sin estudiantes (solo su docente)",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "El examen ya tiene estudiantes"},
    },
)
def delete_exam_session(
    session_id: UUID,
    use_case: DeleteExamSessionDep,
    current_user: CurrentUserDep,
) -> Response:
    """Borra el examen de verdad, y **solo si nadie entró**.

    Es el caso del docente que acaba de crear un examen con la fecha mal y quiere
    que desaparezca. En cuanto hay un participante hay evidencia, y entonces lo
    que corresponde es cancelarlo.
    """
    use_case.execute(session_id, actor=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
