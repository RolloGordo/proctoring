"""Endpoints de cursos."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Response, status

from proctoring_api.adapters.inbound.http.dependencies import (
    CreateCourseDep,
    CurrentUserDep,
    DeleteCourseDep,
    EnrollStudentDep,
    GetCourseDep,
    ListCourseMembersDep,
    ListMyCoursesDep,
    ListTeacherCoursesDep,
    RequestCourseCoverUploadDep,
    SetCourseCoverDep,
)
from proctoring_api.adapters.inbound.http.schemas import (
    CourseCoverUploadRequest,
    CourseMemberResponse,
    CourseResponse,
    CreateCourseRequest,
    EnrollStudentRequest,
    EnrollStudentResponse,
    ErrorResponse,
    EvidenceUploadResponse,
    MyCourseResponse,
    SetCourseCoverRequest,
)
from proctoring_api.application.use_cases.manage_courses import TeacherCourse

router = APIRouter(prefix="/api/v1", tags=["courses"])

AUTH_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse, "description": "Token ausente o invalido"},
    403: {"model": ErrorResponse, "description": "No puedes hacer esto"},
}


@router.post(
    "/courses",
    status_code=status.HTTP_201_CREATED,
    response_model=CourseResponse,
    summary="Crear un curso (solo docente)",
    responses=AUTH_RESPONSES,
)
def create_course(
    payload: CreateCourseRequest, use_case: CreateCourseDep, current_user: CurrentUserDep
) -> CourseResponse:
    """Crea un curso del docente que lo pide."""
    course = use_case.execute(payload.name, payload.section, actor=current_user)
    return CourseResponse.from_entity(TeacherCourse(course=course, student_count=0))


@router.get(
    "/courses",
    response_model=list[CourseResponse],
    summary="Mis cursos (solo docente)",
    responses=AUTH_RESPONSES,
)
def list_courses(
    use_case: ListTeacherCoursesDep, current_user: CurrentUserDep
) -> list[CourseResponse]:
    """Los cursos del docente, con cuantos estudiantes tiene cada uno.

    El docente sale del token: no hay parametro con el que pedir los de otro.
    """
    return [CourseResponse.from_entity(c) for c in use_case.execute(actor=current_user)]


@router.get(
    "/courses/{course_id}",
    response_model=CourseResponse,
    summary="Un curso (solo su docente)",
    responses=AUTH_RESPONSES,
)
def get_course(
    course_id: UUID, use_case: GetCourseDep, current_user: CurrentUserDep
) -> CourseResponse:
    """Un curso inexistente y uno ajeno responden lo mismo."""
    return CourseResponse.from_entity(use_case.execute(course_id, actor=current_user))


@router.delete(
    "/courses/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un curso vacío (solo su docente)",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "El curso tiene contenido asociado"},
    },
)
def delete_course(
    course_id: UUID, use_case: DeleteCourseDep, current_user: CurrentUserDep
) -> Response:
    """Elimina un curso sin matrículas, exámenes ni bancos asociados."""
    use_case.execute(course_id, actor=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/courses/{course_id}/cover/upload-url",
    response_model=EvidenceUploadResponse,
    summary="URL firmada para subir la portada de un curso (solo su docente)",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "Formato de imagen no admitido"},
    },
)
def request_cover_upload(
    course_id: UUID,
    payload: CourseCoverUploadRequest,
    use_case: RequestCourseCoverUploadDep,
    current_user: CurrentUserDep,
) -> EvidenceUploadResponse:
    """Permiso para subir **una** imagen a **una** ruta nueva del bucket de portadas.

    La imagen va directo a Storage; después se fija con `PUT .../cover`.
    """
    firma = use_case.execute(course_id, payload.content_type, actor=current_user)
    return EvidenceUploadResponse(
        path=firma.path,
        url=firma.url,
        token=firma.token,
        expires_in_seconds=firma.expires_in_seconds,
    )


@router.put(
    "/courses/{course_id}/cover",
    response_model=CourseResponse,
    summary="Fijar la portada de un curso (solo su docente)",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "La ruta no es una portada de este curso"},
    },
)
def set_cover(
    course_id: UUID,
    payload: SetCourseCoverRequest,
    use_case: SetCourseCoverDep,
    current_user: CurrentUserDep,
) -> CourseResponse:
    """Fija como portada la imagen ya subida. La anterior se borra del bucket."""
    return CourseResponse.from_entity(use_case.execute(course_id, payload.path, actor=current_user))


@router.delete(
    "/courses/{course_id}/cover",
    response_model=CourseResponse,
    summary="Quitar la portada de un curso (solo su docente)",
    responses=AUTH_RESPONSES,
)
def remove_cover(
    course_id: UUID, use_case: SetCourseCoverDep, current_user: CurrentUserDep
) -> CourseResponse:
    """Vuelve a la portada de reserva y borra la imagen del bucket."""
    return CourseResponse.from_entity(use_case.execute(course_id, None, actor=current_user))


@router.get(
    "/courses/{course_id}/students",
    response_model=list[CourseMemberResponse],
    summary="Estudiantes de un curso (solo su docente)",
    responses=AUTH_RESPONSES,
)
def list_students(
    course_id: UUID, use_case: ListCourseMembersDep, current_user: CurrentUserDep
) -> list[CourseMemberResponse]:
    return [
        CourseMemberResponse.from_entity(m) for m in use_case.execute(course_id, actor=current_user)
    ]


@router.post(
    "/courses/{course_id}/students",
    response_model=EnrollStudentResponse,
    summary="Matricular a un estudiante por su correo (solo su docente)",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "No hay un estudiante con ese correo"},
    },
)
def enroll_student(
    course_id: UUID,
    payload: EnrollStudentRequest,
    use_case: EnrollStudentDep,
    current_user: CurrentUserDep,
) -> EnrollStudentResponse:
    """Matricula a quien tenga ese correo, si es estudiante.

    Es idempotente: matricular dos veces a la misma persona devuelve
    `already_enrolled: true` en vez de un error.

    Un correo inexistente y uno de un docente responden **lo mismo**: distinguirlos
    le diria a cualquier docente quien tiene cuenta y con que rol.
    """
    resultado = use_case.execute(course_id, payload.email, actor=current_user)
    return EnrollStudentResponse(
        student=CourseMemberResponse.from_entity(resultado.member),
        already_enrolled=resultado.already_enrolled,
    )


@router.get(
    "/me/courses",
    response_model=list[MyCourseResponse],
    summary="Mis clases (estudiante)",
    responses=AUTH_RESPONSES,
)
def my_courses(use_case: ListMyCoursesDep, current_user: CurrentUserDep) -> list[MyCourseResponse]:
    """Las clases del estudiante y los examenes que vienen en cada una.

    Estar en una clase **no da acceso a sus examenes**: para rendir uno hace falta
    el codigo de acceso. Aqui solo se ve cuando es.
    """
    return [MyCourseResponse.from_entity(c) for c in use_case.execute(actor=current_user)]
