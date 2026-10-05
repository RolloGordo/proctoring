"""Endpoints de matrícula, consentimiento y entrega."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from proctoring_api.adapters.inbound.http.dependencies import (
    CurrentUserDep,
    EnrollInExamDep,
    ListMyExamsDep,
    ListParticipantsDep,
    ReviewIdentityDep,
    SubmitExamDep,
)
from proctoring_api.adapters.inbound.http.schemas import (
    EnrollRequest,
    ErrorResponse,
    MyExamResponse,
    ParticipantResponse,
    ReviewIdentityRequest,
)

router = APIRouter(prefix="/api/v1", tags=["enrollment"])

AUTH_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse, "description": "Token ausente o invalido"},
    403: {"model": ErrorResponse, "description": "No puedes hacer esto"},
}


@router.post(
    "/exam/{session_id}/enroll",
    status_code=status.HTTP_201_CREATED,
    response_model=ParticipantResponse,
    summary="Aceptar la supervision y entrar al examen",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "Falta el consentimiento"},
    },
)
def enroll_in_exam(
    session_id: UUID,
    payload: EnrollRequest,
    use_case: EnrollInExamDep,
    current_user: CurrentUserDep,
) -> ParticipantResponse:
    """Matricula al estudiante que acepta ser supervisado.

    Es el momento del **consentimiento**: a partir de aqui el sistema observa
    camara, microfono, pantalla y procesos. Por eso `accepts_supervision` no
    tiene valor por defecto y sin el responde 400.

    Si ya estaba matriculado, devuelve su estado sin pedir nada otra vez.
    """
    resultado = use_case.execute(
        session_id, accepts_supervision=payload.accepts_supervision, actor=current_user
    )
    return ParticipantResponse.from_entity(resultado.participant)


@router.get(
    "/exam/{session_id}/me",
    response_model=ParticipantResponse,
    summary="Mi estado en este examen",
    responses=AUTH_RESPONSES,
)
def my_enrollment(
    session_id: UUID,
    use_case: EnrollInExamDep,
    current_user: CurrentUserDep,
) -> ParticipantResponse:
    """Estado del estudiante: si consintio, si esta verificado y si ya entrego.

    Lo usa la sala de espera para saber que mostrar. No matricula: si no existe
    la matricula, `accepts_supervision=False` hace que responda 400 pidiendo el
    consentimiento, que es la respuesta correcta.
    """
    resultado = use_case.execute(session_id, accepts_supervision=False, actor=current_user)
    return ParticipantResponse.from_entity(resultado.participant)


@router.post(
    "/exam/{session_id}/submit",
    response_model=ParticipantResponse,
    summary="Entregar el examen",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "Ya habias entregado"},
    },
)
def submit_exam(
    session_id: UUID,
    use_case: SubmitExamDep,
    current_user: CurrentUserDep,
) -> ParticipantResponse:
    """Marca la entrega.

    Reenviar responde 400: sobrescribir la hora de entrega destruiria evidencia.
    """
    return ParticipantResponse.from_entity(use_case.execute(session_id, actor=current_user))


@router.get(
    "/sessions/{session_id}/participants",
    response_model=list[ParticipantResponse],
    summary="Sala de espera (solo docente)",
    responses=AUTH_RESPONSES,
)
def list_participants(
    session_id: UUID,
    use_case: ListParticipantsDep,
    current_user: CurrentUserDep,
) -> list[ParticipantResponse]:
    """Quien llego al examen y en que estado esta.

    Un estudiante no ve quien mas esta rindiendo.
    """
    return [
        ParticipantResponse.from_entry(entrada)
        for entrada in use_case.execute(session_id, actor=current_user)
    ]


@router.post(
    "/sessions/{session_id}/participants/{student_id}/identity",
    response_model=ParticipantResponse,
    summary="Admitir o rechazar a mano tras la verificacion facial (solo docente)",
    responses=AUTH_RESPONSES,
)
def review_identity(
    session_id: UUID,
    student_id: UUID,
    payload: ReviewIdentityRequest,
    use_case: ReviewIdentityDep,
    current_user: CurrentUserDep,
) -> ParticipantResponse:
    """El docente resuelve una verificacion que no paso.

    Existe porque un reconocimiento facial que falla con mala luz no puede
    costarle el examen a nadie. Queda registrado quien lo decidio.
    """
    return ParticipantResponse.from_entity(
        use_case.execute(session_id, student_id, approve=payload.approve, actor=current_user)
    )


@router.get(
    "/me/exams",
    response_model=list[MyExamResponse],
    summary="Mis examenes (panel del estudiante)",
    responses=AUTH_RESPONSES,
)
def my_exams(
    use_case: ListMyExamsDep,
    current_user: CurrentUserDep,
) -> list[MyExamResponse]:
    """A que examenes entro el estudiante y en que estado esta cada uno.

    Es la base de su panel: lo que viene, lo que esta en curso y lo ya entregado.
    El estudiante sale del token; no hay parametro con el que pedir los de otro.
    """
    return [MyExamResponse.from_entity(examen) for examen in use_case.execute(actor=current_user)]
