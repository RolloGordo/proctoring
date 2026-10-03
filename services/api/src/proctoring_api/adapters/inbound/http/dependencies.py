"""Inyeccion de dependencias para los routers.

Los casos de uso se arman una sola vez en `main.create_app()` y se guardan en
`app.state`. Los routers los piden con `Depends`, asi que nunca construyen un
adaptador ni saben cual esta configurado: eso es lo que permite cambiar memoria
por Supabase con una variable de entorno.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from proctoring_api.application.use_cases.create_evidence_upload_url import (
    CreateEvidenceUploadUrl,
)
from proctoring_api.application.use_cases.create_exam_session import CreateExamSession
from proctoring_api.application.use_cases.identify_user import IdentifyUser
from proctoring_api.application.use_cases.join_exam_session import JoinExamSession
from proctoring_api.application.use_cases.list_session_alerts import ListSessionAlerts
from proctoring_api.application.use_cases.list_session_events import ListSessionEvents
from proctoring_api.application.use_cases.list_teacher_sessions import (
    GetExamSession,
    ListTeacherSessions,
)
from proctoring_api.application.use_cases.register_event import RegisterEvent
from proctoring_api.config import Settings
from proctoring_api.domain.errors import AuthenticationError
from proctoring_api.domain.user import AuthenticatedUser

#: auto_error=False para poder dar un mensaje propio cuando falta el token, en vez
#: del 403 escueto que devuelve FastAPI por defecto.
_bearer_scheme = HTTPBearer(auto_error=False, description="Token de Supabase Auth")


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_register_event(request: Request) -> RegisterEvent:
    use_case: RegisterEvent = request.app.state.register_event
    return use_case


def get_list_session_events(request: Request) -> ListSessionEvents:
    use_case: ListSessionEvents = request.app.state.list_session_events
    return use_case


def get_list_session_alerts(request: Request) -> ListSessionAlerts:
    use_case: ListSessionAlerts = request.app.state.list_session_alerts
    return use_case


def get_create_evidence_upload_url(request: Request) -> CreateEvidenceUploadUrl:
    use_case: CreateEvidenceUploadUrl = request.app.state.create_evidence_upload_url
    return use_case


def get_create_exam_session(request: Request) -> CreateExamSession:
    use_case: CreateExamSession = request.app.state.create_exam_session
    return use_case


def get_list_teacher_sessions(request: Request) -> ListTeacherSessions:
    use_case: ListTeacherSessions = request.app.state.list_teacher_sessions
    return use_case


def get_exam_session(request: Request) -> GetExamSession:
    use_case: GetExamSession = request.app.state.get_exam_session
    return use_case


def get_join_exam_session(request: Request) -> JoinExamSession:
    use_case: JoinExamSession = request.app.state.join_exam_session
    return use_case


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> AuthenticatedUser | None:
    """Identifica a quien hace la peticion a partir del `Authorization: Bearer`.

    Devuelve `None` **solo** cuando la autenticacion esta desactivada, que la
    configuracion unicamente permite con `ENV=local`. Los casos de uso entienden
    ese `None` como "no comprobar permisos".

    Raises:
        AuthenticationError: si falta el token o no es valido.
    """
    identify_user: IdentifyUser | None = request.app.state.identify_user

    if identify_user is None:
        return None

    if credentials is None or not credentials.credentials:
        raise AuthenticationError(
            "Falta el token. Envia la cabecera 'Authorization: Bearer <token>' "
            "con el token de Supabase Auth."
        )

    return identify_user.execute(credentials.credentials)


SettingsDep = Annotated[Settings, Depends(get_settings)]
RegisterEventDep = Annotated[RegisterEvent, Depends(get_register_event)]
ListSessionEventsDep = Annotated[ListSessionEvents, Depends(get_list_session_events)]
ListSessionAlertsDep = Annotated[ListSessionAlerts, Depends(get_list_session_alerts)]
CurrentUserDep = Annotated[AuthenticatedUser | None, Depends(get_current_user)]
CreateExamSessionDep = Annotated[CreateExamSession, Depends(get_create_exam_session)]
ListTeacherSessionsDep = Annotated[ListTeacherSessions, Depends(get_list_teacher_sessions)]
GetExamSessionDep = Annotated[GetExamSession, Depends(get_exam_session)]
JoinExamSessionDep = Annotated[JoinExamSession, Depends(get_join_exam_session)]
CreateEvidenceUploadUrlDep = Annotated[
    CreateEvidenceUploadUrl, Depends(get_create_evidence_upload_url)
]
