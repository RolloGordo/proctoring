"""Endpoints de identidad y del servicio de IA.

Dos públicos, que usa el estudiante, y cuatro **internos**, que usa el worker de
`services/ai` con el secreto compartido (ver `internal_auth.py`).

El reparto importa: el worker **mide** y la API **decide**. La regla que define
el proyecto —alertar solo si lo dicho se parece al enunciado **y** hay una
segunda voz sintética— se aplica aquí, con los umbrales de la sesión.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from proctoring_api.adapters.inbound.http.dependencies import (
    CurrentUserDep,
    GetAudioJobDep,
    GetFaceJobDep,
    RecordAudioAnalysisDep,
    RecordIdentityCheckDep,
    RegisterReferenceFaceDep,
    RequestIdentityCheckDep,
)
from proctoring_api.adapters.inbound.http.internal_auth import verify_internal_token
from proctoring_api.adapters.inbound.http.schemas import (
    AudioAnalysisResponse,
    AudioJobResponse,
    AudioMeasurementRequest,
    ErrorResponse,
    FaceJobResponse,
    FaceMeasurementRequest,
    IdentityCheckResponse,
    ParticipantResponse,
    RegisterReferenceFaceRequest,
    RequestIdentityCheckRequest,
)
from proctoring_api.application.use_cases.ai_jobs import AudioMeasurement, FaceMeasurement

router = APIRouter(prefix="/api/v1", tags=["identity"])

#: Los internos van en su propio router: todos exigen el secreto compartido, y
#: declararlo una vez evita que una ruta nueva se quede sin él por olvido.
internal = APIRouter(
    prefix="/api/v1/internal",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
    responses={401: {"model": ErrorResponse, "description": "Token interno ausente o invalido"}},
)

AUTH_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse, "description": "Token ausente o invalido"},
    403: {"model": ErrorResponse, "description": "No puedes hacer esto"},
}


# --------------------------------------------------------------- estudiante


@router.post(
    "/me/reference-face",
    status_code=status.HTTP_201_CREATED,
    summary="Registrar mi rostro de referencia",
    responses=AUTH_RESPONSES,
)
def register_reference_face(
    payload: RegisterReferenceFaceRequest,
    use_case: RegisterReferenceFaceDep,
    current_user: CurrentUserDep,
) -> dict[str, str]:
    """Guarda la **ruta** de la foto de referencia, no la foto.

    La imagen se sube antes directo a Storage con una URL firmada
    (`POST /api/v1/evidence/upload-url` con `kind=reference_face`). Registrarla
    otra vez reemplaza la anterior.
    """
    face = use_case.execute(payload.storage_path, actor=current_user)
    return {"storage_path": face.storage_path}


@router.post(
    "/exam/{session_id}/identity/check",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ParticipantResponse,
    summary="Pedir la verificacion de identidad",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "Falta el rostro de referencia"},
    },
)
def request_identity_check(
    session_id: UUID,
    payload: RequestIdentityCheckRequest,
    use_case: RequestIdentityCheckDep,
    current_user: CurrentUserDep,
) -> ParticipantResponse:
    """Encola la comparacion y responde en seguida.

    202 y no 200 a proposito: la verificacion **todavia no ocurrio**. El
    resultado llega despues, y la sala de espera lo recoge sola.
    """
    return ParticipantResponse.from_entity(
        use_case.execute(session_id, payload.capture_path, actor=current_user)
    )


# ----------------------------------------------------------------- internos


@internal.get(
    "/audio-jobs/{event_id}",
    response_model=AudioJobResponse,
    summary="[IA] Que analizar de un evento de habla",
    responses={400: {"model": ErrorResponse, "description": "No hay trabajo que hacer"}},
)
def get_audio_job(event_id: UUID, use_case: GetAudioJobDep) -> AudioJobResponse:
    """Todo lo que el worker necesita, servido de una vez.

    Incluye el **enunciado** de la pregunta en curso, que es con lo que hay que
    comparar la transcripcion, y la ruta del audio en Storage. El worker no
    consulta la base: si lo hiciera, habria dos sitios que mantener.
    """
    return AudioJobResponse.from_entity(use_case.execute(event_id))


@internal.post(
    "/audio-jobs/{event_id}/result",
    response_model=AudioAnalysisResponse,
    summary="[IA] Entregar lo medido del audio",
    responses={400: {"model": ErrorResponse, "description": "Medida fuera de rango"}},
)
def record_audio_analysis(
    event_id: UUID, payload: AudioMeasurementRequest, use_case: RecordAudioAnalysisDep
) -> AudioAnalysisResponse:
    """Guarda lo medido y **la API decide** si el docente debe enterarse.

    El worker nunca crea la alerta. La regla de las dos condiciones —similitud
    con el enunciado **y** voz sintetica— se aplica aqui, con los umbrales de la
    sesion, y la respuesta dice en `alerted` que se decidio.
    """
    resultado = use_case.execute(
        event_id,
        AudioMeasurement(
            transcript=payload.transcript,
            similarity=payload.similarity,
            synthetic_voice_score=payload.synthetic_voice_score,
            processing_ms=payload.processing_ms,
            model_versions=payload.model_versions,
        ),
    )
    return AudioAnalysisResponse.from_entity(resultado.analysis, resultado.alerted)


@internal.get(
    "/face-jobs/{participant_id}",
    response_model=FaceJobResponse,
    summary="[IA] Que caras comparar",
    responses={400: {"model": ErrorResponse, "description": "No hay trabajo que hacer"}},
)
def get_face_job(
    participant_id: UUID, capture_path: str, use_case: GetFaceJobDep
) -> FaceJobResponse:
    """Las dos rutas a comparar y el umbral de la sesion.

    `capture_path` viaja por la cola junto al `participant_id`, asi que llega
    como parametro de consulta.
    """
    return FaceJobResponse.from_entity(use_case.execute(participant_id, capture_path))


@internal.post(
    "/sessions/{session_id}/students/{student_id}/identity-result",
    response_model=IdentityCheckResponse,
    summary="[IA] Entregar el resultado de la verificacion facial",
    responses={400: {"model": ErrorResponse, "description": "Medida fuera de rango"}},
)
def record_identity_result(
    session_id: UUID,
    student_id: UUID,
    payload: FaceMeasurementRequest,
    use_case: RecordIdentityCheckDep,
) -> IdentityCheckResponse:
    """Aplica el umbral de la sesion y deja el resultado como evidencia.

    Un fallo **no expulsa a nadie**: el estudiante queda esperando y el docente
    lo admite a mano. Un reconocimiento que falla con mala luz no puede costarle
    el examen a nadie.
    """
    resultado = use_case.execute(
        session_id,
        student_id,
        FaceMeasurement(
            similarity=payload.similarity,
            inconclusive=payload.inconclusive,
            latency_ms=payload.latency_ms,
            model_version=payload.model_version,
            reference_embedding=payload.reference_embedding,
        ),
    )
    return IdentityCheckResponse.from_entity(resultado.check, resultado.participant)
