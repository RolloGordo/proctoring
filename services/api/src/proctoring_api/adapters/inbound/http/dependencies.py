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

from proctoring_api.application.use_cases.ai_jobs import (
    GetAudioJob,
    GetFaceJob,
    RecordAudioAnalysis,
    RecordIdentityCheck,
    RegisterReferenceFace,
    RequestIdentityCheck,
)
from proctoring_api.application.use_cases.create_evidence_upload_url import (
    CreateEvidenceUploadUrl,
)
from proctoring_api.application.use_cases.create_exam_session import CreateExamSession
from proctoring_api.application.use_cases.edit_exam_session import (
    CancelExamSession,
    DeleteExamSession,
    UpdateExamSession,
)
from proctoring_api.application.use_cases.edit_questions import (
    DeleteQuestion,
    UpdateQuestion,
)
from proctoring_api.application.use_cases.identify_user import IdentifyUser
from proctoring_api.application.use_cases.join_exam_session import JoinExamSession
from proctoring_api.application.use_cases.list_my_exams import ListMyExams
from proctoring_api.application.use_cases.list_session_alerts import ListSessionAlerts
from proctoring_api.application.use_cases.list_session_events import ListSessionEvents
from proctoring_api.application.use_cases.list_teacher_sessions import (
    GetExamSession,
    ListTeacherSessions,
)
from proctoring_api.application.use_cases.manage_answers import ListMyAnswers, SaveAnswers
from proctoring_api.application.use_cases.manage_banks import (
    AddQuestionsToBank,
    AttachBankToSession,
    CreateQuestionBank,
    DetachBankFromSession,
    ListBankQuestions,
    ListQuestionBanks,
    ListSessionBanks,
)
from proctoring_api.application.use_cases.manage_courses import (
    CreateCourse,
    EnrollStudentInCourse,
    GetCourse,
    ListCourseMembers,
    ListMyCourses,
    ListTeacherCourses,
)
from proctoring_api.application.use_cases.manage_enrollment import (
    EnrollInExam,
    ListSessionParticipantsWithNames,
    ReviewParticipantIdentity,
    SubmitExam,
)
from proctoring_api.application.use_cases.manage_questions import (
    AddQuestions,
    GetExamQuestions,
    ListSessionQuestions,
)
from proctoring_api.application.use_cases.register_event import RegisterEvent
from proctoring_api.application.use_cases.review_case import (
    ListSessionDecisions,
    RecordDecision,
    ReviewStudentCase,
)
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


def get_add_questions(request: Request) -> AddQuestions:
    use_case: AddQuestions = request.app.state.add_questions
    return use_case


def get_list_session_questions(request: Request) -> ListSessionQuestions:
    use_case: ListSessionQuestions = request.app.state.list_session_questions
    return use_case


def get_exam_questions(request: Request) -> GetExamQuestions:
    use_case: GetExamQuestions = request.app.state.get_exam_questions
    return use_case


def get_enroll_in_exam(request: Request) -> EnrollInExam:
    use_case: EnrollInExam = request.app.state.enroll_in_exam
    return use_case


def get_list_participants(request: Request) -> ListSessionParticipantsWithNames:
    use_case: ListSessionParticipantsWithNames = request.app.state.list_participants
    return use_case


def get_review_identity(request: Request) -> ReviewParticipantIdentity:
    use_case: ReviewParticipantIdentity = request.app.state.review_identity
    return use_case


def get_submit_exam(request: Request) -> SubmitExam:
    use_case: SubmitExam = request.app.state.submit_exam
    return use_case


def get_save_answers(request: Request) -> SaveAnswers:
    use_case: SaveAnswers = request.app.state.save_answers
    return use_case


def get_list_my_answers(request: Request) -> ListMyAnswers:
    use_case: ListMyAnswers = request.app.state.list_my_answers
    return use_case


def get_list_my_exams(request: Request) -> ListMyExams:
    use_case: ListMyExams = request.app.state.list_my_exams
    return use_case


def get_create_course(request: Request) -> CreateCourse:
    use_case: CreateCourse = request.app.state.create_course
    return use_case


def get_list_teacher_courses(request: Request) -> ListTeacherCourses:
    use_case: ListTeacherCourses = request.app.state.list_teacher_courses
    return use_case


def get_get_course(request: Request) -> GetCourse:
    use_case: GetCourse = request.app.state.get_course
    return use_case


def get_enroll_student(request: Request) -> EnrollStudentInCourse:
    use_case: EnrollStudentInCourse = request.app.state.enroll_student
    return use_case


def get_list_course_members(request: Request) -> ListCourseMembers:
    use_case: ListCourseMembers = request.app.state.list_course_members
    return use_case


def get_list_my_courses(request: Request) -> ListMyCourses:
    use_case: ListMyCourses = request.app.state.list_my_courses
    return use_case


def get_review_case(request: Request) -> ReviewStudentCase:
    use_case: ReviewStudentCase = request.app.state.review_case
    return use_case


def get_record_decision(request: Request) -> RecordDecision:
    use_case: RecordDecision = request.app.state.record_decision
    return use_case


def get_list_decisions(request: Request) -> ListSessionDecisions:
    use_case: ListSessionDecisions = request.app.state.list_decisions
    return use_case


def get_audio_job(request: Request) -> GetAudioJob:
    use_case: GetAudioJob = request.app.state.get_audio_job
    return use_case


def get_record_audio_analysis(request: Request) -> RecordAudioAnalysis:
    use_case: RecordAudioAnalysis = request.app.state.record_audio_analysis
    return use_case


def get_face_job(request: Request) -> GetFaceJob:
    use_case: GetFaceJob = request.app.state.get_face_job
    return use_case


def get_record_identity_check(request: Request) -> RecordIdentityCheck:
    use_case: RecordIdentityCheck = request.app.state.record_identity_check
    return use_case


def get_register_reference_face(request: Request) -> RegisterReferenceFace:
    use_case: RegisterReferenceFace = request.app.state.register_reference_face
    return use_case


def get_request_identity_check(request: Request) -> RequestIdentityCheck:
    use_case: RequestIdentityCheck = request.app.state.request_identity_check
    return use_case


def get_create_bank(request: Request) -> CreateQuestionBank:
    use_case: CreateQuestionBank = request.app.state.create_bank
    return use_case


def get_list_banks(request: Request) -> ListQuestionBanks:
    use_case: ListQuestionBanks = request.app.state.list_banks
    return use_case


def get_list_bank_questions(request: Request) -> ListBankQuestions:
    use_case: ListBankQuestions = request.app.state.list_bank_questions
    return use_case


def get_add_questions_to_bank(request: Request) -> AddQuestionsToBank:
    use_case: AddQuestionsToBank = request.app.state.add_questions_to_bank
    return use_case


def get_attach_bank(request: Request) -> AttachBankToSession:
    use_case: AttachBankToSession = request.app.state.attach_bank
    return use_case


def get_detach_bank(request: Request) -> DetachBankFromSession:
    use_case: DetachBankFromSession = request.app.state.detach_bank
    return use_case


def get_list_session_banks(request: Request) -> ListSessionBanks:
    use_case: ListSessionBanks = request.app.state.list_session_banks
    return use_case


def get_update_session(request: Request) -> UpdateExamSession:
    use_case: UpdateExamSession = request.app.state.update_session
    return use_case


def get_cancel_session(request: Request) -> CancelExamSession:
    use_case: CancelExamSession = request.app.state.cancel_session
    return use_case


def get_delete_session(request: Request) -> DeleteExamSession:
    use_case: DeleteExamSession = request.app.state.delete_session
    return use_case


def get_update_question(request: Request) -> UpdateQuestion:
    use_case: UpdateQuestion = request.app.state.update_question
    return use_case


def get_delete_question(request: Request) -> DeleteQuestion:
    use_case: DeleteQuestion = request.app.state.delete_question
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
AddQuestionsDep = Annotated[AddQuestions, Depends(get_add_questions)]
ListSessionQuestionsDep = Annotated[ListSessionQuestions, Depends(get_list_session_questions)]
GetExamQuestionsDep = Annotated[GetExamQuestions, Depends(get_exam_questions)]
EnrollInExamDep = Annotated[EnrollInExam, Depends(get_enroll_in_exam)]
ListParticipantsDep = Annotated[ListSessionParticipantsWithNames, Depends(get_list_participants)]
ReviewIdentityDep = Annotated[ReviewParticipantIdentity, Depends(get_review_identity)]
SubmitExamDep = Annotated[SubmitExam, Depends(get_submit_exam)]
SaveAnswersDep = Annotated[SaveAnswers, Depends(get_save_answers)]
ListMyExamsDep = Annotated[ListMyExams, Depends(get_list_my_exams)]
ListMyAnswersDep = Annotated[ListMyAnswers, Depends(get_list_my_answers)]
CreateEvidenceUploadUrlDep = Annotated[
    CreateEvidenceUploadUrl, Depends(get_create_evidence_upload_url)
]
CreateCourseDep = Annotated[CreateCourse, Depends(get_create_course)]
ListTeacherCoursesDep = Annotated[ListTeacherCourses, Depends(get_list_teacher_courses)]
GetCourseDep = Annotated[GetCourse, Depends(get_get_course)]
EnrollStudentDep = Annotated[EnrollStudentInCourse, Depends(get_enroll_student)]
ListCourseMembersDep = Annotated[ListCourseMembers, Depends(get_list_course_members)]
ListMyCoursesDep = Annotated[ListMyCourses, Depends(get_list_my_courses)]
ReviewCaseDep = Annotated[ReviewStudentCase, Depends(get_review_case)]
RecordDecisionDep = Annotated[RecordDecision, Depends(get_record_decision)]
ListDecisionsDep = Annotated[ListSessionDecisions, Depends(get_list_decisions)]
GetAudioJobDep = Annotated[GetAudioJob, Depends(get_audio_job)]
RecordAudioAnalysisDep = Annotated[RecordAudioAnalysis, Depends(get_record_audio_analysis)]
GetFaceJobDep = Annotated[GetFaceJob, Depends(get_face_job)]
RecordIdentityCheckDep = Annotated[RecordIdentityCheck, Depends(get_record_identity_check)]
RegisterReferenceFaceDep = Annotated[RegisterReferenceFace, Depends(get_register_reference_face)]
RequestIdentityCheckDep = Annotated[RequestIdentityCheck, Depends(get_request_identity_check)]
CreateBankDep = Annotated[CreateQuestionBank, Depends(get_create_bank)]
ListBanksDep = Annotated[ListQuestionBanks, Depends(get_list_banks)]
ListBankQuestionsDep = Annotated[ListBankQuestions, Depends(get_list_bank_questions)]
AddQuestionsToBankDep = Annotated[AddQuestionsToBank, Depends(get_add_questions_to_bank)]
AttachBankDep = Annotated[AttachBankToSession, Depends(get_attach_bank)]
DetachBankDep = Annotated[DetachBankFromSession, Depends(get_detach_bank)]
ListSessionBanksDep = Annotated[ListSessionBanks, Depends(get_list_session_banks)]
UpdateExamSessionDep = Annotated[UpdateExamSession, Depends(get_update_session)]
CancelExamSessionDep = Annotated[CancelExamSession, Depends(get_cancel_session)]
DeleteExamSessionDep = Annotated[DeleteExamSession, Depends(get_delete_session)]
UpdateQuestionDep = Annotated[UpdateQuestion, Depends(get_update_question)]
DeleteQuestionDep = Annotated[DeleteQuestion, Depends(get_delete_question)]
