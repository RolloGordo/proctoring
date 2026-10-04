"""Matrícula, consentimiento y entrega."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from proctoring_api.adapters.outbound.memory.exam_session_repository import (
    InMemoryExamSessionRepository,
)
from proctoring_api.adapters.outbound.memory.participant_repository import (
    InMemoryParticipantRepository,
)
from proctoring_api.application.use_cases.manage_enrollment import (
    ConsentRequiredError,
    EnrollInExam,
    ListSessionParticipants,
    ReviewParticipantIdentity,
    SubmitExam,
    ensure_can_take_exam,
)
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.participant import (
    InvalidEnrollmentError,
    SessionParticipant,
    VerificationStatus,
)
from proctoring_api.domain.user import AuthenticatedUser, UserRole

from tests.conftest import NOW, FixedClock

ANA = AuthenticatedUser(id=uuid4(), role=UserRole.STUDENT)
LUIS = AuthenticatedUser(id=uuid4(), role=UserRole.STUDENT)
DOCENTE = AuthenticatedUser(id=uuid4(), role=UserRole.TEACHER)


def una_sesion(empieza_en: timedelta = timedelta(minutes=-5)) -> ExamSession:
    return ExamSession.create(
        teacher_id=DOCENTE.id,
        title="Parcial",
        starts_at=NOW + empieza_en,
        duration_minutes=90,
    )


@pytest.fixture
def sessions() -> InMemoryExamSessionRepository:
    repositorio = InMemoryExamSessionRepository()
    repositorio.save(una_sesion())
    return repositorio


@pytest.fixture
def participants() -> InMemoryParticipantRepository:
    return InMemoryParticipantRepository()


@pytest.fixture
def sesion(sessions: InMemoryExamSessionRepository) -> ExamSession:
    return sessions.list_by_teacher(DOCENTE.id)[0]


@pytest.fixture
def enroll(
    participants: InMemoryParticipantRepository,
    sessions: InMemoryExamSessionRepository,
    clock: FixedClock,
) -> EnrollInExam:
    return EnrollInExam(participants, sessions, clock)


class TestConsentimiento:
    def test_sin_aceptar_la_supervision_no_se_matricula(
        self, enroll: EnrollInExam, sesion: ExamSession
    ) -> None:
        """El consentimiento no es un trámite.

        El sistema observa cámara, micrófono, pantalla y procesos. Que la
        persona lo sepa y lo acepte antes de empezar es la diferencia entre
        supervisar y espiar.
        """
        with pytest.raises(ConsentRequiredError, match="aceptar la supervision"):
            enroll.execute(sesion.id, accepts_supervision=False, actor=ANA)

    def test_no_queda_matricula_si_no_consintio(
        self,
        enroll: EnrollInExam,
        sesion: ExamSession,
        participants: InMemoryParticipantRepository,
    ) -> None:
        with pytest.raises(ConsentRequiredError):
            enroll.execute(sesion.id, accepts_supervision=False, actor=ANA)

        assert participants.find(sesion.id, ANA.id) is None

    def test_al_aceptar_queda_registrado_cuando(
        self, enroll: EnrollInExam, sesion: ExamSession
    ) -> None:
        resultado = enroll.execute(sesion.id, accepts_supervision=True, actor=ANA)

        assert resultado.participant.consent_at == NOW
        assert resultado.participant.has_consented

    def test_entra_pendiente_de_verificar(self, enroll: EnrollInExam, sesion: ExamSession) -> None:
        # La verificación facial es el paso siguiente; hasta entonces no debería
        # ver las preguntas.
        resultado = enroll.execute(sesion.id, accepts_supervision=True, actor=ANA)

        assert resultado.participant.verification_status is VerificationStatus.PENDING
        assert resultado.participant.can_take_exam is False

    def test_volver_a_entrar_no_pide_consentir_otra_vez(
        self, enroll: EnrollInExam, sesion: ExamSession
    ) -> None:
        primera = enroll.execute(sesion.id, accepts_supervision=True, actor=ANA)

        # Recarga la página: no debe volver a pedírselo ni reiniciar su estado.
        segunda = enroll.execute(sesion.id, accepts_supervision=False, actor=ANA)

        assert segunda.participant.id == primera.participant.id
        assert segunda.participant.consent_at == primera.participant.consent_at


class TestVentanaDeIngreso:
    def test_no_se_matricula_fuera_de_plazo(
        self,
        participants: InMemoryParticipantRepository,
        clock: FixedClock,
    ) -> None:
        sessions = InMemoryExamSessionRepository()
        vencida = una_sesion(empieza_en=timedelta(hours=-3))
        sessions.save(vencida)

        with pytest.raises(AuthorizationError, match="plazo de ingreso"):
            EnrollInExam(participants, sessions, clock).execute(
                vencida.id, accepts_supervision=True, actor=ANA
            )

    def test_una_sesion_inexistente_responde_como_una_ajena(self, enroll: EnrollInExam) -> None:
        with pytest.raises(AuthorizationError, match="No tienes acceso"):
            enroll.execute(uuid4(), accepts_supervision=True, actor=ANA)


class TestQuienPuedeMatricularse:
    def test_un_docente_no_se_matricula_en_su_examen(
        self, enroll: EnrollInExam, sesion: ExamSession
    ) -> None:
        with pytest.raises(AuthorizationError, match="docente"):
            enroll.execute(sesion.id, accepts_supervision=True, actor=DOCENTE)


class TestAccesoAlExamen:
    """`ensure_can_take_exam` es la comprobación que faltaba."""

    def test_sin_matricula_no_hay_examen(
        self, participants: InMemoryParticipantRepository, sesion: ExamSession
    ) -> None:
        # Conocer el session_id de un examen ajeno no da acceso a sus preguntas.
        with pytest.raises(AuthorizationError, match="No estas matriculado"):
            ensure_can_take_exam(participants, sesion.id, ANA)

    def test_matriculado_pero_sin_verificar_tampoco(
        self,
        enroll: EnrollInExam,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
    ) -> None:
        enroll.execute(sesion.id, accepts_supervision=True, actor=ANA)

        with pytest.raises(AuthorizationError, match="identidad"):
            ensure_can_take_exam(participants, sesion.id, ANA)

    def test_verificado_si_puede(
        self,
        enroll: EnrollInExam,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
    ) -> None:
        enroll.execute(sesion.id, accepts_supervision=True, actor=ANA)
        matricula = participants.find(sesion.id, ANA.id)
        assert matricula is not None
        participants.save(matricula.verified(NOW))

        ensure_can_take_exam(participants, sesion.id, ANA)  # no lanza

    def test_quien_ya_entrego_no_vuelve_a_ver_las_preguntas(
        self,
        enroll: EnrollInExam,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
    ) -> None:
        enroll.execute(sesion.id, accepts_supervision=True, actor=ANA)
        matricula = participants.find(sesion.id, ANA.id)
        assert matricula is not None
        participants.save(matricula.verified(NOW).submitted(NOW))

        with pytest.raises(AuthorizationError, match="Ya entregaste"):
            ensure_can_take_exam(participants, sesion.id, ANA)

    def test_sin_repositorio_no_se_comprueba(self, sesion: ExamSession) -> None:
        # Modo de desarrollo sin matrículas.
        ensure_can_take_exam(None, sesion.id, ANA)


class TestRevisionManualDeIdentidad:
    def test_el_docente_admite_a_mano_y_queda_registrado(
        self,
        enroll: EnrollInExam,
        participants: InMemoryParticipantRepository,
        sessions: InMemoryExamSessionRepository,
        sesion: ExamSession,
        clock: FixedClock,
    ) -> None:
        """Un reconocimiento que falla con mala luz no puede costar un examen."""
        enroll.execute(sesion.id, accepts_supervision=True, actor=ANA)
        matricula = participants.find(sesion.id, ANA.id)
        assert matricula is not None
        participants.save(matricula.verification_failed())

        revisado = ReviewParticipantIdentity(participants, sessions, clock).execute(
            sesion.id, ANA.id, approve=True, actor=DOCENTE
        )

        assert revisado.verification_status is VerificationStatus.MANUALLY_APPROVED
        # Es una decisión con consecuencias: tiene que tener un responsable.
        assert revisado.verification_reviewed_by == DOCENTE.id
        assert revisado.can_take_exam

    def test_un_estudiante_no_revisa_identidades(
        self,
        participants: InMemoryParticipantRepository,
        sessions: InMemoryExamSessionRepository,
        sesion: ExamSession,
        clock: FixedClock,
    ) -> None:
        with pytest.raises(AuthorizationError, match="Solo el docente"):
            ReviewParticipantIdentity(participants, sessions, clock).execute(
                sesion.id, LUIS.id, approve=True, actor=ANA
            )


class TestEntrega:
    def test_entregar_marca_la_hora(
        self,
        enroll: EnrollInExam,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
        clock: FixedClock,
    ) -> None:
        enroll.execute(sesion.id, accepts_supervision=True, actor=ANA)

        entregado = SubmitExam(participants, clock).execute(sesion.id, actor=ANA)

        assert entregado.submitted_at == NOW
        assert entregado.has_submitted

    def test_no_se_puede_reenviar(
        self,
        enroll: EnrollInExam,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
        clock: FixedClock,
    ) -> None:
        # Sobrescribir la hora de entrega destruiría evidencia.
        enroll.execute(sesion.id, accepts_supervision=True, actor=ANA)
        submit = SubmitExam(participants, clock)
        submit.execute(sesion.id, actor=ANA)

        with pytest.raises(InvalidEnrollmentError, match="ya fue entregado"):
            submit.execute(sesion.id, actor=ANA)

    def test_sin_matricula_no_se_entrega(
        self,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
        clock: FixedClock,
    ) -> None:
        with pytest.raises(AuthorizationError, match="No estas matriculado"):
            SubmitExam(participants, clock).execute(sesion.id, actor=ANA)


class TestSalaDeEsperaDelDocente:
    def test_lista_a_quien_llego(
        self,
        enroll: EnrollInExam,
        participants: InMemoryParticipantRepository,
        sessions: InMemoryExamSessionRepository,
        sesion: ExamSession,
    ) -> None:
        enroll.execute(sesion.id, accepts_supervision=True, actor=ANA)
        enroll.execute(sesion.id, accepts_supervision=True, actor=LUIS)

        lista = ListSessionParticipants(participants, sessions).execute(sesion.id, actor=DOCENTE)

        assert {p.student_id for p in lista} == {ANA.id, LUIS.id}

    def test_un_estudiante_no_ve_quien_mas_rinde(
        self,
        participants: InMemoryParticipantRepository,
        sessions: InMemoryExamSessionRepository,
        sesion: ExamSession,
    ) -> None:
        with pytest.raises(AuthorizationError, match="Solo el docente"):
            ListSessionParticipants(participants, sessions).execute(sesion.id, actor=ANA)

    def test_un_docente_ajeno_tampoco(
        self,
        participants: InMemoryParticipantRepository,
        sessions: InMemoryExamSessionRepository,
        sesion: ExamSession,
    ) -> None:
        otro = AuthenticatedUser(id=uuid4(), role=UserRole.TEACHER)

        with pytest.raises(AuthorizationError, match="acceso a esta sesion"):
            ListSessionParticipants(participants, sessions).execute(sesion.id, actor=otro)


def test_una_matricula_sin_consentimiento_no_se_puede_construir() -> None:
    # `consented_at` no tiene valor por defecto: hacerlo opcional dejaria crear
    # participantes sin consentimiento.
    with pytest.raises(TypeError):
        SessionParticipant.enroll(session_id=uuid4(), student_id=uuid4())  # type: ignore[call-arg]
