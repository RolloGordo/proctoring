"""Corregir, cancelar y borrar un examen.

Lo que de verdad se prueba aquí es qué **no** se puede hacer: borrar un examen
con evidencia, cambiar la escala con gente dentro, o colar por la edición un
examen que `create` nunca habría aceptado.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from proctoring_api.adapters.outbound.memory.exam_session_repository import (
    InMemoryExamSessionRepository,
)
from proctoring_api.adapters.outbound.memory.participant_repository import (
    InMemoryParticipantRepository,
)
from proctoring_api.application.use_cases.edit_exam_session import (
    CancelExamSession,
    DeleteExamSession,
    ExamInUseError,
    ExamSessionChanges,
    UpdateExamSession,
)
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.exam_session import (
    EntryState,
    ExamSession,
    InvalidExamSessionError,
    SessionStatus,
    SupervisionPreset,
)
from proctoring_api.domain.participant import SessionParticipant
from proctoring_api.domain.user import AuthenticatedUser, UserRole

from tests.conftest import NOW, FixedClock

DOCENTE = AuthenticatedUser(id=uuid4(), role=UserRole.TEACHER)
OTRO_DOCENTE = AuthenticatedUser(id=uuid4(), role=UserRole.TEACHER)
ANA = AuthenticatedUser(id=uuid4(), role=UserRole.STUDENT)


@pytest.fixture
def sessions() -> InMemoryExamSessionRepository:
    return InMemoryExamSessionRepository()


@pytest.fixture
def participants() -> InMemoryParticipantRepository:
    return InMemoryParticipantRepository()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def sesion(sessions: InMemoryExamSessionRepository) -> ExamSession:
    creada = ExamSession.create(
        teacher_id=DOCENTE.id,
        title="Parcial de bases de datos",
        starts_at=NOW + timedelta(days=1),
        duration_minutes=90,
    )
    sessions.save(creada)
    return creada


def con_un_estudiante(participants: InMemoryParticipantRepository, sesion: ExamSession) -> None:
    participants.save(
        SessionParticipant.enroll(session_id=sesion.id, student_id=ANA.id, consented_at=NOW)
    )


class TestCorregir:
    def test_se_cambia_la_fecha(
        self, sessions: InMemoryExamSessionRepository, sesion: ExamSession
    ) -> None:
        nueva = NOW + timedelta(days=3)

        corregida = UpdateExamSession(sessions).execute(
            sesion.id, ExamSessionChanges(starts_at=nueva), actor=DOCENTE
        )

        assert corregida.starts_at == nueva
        assert sessions.find_by_id(sesion.id) is not None
        encontrada = sessions.find_by_id(sesion.id)
        assert encontrada is not None
        assert encontrada.starts_at == nueva

    def test_lo_que_no_se_envia_no_se_toca(
        self, sessions: InMemoryExamSessionRepository, sesion: ExamSession
    ) -> None:
        corregida = UpdateExamSession(sessions).execute(
            sesion.id, ExamSessionChanges(title="Otro titulo"), actor=DOCENTE
        )

        assert corregida.title == "Otro titulo"
        assert corregida.duration_minutes == sesion.duration_minutes
        assert corregida.starts_at == sesion.starts_at
        assert corregida.preset is sesion.preset

    def test_el_codigo_de_acceso_no_cambia(
        self, sessions: InMemoryExamSessionRepository, sesion: ExamSession
    ) -> None:
        """Si cambiara, los estudiantes que ya lo tienen apuntado se quedan fuera."""
        corregida = UpdateExamSession(sessions).execute(
            sesion.id, ExamSessionChanges(duration_minutes=120), actor=DOCENTE
        )

        assert corregida.access_code == sesion.access_code

    def test_el_id_no_cambia(
        self, sessions: InMemoryExamSessionRepository, sesion: ExamSession
    ) -> None:
        """Un id nuevo dejaría huérfanos los eventos y las respuestas."""
        corregida = UpdateExamSession(sessions).execute(
            sesion.id, ExamSessionChanges(title="Otro"), actor=DOCENTE
        )

        assert corregida.id == sesion.id

    def test_se_pone_la_nota_sobre_veinte(
        self, sessions: InMemoryExamSessionRepository, sesion: ExamSession
    ) -> None:
        corregida = UpdateExamSession(sessions).execute(
            sesion.id, ExamSessionChanges(max_score=Decimal(20)), actor=DOCENTE
        )

        assert corregida.max_score == Decimal(20)

    def test_editar_revalida(
        self, sessions: InMemoryExamSessionRepository, sesion: ExamSession
    ) -> None:
        """Si editar saltara las validaciones, se llegaría por la puerta de atrás
        a un examen que `create` nunca habría aceptado."""
        with pytest.raises(InvalidExamSessionError):
            UpdateExamSession(sessions).execute(
                sesion.id, ExamSessionChanges(duration_minutes=0), actor=DOCENTE
            )

    def test_una_nota_maxima_de_cero_se_rechaza(
        self, sessions: InMemoryExamSessionRepository, sesion: ExamSession
    ) -> None:
        """Dividir por el máximo es como se pasa de puntos a nota."""
        with pytest.raises(InvalidExamSessionError, match="mayor que cero"):
            UpdateExamSession(sessions).execute(
                sesion.id, ExamSessionChanges(max_score=Decimal(0)), actor=DOCENTE
            )

    def test_cambiar_de_preset_trae_los_modulos_del_nuevo(
        self, sessions: InMemoryExamSessionRepository, sesion: ExamSession
    ) -> None:
        corregida = UpdateExamSession(sessions).execute(
            sesion.id, ExamSessionChanges(preset=SupervisionPreset.BASIC), actor=DOCENTE
        )

        assert corregida.preset is SupervisionPreset.BASIC
        assert len(corregida.modules) < len(sesion.modules)

    def test_se_puede_vaciar_la_descripcion(self, sessions: InMemoryExamSessionRepository) -> None:
        """Con solo `None` no habría forma: `None` ya significa "no lo cambies"."""
        creada = ExamSession.create(
            teacher_id=DOCENTE.id,
            title="Con indicaciones",
            starts_at=NOW,
            duration_minutes=60,
            description="Trae calculadora",
        )
        sessions.save(creada)

        corregida = UpdateExamSession(sessions).execute(
            creada.id, ExamSessionChanges(clear_description=True), actor=DOCENTE
        )

        assert corregida.description is None

    def test_un_examen_ajeno_no_se_edita(
        self, sessions: InMemoryExamSessionRepository, sesion: ExamSession
    ) -> None:
        with pytest.raises(AuthorizationError):
            UpdateExamSession(sessions).execute(
                sesion.id, ExamSessionChanges(title="Secuestrado"), actor=OTRO_DOCENTE
            )

    def test_un_examen_inexistente_responde_igual_que_uno_ajeno(
        self, sessions: InMemoryExamSessionRepository, sesion: ExamSession
    ) -> None:
        inexistente = uuid4()

        with pytest.raises(AuthorizationError) as ajeno:
            UpdateExamSession(sessions).execute(
                sesion.id, ExamSessionChanges(title="x"), actor=OTRO_DOCENTE
            )
        with pytest.raises(AuthorizationError) as no_existe:
            UpdateExamSession(sessions).execute(
                inexistente, ExamSessionChanges(title="x"), actor=OTRO_DOCENTE
            )

        assert str(ajeno.value) == str(no_existe.value)

    def test_un_estudiante_no_edita_examenes(
        self, sessions: InMemoryExamSessionRepository, sesion: ExamSession
    ) -> None:
        with pytest.raises(AuthorizationError, match="Solo un docente"):
            UpdateExamSession(sessions).execute(
                sesion.id, ExamSessionChanges(title="Mio"), actor=ANA
            )


class TestConEstudiantesDentro:
    def test_no_se_cambia_la_nota_maxima(
        self,
        sessions: InMemoryExamSessionRepository,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
    ) -> None:
        """Dejaría a unos calificados con una regla y a otros con otra."""
        con_un_estudiante(participants, sesion)

        with pytest.raises(ExamInUseError, match="nota maxima"):
            UpdateExamSession(sessions, participants).execute(
                sesion.id, ExamSessionChanges(max_score=Decimal(10)), actor=DOCENTE
            )

    def test_tampoco_cuantas_preguntas_tocan(
        self,
        sessions: InMemoryExamSessionRepository,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
    ) -> None:
        con_un_estudiante(participants, sesion)

        with pytest.raises(ExamInUseError):
            UpdateExamSession(sessions, participants).execute(
                sesion.id, ExamSessionChanges(question_pool_size=5), actor=DOCENTE
            )

    def test_la_duracion_si_se_puede_alargar(
        self,
        sessions: InMemoryExamSessionRepository,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
    ) -> None:
        """Alargar el examen a mitad es exactamente lo que un docente necesita
        cuando hay un corte de luz."""
        con_un_estudiante(participants, sesion)

        corregida = UpdateExamSession(sessions, participants).execute(
            sesion.id, ExamSessionChanges(duration_minutes=120), actor=DOCENTE
        )

        assert corregida.duration_minutes == 120

    def test_el_titulo_y_las_indicaciones_tambien(
        self,
        sessions: InMemoryExamSessionRepository,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
    ) -> None:
        con_un_estudiante(participants, sesion)

        corregida = UpdateExamSession(sessions, participants).execute(
            sesion.id,
            ExamSessionChanges(title="Parcial — corregido", description="Sin calculadora"),
            actor=DOCENTE,
        )

        assert corregida.title == "Parcial — corregido"
        assert corregida.description == "Sin calculadora"


class TestCancelar:
    def test_cancelar_no_borra_la_sesion(
        self,
        sessions: InMemoryExamSessionRepository,
        sesion: ExamSession,
        clock: FixedClock,
    ) -> None:
        cancelada = CancelExamSession(sessions, clock).execute(sesion.id, actor=DOCENTE)

        assert cancelada.status is SessionStatus.CANCELLED
        assert cancelada.cancelled_at == NOW
        assert sessions.find_by_id(sesion.id) is not None

    def test_un_examen_cancelado_no_acepta_a_nadie(
        self,
        sessions: InMemoryExamSessionRepository,
        sesion: ExamSession,
        clock: FixedClock,
    ) -> None:
        cancelada = CancelExamSession(sessions, clock).execute(sesion.id, actor=DOCENTE)

        # Y el estado lo dice, en vez de parecerse a "todavia no empieza".
        assert cancelada.entry_state_at(sesion.starts_at) is EntryState.CANCELLED
        assert not cancelada.accepts_entry_at(sesion.starts_at)

    def test_cancelado_manda_sobre_el_reloj(
        self,
        sessions: InMemoryExamSessionRepository,
        sesion: ExamSession,
        clock: FixedClock,
    ) -> None:
        """A cualquier hora: antes, durante y después de la ventana."""
        cancelada = CancelExamSession(sessions, clock).execute(sesion.id, actor=DOCENTE)

        for momento in (
            sesion.starts_at - timedelta(days=1),
            sesion.starts_at + timedelta(minutes=1),
            sesion.ends_at + timedelta(days=1),
        ):
            assert cancelada.entry_state_at(momento) is EntryState.CANCELLED

    def test_cancelar_dos_veces_no_mueve_la_fecha(
        self,
        sessions: InMemoryExamSessionRepository,
        sesion: ExamSession,
        clock: FixedClock,
    ) -> None:
        """Perdería cuándo se decidió de verdad."""
        CancelExamSession(sessions, clock).execute(sesion.id, actor=DOCENTE)

        with pytest.raises(InvalidExamSessionError, match="ya estaba cancelado"):
            CancelExamSession(sessions, clock).execute(sesion.id, actor=DOCENTE)

    def test_un_examen_cancelado_ya_no_se_edita(
        self,
        sessions: InMemoryExamSessionRepository,
        sesion: ExamSession,
        clock: FixedClock,
    ) -> None:
        CancelExamSession(sessions, clock).execute(sesion.id, actor=DOCENTE)

        with pytest.raises(InvalidExamSessionError, match="cancelado"):
            UpdateExamSession(sessions).execute(
                sesion.id, ExamSessionChanges(title="Resucitado"), actor=DOCENTE
            )

    def test_no_se_cancela_el_examen_de_otro(
        self,
        sessions: InMemoryExamSessionRepository,
        sesion: ExamSession,
        clock: FixedClock,
    ) -> None:
        with pytest.raises(AuthorizationError):
            CancelExamSession(sessions, clock).execute(sesion.id, actor=OTRO_DOCENTE)


class TestBorrar:
    def test_un_examen_sin_estudiantes_se_borra(
        self,
        sessions: InMemoryExamSessionRepository,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
    ) -> None:
        """El caso real: lo acaba de crear con la fecha mal."""
        DeleteExamSession(sessions, participants).execute(sesion.id, actor=DOCENTE)

        assert sessions.find_by_id(sesion.id) is None

    def test_con_estudiantes_no_se_borra(
        self,
        sessions: InMemoryExamSessionRepository,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
    ) -> None:
        """Borrarlo se llevaría sus eventos, alertas y respuestas: la evidencia."""
        con_un_estudiante(participants, sesion)

        with pytest.raises(ExamInUseError, match="cancelalo"):
            DeleteExamSession(sessions, participants).execute(sesion.id, actor=DOCENTE)

        assert sessions.find_by_id(sesion.id) is not None

    def test_no_se_borra_el_examen_de_otro(
        self,
        sessions: InMemoryExamSessionRepository,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
    ) -> None:
        with pytest.raises(AuthorizationError):
            DeleteExamSession(sessions, participants).execute(sesion.id, actor=OTRO_DOCENTE)

        assert sessions.find_by_id(sesion.id) is not None

    def test_un_estudiante_no_borra_examenes(
        self,
        sessions: InMemoryExamSessionRepository,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
    ) -> None:
        with pytest.raises(AuthorizationError, match="Solo un docente"):
            DeleteExamSession(sessions, participants).execute(sesion.id, actor=ANA)

    def test_borrar_uno_inexistente_responde_como_uno_ajeno(
        self,
        sessions: InMemoryExamSessionRepository,
        participants: InMemoryParticipantRepository,
        sesion: ExamSession,
    ) -> None:
        with pytest.raises(AuthorizationError):
            DeleteExamSession(sessions, participants).execute(uuid4(), actor=OTRO_DOCENTE)
