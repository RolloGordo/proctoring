"""Endpoint de subida de evidencia."""

from __future__ import annotations

from fastapi import APIRouter, status

from proctoring_api.adapters.inbound.http.dependencies import (
    CreateEvidenceUploadUrlDep,
    CurrentUserDep,
)
from proctoring_api.adapters.inbound.http.schemas import (
    ErrorResponse,
    EvidenceUploadRequestBody,
    EvidenceUploadResponse,
)
from proctoring_api.application.use_cases.create_evidence_upload_url import (
    EvidenceUploadRequest,
)

router = APIRouter(prefix="/api/v1", tags=["evidence"])


@router.post(
    "/evidence/upload-url",
    status_code=status.HTTP_201_CREATED,
    response_model=EvidenceUploadResponse,
    summary="Pedir una URL firmada para subir evidencia",
    responses={
        400: {"model": ErrorResponse, "description": "Extension no permitida"},
        401: {"model": ErrorResponse, "description": "Token ausente o invalido"},
        403: {"model": ErrorResponse, "description": "No puedes subir por otro estudiante"},
    },
)
def create_evidence_upload_url(
    payload: EvidenceUploadRequestBody,
    use_case: CreateEvidenceUploadUrlDep,
    current_user: CurrentUserDep,
) -> EvidenceUploadResponse:
    """Devuelve permiso temporal para subir **un** archivo a **una** ruta.

    El flujo para el cliente es:

    1. pedir esta URL;
    2. subir el archivo **directo a Storage** (la API nunca lo recibe);
    3. mandar el evento con el `path` devuelto en `evidence_path`.

    El paso 2 es el que mantiene el proyecto dentro del presupuesto: si las
    capturas y el audio pasaran por la API, cada examen costaria ancho de banda
    del plan gratuito de Render. Ver ADR-0004.
    """
    upload = use_case.execute(
        EvidenceUploadRequest(
            session_id=payload.session_id,
            student_id=payload.student_id,
            kind=payload.kind,
            extension=payload.extension,
        ),
        actor=current_user,
    )
    return EvidenceUploadResponse(
        path=upload.path,
        url=upload.url,
        token=upload.token,
        expires_in_seconds=upload.expires_in_seconds,
    )
