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
    ExamNotStartedError,
    ListSessionParticipants,
    ReviewParticipantIdentity,
    SubmitExam,
    ensure_can_take_exam,
)
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.exam_session import EntryState, ExamSession
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

    def test_sin_autenticacion_el_revisor_es_el_docente_de_desarrollo(
        self,
        enroll: EnrollInExam,
        participants: InMemoryParticipantRepository,
        sessions: InMemoryExamSessionRepository,
        sesion: ExamSession,
        clock: FixedClock,
    ) -> None:
        """El revisor tiene que ser **una persona**, nunca otra cosa.

        Antes, sin actor, se guardaba aquí el `session_id`: una pista de auditoría
        falsa, y contra PostgreSQL un fallo de clave ajena a `profiles`. La
        columna existe para responder "quién lo admitió".
        """
        enroll.execute(sesion.id, accepts_supervision=True, actor=None)
        matricula = next(iter(participants.list_by_session(sesion.id)))
        participants.save(matricula.verification_failed())
        docente_dev = uuid4()

        revisado = ReviewParticipantIdentity(participants, sessions, clock, docente_dev).execute(
            sesion.id, matricula.student_id, approve=True, actor=None
        )

        assert revisado.verification_reviewed_by == docente_dev
        assert revisado.verification_reviewed_by != sesion.id
        assert revisado.verification_reviewed_by != matricula.student_id

    def test_rechazar_sin_autenticacion_tambien_registra_una_persona(
        self,
        enroll: EnrollInExam,
        participants: InMemoryParticipantRepository,
        sessions: InMemoryExamSessionRepository,
        sesion: ExamSession,
        clock: FixedClock,
    ) -> None:
        """Rechazar pasa por la misma línea, así que se comprueba igual."""
        enroll.execute(sesion.id, accepts_supervision=True, actor=None)
        matricula = next(iter(participants.list_by_session(sesion.id)))
        docente_dev = uuid4()

        revisado = ReviewParticipantIdentity(participants, sessions, clock, docente_dev).execute(
            sesion.id, matricula.student_id, approve=False, actor=None
        )

        assert revisado.verification_status is VerificationStatus.REJECTED
        assert revisado.verification_reviewed_by == docente_dev


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


class TestLlegarAntesDeTiempo:
    """Llegar pronto y llegar tarde no son lo mismo para quien espera."""

    def escenario(self, empieza_en: timedelta) -> tuple[EnrollInExam, ExamSession]:
        sessions = InMemoryExamSessionRepository()
        sesion = ExamSession.create(
            teacher_id=DOCENTE.id,
            title="Parcial",
            starts_at=NOW + empieza_en,
            duration_minutes=60,
            entry_tolerance_minutes=10,
        )
        sessions.save(sesion)
        caso = EnrollInExam(InMemoryParticipantRepository(), sessions, FixedClock(NOW))
        return caso, sesion

    def test_antes_de_la_hora_dice_que_espere(self) -> None:
        # Era el error: recibia "el plazo esta cerrado", que es lo contrario.
        caso, sesion = self.escenario(timedelta(minutes=30))

        with pytest.raises(ExamNotStartedError, match="todavia no empieza"):
            caso.execute(sesion.id, accepts_supervision=True, actor=ANA)

    def test_pasada_la_tolerancia_dice_que_hable_con_su_docente(self) -> None:
        caso, sesion = self.escenario(timedelta(minutes=-30))

        with pytest.raises(AuthorizationError, match="cerrado"):
            caso.execute(sesion.id, accepts_supervision=True, actor=ANA)

    def test_dentro_de_la_ventana_entra(self) -> None:
        caso, sesion = self.escenario(timedelta(minutes=-5))

        resultado = caso.execute(sesion.id, accepts_supervision=True, actor=ANA)

        assert resultado.participant.has_consented


class TestEstadoDeLaVentana:
    def sesion(self, empieza_en: timedelta, tolerancia: int = 10) -> ExamSession:
        return ExamSession.create(
            teacher_id=DOCENTE.id,
            title="Parcial",
            starts_at=NOW + empieza_en,
            duration_minutes=60,
            entry_tolerance_minutes=tolerancia,
        )

    def test_los_tres_estados(self) -> None:
        assert self.sesion(timedelta(minutes=1)).entry_state_at(NOW) is EntryState.NOT_STARTED
        assert self.sesion(timedelta(minutes=-1)).entry_state_at(NOW) is EntryState.OPEN
        assert self.sesion(timedelta(minutes=-30)).entry_state_at(NOW) is EntryState.CLOSED

    def test_justo_a_la_hora_de_inicio_ya_abre(self) -> None:
        assert self.sesion(timedelta(0)).entry_state_at(NOW) is EntryState.OPEN

    def test_justo_en_el_limite_de_tolerancia_sigue_abierto(self) -> None:
        assert self.sesion(timedelta(minutes=-10)).entry_state_at(NOW) is EntryState.OPEN

    def test_un_segundo_despues_ya_no(self) -> None:
        sesion = self.sesion(timedelta(minutes=-10))

        assert sesion.entry_state_at(NOW + timedelta(seconds=1)) is EntryState.CLOSED

    def test_una_tolerancia_mayor_que_el_examen_no_lo_alarga(self) -> None:
        # Con 180 min de tolerancia sobre un examen de 60, la puerta cierra con
        # el examen, no tres horas despues.
        sesion = self.sesion(timedelta(minutes=-90), tolerancia=180)

        assert sesion.entry_state_at(NOW) is EntryState.CLOSED
