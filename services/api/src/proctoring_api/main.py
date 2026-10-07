"""Composicion de dependencias y aplicacion FastAPI.

Este es el unico archivo que conoce **todos** los adaptadores a la vez. Es el
precio de la arquitectura hexagonal y tambien su beneficio: el cableado esta en un
solo sitio y se lee de arriba abajo.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from proctoring_api import __version__
from proctoring_api.adapters.inbound.http.errors import register_error_handlers
from proctoring_api.adapters.inbound.http.rate_limit import RateLimitMiddleware
from proctoring_api.adapters.inbound.http.routers import (
    ai,
    answers,
    banks,
    courses,
    enrollment,
    events,
    evidence,
    health,
    questions,
    review,
    sessions,
)
from proctoring_api.adapters.outbound.clock import SystemClock
from proctoring_api.adapters.outbound.memory.alert_repository import InMemoryAlertRepository
from proctoring_api.adapters.outbound.memory.answer_repository import InMemoryAnswerRepository
from proctoring_api.adapters.outbound.memory.audio_analysis_repository import (
    InMemoryAudioAnalysisRepository,
)
from proctoring_api.adapters.outbound.memory.course_repository import InMemoryCourseRepository
from proctoring_api.adapters.outbound.memory.decision_repository import (
    InMemoryDecisionRepository,
)
from proctoring_api.adapters.outbound.memory.event_repository import InMemoryEventRepository
from proctoring_api.adapters.outbound.memory.evidence_storage import InMemoryEvidenceStorage
from proctoring_api.adapters.outbound.memory.exam_session_repository import (
    InMemoryExamSessionRepository,
)
from proctoring_api.adapters.outbound.memory.job_queue import InMemoryJobQueue
from proctoring_api.adapters.outbound.memory.participant_repository import (
    InMemoryParticipantRepository,
)
from proctoring_api.adapters.outbound.memory.profile_repository import InMemoryProfileRepository
from proctoring_api.adapters.outbound.memory.question_bank_repository import (
    InMemoryQuestionBankRepository,
)
from proctoring_api.adapters.outbound.memory.question_repository import (
    InMemoryQuestionRepository,
)
from proctoring_api.adapters.outbound.memory.reference_face_repository import (
    InMemoryReferenceFaceRepository,
)
from proctoring_api.application.ports.alert_repository import AlertRepository
from proctoring_api.application.ports.answer_repository import AnswerRepository
from proctoring_api.application.ports.audio_analysis_repository import AudioAnalysisRepository
from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.course_repository import CourseRepository
from proctoring_api.application.ports.decision_repository import DecisionRepository
from proctoring_api.application.ports.event_repository import EventRepository
from proctoring_api.application.ports.evidence_storage import EvidenceStorage
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.ports.job_queue import JobQueue
from proctoring_api.application.ports.participant_repository import ParticipantRepository
from proctoring_api.application.ports.profile_repository import ProfileRepository
from proctoring_api.application.ports.question_bank_repository import QuestionBankRepository
from proctoring_api.application.ports.question_repository import QuestionRepository
from proctoring_api.application.ports.reference_face_repository import ReferenceFaceRepository
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
from proctoring_api.config import ENVS_WITHOUT_AUTH, Settings
from proctoring_api.domain.evidence import EvidenceKind

DESCRIPTION = """
API principal del sistema de proctoring para examenes remotos (UPAO, Taller Integrador 1).

Recibe las senales que detectan la app de escritorio del estudiante y la web, las
guarda como evidencia y encola el analisis de audio del servicio de IA.

**No recibe video.** Solo eventos, y la ruta en Storage de la captura o del
fragmento de audio, que el cliente sube directo con una URL firmada.

El sistema es un auditor, no un juez: calcula riesgo y entrega evidencia; la
decision final es del docente, con justificacion obligatoria.

## Autenticacion

Token de Supabase Auth en `Authorization: Bearer <token>`. Un estudiante solo
puede registrar eventos sobre si mismo y solo puede leer los suyos.
"""


def _build_supabase_client(settings: Settings) -> object:
    from supabase import create_client

    url, key = settings.require_supabase()
    return create_client(url, key)


def _build_event_repository(settings: Settings, client: object | None) -> EventRepository:
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.event_repository import (
            SupabaseEventRepository,
        )

        assert isinstance(client, Client)
        return SupabaseEventRepository(client)

    return InMemoryEventRepository()


def _build_alert_repository(settings: Settings, client: object | None) -> AlertRepository:
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.alert_repository import (
            SupabaseAlertRepository,
        )

        assert isinstance(client, Client)
        return SupabaseAlertRepository(client)

    return InMemoryAlertRepository()


def _build_profile_repository(settings: Settings, client: object | None) -> ProfileRepository:
    # Los perfiles viven en la misma base que los eventos, asi que siguen el mismo
    # adaptador: no tiene sentido leer eventos de Supabase y perfiles de memoria.
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.profile_repository import (
            SupabaseProfileRepository,
        )

        assert isinstance(client, Client)
        return SupabaseProfileRepository(client)

    return InMemoryProfileRepository()


def _build_question_repository(settings: Settings, client: object | None) -> QuestionRepository:
    """Banco de preguntas del examen.

    En memoria tambien existe de verdad: las preguntas se crean por la API y se
    pueden listar. Lo que cambia es que `RegisterEvent` solo valida el
    `question_id` contra el cuando hay Supabase detras (ver `create_app`), para
    no bloquear a quien manda eventos sin haber creado un examen.
    """
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.question_repository import (
            SupabaseQuestionRepository,
        )

        assert isinstance(client, Client)
        return SupabaseQuestionRepository(client)

    return InMemoryQuestionRepository()


def _build_session_repository(settings: Settings, client: object | None) -> ExamSessionRepository:
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.exam_session_repository import (
            SupabaseExamSessionRepository,
        )

        assert isinstance(client, Client)
        return SupabaseExamSessionRepository(client)

    # En memoria las sesiones existen de verdad: se crean por la API y se pueden
    # listar. Ya no hace falta devolver None.
    return InMemoryExamSessionRepository()


def _build_evidence_storage(settings: Settings, client: object | None) -> EvidenceStorage:
    if settings.evidence_storage == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.evidence_storage import (
            SupabaseEvidenceStorage,
        )

        assert isinstance(client, Client)
        return SupabaseEvidenceStorage(client)

    return InMemoryEvidenceStorage()


def _build_audio_analysis_repository(
    settings: Settings, client: object | None
) -> AudioAnalysisRepository:
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.audio_analysis_repository import (
            SupabaseAudioAnalysisRepository,
        )

        assert isinstance(client, Client)
        return SupabaseAudioAnalysisRepository(client)

    return InMemoryAudioAnalysisRepository()


def _build_reference_face_repository(
    settings: Settings, client: object | None
) -> ReferenceFaceRepository:
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.reference_face_repository import (
            SupabaseReferenceFaceRepository,
        )

        assert isinstance(client, Client)
        return SupabaseReferenceFaceRepository(client)

    return InMemoryReferenceFaceRepository()


def _build_decision_repository(settings: Settings, client: object | None) -> DecisionRepository:
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.decision_repository import (
            SupabaseDecisionRepository,
        )

        assert isinstance(client, Client)
        return SupabaseDecisionRepository(client)

    return InMemoryDecisionRepository()


def _build_question_bank_repository(
    settings: Settings, client: object | None, questions: QuestionRepository
) -> QuestionBankRepository:
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.question_bank_repository import (
            SupabaseQuestionBankRepository,
        )

        assert isinstance(client, Client)
        return SupabaseQuestionBankRepository(client)

    # El de memoria cuenta preguntas mirando el repositorio de preguntas.
    return InMemoryQuestionBankRepository(questions)


def _build_course_repository(settings: Settings, client: object | None) -> CourseRepository:
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.course_repository import (
            SupabaseCourseRepository,
        )

        assert isinstance(client, Client)
        return SupabaseCourseRepository(client)

    return InMemoryCourseRepository()


def _build_answer_repository(settings: Settings, client: object | None) -> AnswerRepository:
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.answer_repository import (
            SupabaseAnswerRepository,
        )

        assert isinstance(client, Client)
        return SupabaseAnswerRepository(client)

    return InMemoryAnswerRepository()


def _build_participant_repository(
    settings: Settings, client: object | None
) -> ParticipantRepository:
    if settings.event_repository == "supabase":
        from supabase import Client

        from proctoring_api.adapters.outbound.supabase.participant_repository import (
            SupabaseParticipantRepository,
        )

        assert isinstance(client, Client)
        return SupabaseParticipantRepository(client)

    return InMemoryParticipantRepository()


def _build_job_queue(settings: Settings) -> JobQueue:
    if settings.job_queue == "redis":
        from proctoring_api.adapters.outbound.redis_queue.job_queue import RedisJobQueue

        return RedisJobQueue(settings.redis_url)

    # En memoria por defecto: la API levanta sin Redis y las pruebas corren sin
    # servicios externos.
    return InMemoryJobQueue()


def _build_identify_user(settings: Settings, profiles: ProfileRepository) -> IdentifyUser | None:
    """`None` significa autenticacion desactivada.

    Solo se permite en desarrollo local. En cualquier otro entorno el servicio se
    niega a arrancar: es preferible un despliegue que falla a uno que acepta
    evidencia de cualquiera.
    """
    if not settings.auth_enabled:
        if settings.env not in ENVS_WITHOUT_AUTH:
            raise ValueError(
                f"AUTH_ENABLED=false solo se permite con ENV en "
                f"{sorted(ENVS_WITHOUT_AUTH)} (ENV={settings.env!r}). "
                "Desplegar la API sin autenticacion dejaria que cualquiera "
                "fabricara evidencia contra cualquier estudiante."
            )
        return None

    from proctoring_api.adapters.outbound.supabase.token_verifier import (
        SupabaseTokenVerifier,
    )

    return IdentifyUser(SupabaseTokenVerifier(settings.require_supabase_url()), profiles)


def create_app(
    settings: Settings | None = None,
    clock: Clock | None = None,
    identify_user: IdentifyUser | None = None,
) -> FastAPI:
    """Arma la aplicacion con los adaptadores que indique la configuracion.

    `clock` e `identify_user` se pueden sustituir para que las pruebas de
    integracion no dependan de la hora a la que se ejecuten ni de un proyecto de
    Supabase real. Si se pasa `identify_user`, manda sobre `AUTH_ENABLED`.
    """
    settings = settings or Settings()

    app = FastAPI(
        title="Proctoring API",
        description=DESCRIPTION,
        version=__version__,
        openapi_tags=[
            {"name": "health", "description": "Estado del servicio"},
            {"name": "events", "description": "Senales detectadas durante un examen"},
            {"name": "evidence", "description": "Subida de capturas y audio a Storage"},
            {"name": "sessions", "description": "Sesiones de examen del docente"},
            {"name": "questions", "description": "Banco de preguntas y examen del estudiante"},
            {
                "name": "enrollment",
                "description": "Matricula, consentimiento y entrega del examen",
            },
        ],
    )

    # Un comodin junto a allow_credentials deja que CUALQUIER sitio haga
    # peticiones autenticadas en nombre del docente. Los navegadores lo rechazan,
    # pero no todos los clientes son navegadores, y el error seria silencioso.
    # Los endpoints internos escriben evidencia y aplican la regla de alerta. Sin
    # el secreto quedarian abiertos a cualquiera que conozca la URL, asi que se
    # exige en cuanto la autenticacion esta activa: mejor un despliegue que falla
    # al arrancar que uno que acepta analisis de cualquiera.
    if settings.auth_enabled and not settings.internal_api_token:
        raise ValueError(
            "Falta INTERNAL_API_TOKEN. Los endpoints internos de services/ai "
            "quedarian abiertos. Genera un secreto largo y ponlo en el .env y en "
            "el entorno del worker."
        )

    if "*" in settings.cors_origins:
        raise ValueError(
            "CORS_ORIGINS no puede ser '*': la API envia credenciales. "
            "Enumera los origenes, separados por coma."
        )

    # El limite va ANTES que CORS en el orden de registro, por lo que Starlette
    # lo ejecuta DESPUES: asi una respuesta 429 tambien lleva las cabeceras de
    # CORS y el navegador puede leer el motivo en vez de ver un error opaco.
    if settings.rate_limit_enabled:
        app.add_middleware(RateLimitMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Cableado: adaptadores -> casos de uso ---
    # Un solo cliente para todos los adaptadores de Supabase que haga falta.
    needs_supabase = "supabase" in (settings.event_repository, settings.evidence_storage)
    client = _build_supabase_client(settings) if needs_supabase else None

    event_repository = _build_event_repository(settings, client)
    alert_repository = _build_alert_repository(settings, client)
    question_repository = _build_question_repository(settings, client)
    participant_repository = _build_participant_repository(settings, client)
    answer_repository = _build_answer_repository(settings, client)
    course_repository = _build_course_repository(settings, client)
    bank_repository = _build_question_bank_repository(settings, client, question_repository)
    decision_repository = _build_decision_repository(settings, client)
    audio_analysis_repository = _build_audio_analysis_repository(settings, client)
    reference_face_repository = _build_reference_face_repository(settings, client)
    session_repository = _build_session_repository(settings, client)
    evidence_storage = _build_evidence_storage(settings, client)
    profile_repository = _build_profile_repository(settings, client)
    job_queue = _build_job_queue(settings)
    clock = clock or SystemClock()

    app.state.settings = settings
    app.state.event_repository = event_repository
    app.state.alert_repository = alert_repository
    app.state.session_repository = session_repository
    app.state.profile_repository = profile_repository
    app.state.job_queue = job_queue
    app.state.identify_user = identify_user or _build_identify_user(settings, profile_repository)
    app.state.register_event = RegisterEvent(
        event_repository,
        job_queue,
        clock,
        alert_repository,
        # Solo se valida el question_id cuando hay un banco real detras.
        question_repository if settings.event_repository == "supabase" else None,
    )
    app.state.list_session_events = ListSessionEvents(event_repository, session_repository)
    app.state.list_session_alerts = ListSessionAlerts(alert_repository, session_repository)
    app.state.create_exam_session = CreateExamSession(
        session_repository, settings.dev_teacher_id, course_repository
    )
    app.state.course_repository = course_repository
    app.state.decision_repository = decision_repository
    app.state.audio_analysis_repository = audio_analysis_repository
    app.state.reference_face_repository = reference_face_repository
    # --- Servicio de IA: el worker mide, la API decide ---
    app.state.get_audio_job = GetAudioJob(
        event_repository,
        session_repository,
        question_repository,
        settings.supabase_audio_bucket,
    )
    app.state.record_audio_analysis = RecordAudioAnalysis(
        audio_analysis_repository,
        event_repository,
        session_repository,
        alert_repository,
        clock,
    )
    app.state.get_face_job = GetFaceJob(
        participant_repository,
        session_repository,
        reference_face_repository,
        settings.supabase_reference_faces_bucket,
        settings.supabase_evidence_bucket,
    )
    app.state.record_identity_check = RecordIdentityCheck(
        participant_repository,
        session_repository,
        event_repository,
        reference_face_repository,
        clock,
    )
    app.state.register_reference_face = RegisterReferenceFace(
        reference_face_repository, clock, settings.dev_student_id
    )
    app.state.request_identity_check = RequestIdentityCheck(
        participant_repository, reference_face_repository, job_queue, settings.dev_student_id
    )
    app.state.review_case = ReviewStudentCase(
        event_repository,
        alert_repository,
        session_repository,
        participant_repository,
        profile_repository,
        decision_repository,
    )
    app.state.record_decision = RecordDecision(
        decision_repository,
        session_repository,
        participant_repository,
        clock,
        settings.dev_teacher_id,
    )
    app.state.list_decisions = ListSessionDecisions(decision_repository, session_repository)
    app.state.create_course = CreateCourse(course_repository, clock, settings.dev_teacher_id)
    app.state.list_teacher_courses = ListTeacherCourses(course_repository, settings.dev_teacher_id)
    app.state.get_course = GetCourse(course_repository)
    app.state.enroll_student = EnrollStudentInCourse(course_repository, profile_repository, clock)
    app.state.list_course_members = ListCourseMembers(course_repository, profile_repository)
    app.state.list_my_courses = ListMyCourses(
        course_repository, session_repository, settings.dev_student_id
    )
    app.state.list_teacher_sessions = ListTeacherSessions(
        session_repository, settings.dev_teacher_id
    )
    app.state.get_exam_session = GetExamSession(session_repository)
    app.state.join_exam_session = JoinExamSession(session_repository, clock)
    app.state.add_questions = AddQuestions(question_repository, session_repository)
    app.state.list_session_questions = ListSessionQuestions(question_repository, session_repository)
    app.state.get_exam_questions = GetExamQuestions(
        question_repository,
        session_repository,
        clock,
        participant_repository,
        settings.dev_student_id,
        bank_repository,
    )
    app.state.bank_repository = bank_repository
    app.state.create_bank = CreateQuestionBank(bank_repository, clock, settings.dev_teacher_id)
    app.state.list_banks = ListQuestionBanks(bank_repository, settings.dev_teacher_id)
    app.state.list_bank_questions = ListBankQuestions(bank_repository, question_repository)
    app.state.add_questions_to_bank = AddQuestionsToBank(bank_repository, question_repository)
    app.state.attach_bank = AttachBankToSession(bank_repository, session_repository)
    app.state.detach_bank = DetachBankFromSession(bank_repository, session_repository)
    app.state.list_session_banks = ListSessionBanks(bank_repository, session_repository)
    app.state.participant_repository = participant_repository
    app.state.answer_repository = answer_repository
    app.state.enroll_in_exam = EnrollInExam(
        participant_repository, session_repository, clock, settings.dev_student_id
    )
    app.state.list_participants = ListSessionParticipantsWithNames(
        participant_repository, session_repository, profile_repository
    )
    app.state.review_identity = ReviewParticipantIdentity(
        participant_repository, session_repository, clock
    )
    app.state.submit_exam = SubmitExam(
        participant_repository,
        clock,
        settings.dev_student_id,
        question_repository,
        answer_repository,
    )
    app.state.list_my_exams = ListMyExams(
        participant_repository,
        session_repository,
        clock,
        settings.dev_student_id,
        question_repository,
    )
    app.state.save_answers = SaveAnswers(
        answer_repository,
        question_repository,
        participant_repository,
        session_repository,
        clock,
        settings.dev_student_id,
    )
    app.state.list_my_answers = ListMyAnswers(
        answer_repository, participant_repository, settings.dev_student_id
    )
    app.state.create_evidence_upload_url = CreateEvidenceUploadUrl(
        evidence_storage,
        {
            EvidenceKind.IMAGE: settings.supabase_evidence_bucket,
            EvidenceKind.AUDIO: settings.supabase_audio_bucket,
            EvidenceKind.REFERENCE_FACE: settings.supabase_reference_faces_bucket,
        },
    )

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(events.router)
    app.include_router(evidence.router)
    app.include_router(sessions.router)
    app.include_router(questions.router)
    app.include_router(enrollment.router)
    app.include_router(answers.router)
    app.include_router(courses.router)
    app.include_router(banks.router)
    app.include_router(review.router)
    app.include_router(ai.router)
    app.include_router(ai.internal)

    return app


# Se arranca con `--factory` (ver Dockerfile y README) en vez de dejar aqui un
# `app = create_app()`. Si la app se construyera al importar el modulo, importarlo
# para cualquier cosa (una prueba, un script) abriria la conexion a Supabase que
# diga el .env del momento.
