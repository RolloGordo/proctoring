"""Matrícula, consentimiento y entrega del examen."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from proctoring_api.application.exam_questions import questions_for
from proctoring_api.application.ports.answer_repository import AnswerRepository
from proctoring_api.application.ports.clock import Clock
from proctoring_api.application.ports.exam_session_repository import ExamSessionRepository
from proctoring_api.application.ports.participant_repository import ParticipantRepository
from proctoring_api.application.ports.profile_repository import ProfileRepository
from proctoring_api.application.ports.question_bank_repository import QuestionBankRepository
from proctoring_api.application.ports.question_repository import QuestionRepository
from proctoring_api.application.session_access import ensure_teacher_owns_session
from proctoring_api.application.use_cases.create_exam_session import DEFAULT_DEV_TEACHER_ID
from proctoring_api.domain.errors import AuthorizationError, DomainError
from proctoring_api.domain.exam_session import DEFAULT_MAX_SCORE, EntryState, ExamSession
from proctoring_api.domain.grading import score_exam
from proctoring_api.domain.participant import InvalidEnrollmentError, SessionParticipant
from proctoring_api.domain.user import AuthenticatedUser, ProfileSummary

#: Estudiante ficticio por defecto cuando la autenticacion esta desactivada.
#:
#: Fijo y no aleatorio para que todas las matriculas de desarrollo sean del
#: mismo "estudiante" y el flujo se pueda recorrer entero.
DEFAULT_DEV_STUDENT_ID = UUID("00000000-0000-4000-8000-000000000002")


class ConsentRequiredError(DomainError):
    """No se puede entrar a un examen supervisado sin aceptar la supervisión."""


class ExamNotStartedError(DomainError):
    """El examen todavía no empieza.

    Separado de "el plazo cerró" a propósito: para quien espera son situaciones
    opuestas. A uno hay que decirle que vuelva en un rato; al otro, que hable con
    su docente. Responde 400, no 403: no es que no pueda, es que todavía no.
    """


class ExamCancelledError(DomainError):
    """El docente retiró el examen.

    También está separado, y por lo mismo: el estudiante que teclea su código y
    recibe "no hay ningún examen con ese código" se queda pensando que lo escribió
    mal y lo intenta diez veces. Lo que necesita saber es que el examen existía y
    ya no va a ocurrir.
    """


@dataclass(frozen=True, slots=True)
class EnrollmentResult:
    participant: SessionParticipant
    session: ExamSession


class EnrollInExam:
    """Matricula al estudiante que acepta la supervisión.

    Es el momento del **consentimiento**: a partir de aquí el sistema observa
    cámara, micrófono, pantalla y procesos. Que la persona sepa qué se observa y
    lo acepte antes de empezar es la diferencia entre supervisar y espiar, así
    que `accepts_supervision` no tiene valor por defecto.
    """

    def __init__(
        self,
        participants: ParticipantRepository,
        sessions: ExamSessionRepository,
        clock: Clock,
        dev_student_id: UUID = DEFAULT_DEV_STUDENT_ID,
    ) -> None:
        self._participants = participants
        self._sessions = sessions
        self._clock = clock
        self._dev_student_id = dev_student_id

    def execute(
        self,
        session_id: UUID,
        *,
        accepts_supervision: bool,
        actor: AuthenticatedUser | None = None,
        student_id: UUID | None = None,
    ) -> EnrollmentResult:
        """Matricula al estudiante, o devuelve su matrícula si ya existía.

        Raises:
            AuthorizationError: si lo pide un docente, si la sesión no existe o
                si la ventana de ingreso está cerrada.
            ConsentRequiredError: si no acepta la supervisión.
        """
        if actor is not None and actor.is_teacher:
            raise AuthorizationError("Un docente no se matricula en su propio examen")

        # Sin autenticacion no hay actor: se usa el estudiante de desarrollo,
        # que solo existe con ENV local o test.
        quien = actor.id if actor is not None else (student_id or self._dev_student_id)

        sesion = self._sessions.find_by_id(session_id)
        if sesion is None:
            raise AuthorizationError("No tienes acceso a este examen")

        ahora = self._clock.now()

        # Si ya estaba matriculado, volver a entrar no debe pedir el
        # consentimiento otra vez ni reiniciar nada: se le devuelve su estado.
        existente = self._participants.find(session_id, quien)
        if existente is not None:
            return EnrollmentResult(participant=existente, session=sesion)

        if not accepts_supervision:
            raise ConsentRequiredError(
                "Para rendir este examen tienes que aceptar la supervision. "
                "Puedes revisar que se observa antes de aceptar."
            )

        estado = sesion.entry_state_at(ahora)
        if estado is EntryState.CANCELLED:
            raise ExamCancelledError(
                "Tu docente cancelo este examen. No tienes que hacer nada; "
                "si no sabias nada, habla con el."
            )
        if estado is EntryState.NOT_STARTED:
            # Llegar antes de tiempo no es un error del estudiante: es lo normal.
            # Decirle "el plazo esta cerrado" era confundirlo con lo contrario.
            raise ExamNotStartedError(
                "Este examen todavia no empieza. Espera a la hora de inicio: "
                "esta pantalla te dejara entrar sola."
            )
        if estado is EntryState.CLOSED:
            raise AuthorizationError(
                "El plazo de ingreso a este examen esta cerrado. "
                "Habla con tu docente si crees que es un error."
            )

        participante = SessionParticipant.enroll(
            session_id=session_id, student_id=quien, consented_at=ahora
        )
        self._participants.save(participante)
        return EnrollmentResult(participant=participante, session=sesion)


class ListSessionParticipants:
    """Sala de espera del docente: quién llegó y en qué estado está."""

    def __init__(
        self,
        participants: ParticipantRepository,
        sessions: ExamSessionRepository | None = None,
    ) -> None:
        self._participants = participants
        self._sessions = sessions

    def execute(
        self, session_id: UUID, *, actor: AuthenticatedUser | None = None
    ) -> Sequence[SessionParticipant]:
        if actor is not None and not actor.is_teacher:
            # Un estudiante no ve quién más está rindiendo el examen.
            raise AuthorizationError("Solo el docente ve los participantes de una sesion")
        ensure_teacher_owns_session(self._sessions, session_id, actor)

        return self._participants.list_by_session(session_id)


@dataclass(frozen=True, slots=True)
class ParticipantEntry:
    """Un participante, con quien es."""

    participant: SessionParticipant
    #: `None` si la persona no tiene perfil. Se muestra igual: sigue siendo un
    #: participante de la sesion.
    profile: ProfileSummary | None


class ListSessionParticipantsWithNames:
    """La sala de espera del docente, con el nombre y el correo de cada estudiante.

    Un docente que admite a alguien tiene que ver **a quien** admite: los primeros
    ocho caracteres de un id no le dicen nada.
    """

    def __init__(
        self,
        participants: ParticipantRepository,
        sessions: ExamSessionRepository | None,
        profiles: ProfileRepository,
    ) -> None:
        self._listing = ListSessionParticipants(participants, sessions)
        self._profiles = profiles

    def execute(
        self, session_id: UUID, *, actor: AuthenticatedUser | None = None
    ) -> Sequence[ParticipantEntry]:
        participantes = self._listing.execute(session_id, actor=actor)
        # Nombres de todos en una consulta, no una por fila.
        perfiles = self._profiles.get_summaries([p.student_id for p in participantes])
        return [ParticipantEntry(p, perfiles.get(p.student_id)) for p in participantes]


class ReviewParticipantIdentity:
    """El docente admite a mano a quien no pasó la verificación facial.

    Existe porque un reconocimiento que falla con mala luz no puede costarle el
    examen a nadie. Queda registrado quién lo admitió.
    """

    def __init__(
        self,
        participants: ParticipantRepository,
        sessions: ExamSessionRepository | None,
        clock: Clock,
        dev_teacher_id: UUID = DEFAULT_DEV_TEACHER_ID,
    ) -> None:
        self._participants = participants
        self._sessions = sessions
        self._clock = clock
        self._dev_teacher_id = dev_teacher_id

    def execute(
        self,
        session_id: UUID,
        student_id: UUID,
        *,
        approve: bool,
        actor: AuthenticatedUser | None = None,
    ) -> SessionParticipant:
        if actor is not None and not actor.is_teacher:
            raise AuthorizationError("Solo el docente revisa la identidad de un estudiante")
        ensure_teacher_owns_session(self._sessions, session_id, actor)

        participante = self._participants.find(session_id, student_id)
        if participante is None:
            raise AuthorizationError("Ese estudiante no esta en esta sesion")

        # Sin autenticacion, el revisor es el docente de desarrollo. Antes se
        # guardaba aqui el `session_id`, que no es ninguna persona: dejaba una
        # pista de auditoria falsa —la columna existe para decir *quien* admitio—
        # y contra PostgreSQL rompia la clave ajena a `profiles`.
        revisor = actor.id if actor is not None else self._dev_teacher_id
        actualizado = (
            participante.approved_by_teacher(revisor, self._clock.now())
            if approve
            else participante.rejected_by_teacher(revisor)
        )
        self._participants.save(actualizado)
        return actualizado


class SubmitExam:
    """El estudiante entrega su examen, y se califica lo que se puede calificar."""

    def __init__(
        self,
        participants: ParticipantRepository,
        clock: Clock,
        dev_student_id: UUID = DEFAULT_DEV_STUDENT_ID,
        questions: QuestionRepository | None = None,
        answers: AnswerRepository | None = None,
        sessions: ExamSessionRepository | None = None,
        banks: QuestionBankRepository | None = None,
    ) -> None:
        self._participants = participants
        self._clock = clock
        self._dev_student_id = dev_student_id
        self._questions = questions
        self._answers = answers
        self._sessions = sessions
        self._banks = banks

    def execute(
        self,
        session_id: UUID,
        *,
        actor: AuthenticatedUser | None = None,
        student_id: UUID | None = None,
    ) -> SessionParticipant:
        """Marca la entrega y la califica.

        Raises:
            AuthorizationError: si no está matriculado.
            InvalidEnrollmentError: si ya había entregado. Reenviar
                sobrescribiría la hora de entrega, que es parte de la evidencia.
        """
        if actor is not None and actor.is_teacher:
            raise AuthorizationError("Un docente no entrega el examen de un estudiante")

        quien = actor.id if actor is not None else (student_id or self._dev_student_id)

        participante = self._participants.find(session_id, quien)
        if participante is None:
            raise AuthorizationError("No estas matriculado en este examen")

        entregado = participante.submitted(self._clock.now())
        entregado = self._grade(session_id, entregado)
        self._participants.save(entregado)
        return entregado

    def _grade(self, session_id: UUID, participante: SessionParticipant) -> SessionParticipant:
        """Califica lo que se corrige solo y guarda la correccion de cada respuesta.

        Se califica **antes** de guardar la entrega: si algo falla aqui, el
        estudiante no queda con el examen entregado y sin nota, sin poder
        reintentar porque reenviar se rechaza.
        """
        if self._questions is None or self._answers is None:
            return participante

        sesion = self._sessions.find_by_id(session_id) if self._sessions is not None else None
        # Las mismas preguntas que recibió, no las del examen: con bancos atados
        # el examen no tiene preguntas propias y calificar contra ellas daría
        # cero a todo el mundo.
        preguntas = (
            questions_for(sesion, participante.id, self._questions, self._banks)
            if sesion is not None
            else self._questions.list_by_session(session_id)
        )
        respuestas = self._answers.list_by_participant(participante.id)
        resultado = score_exam(preguntas, respuestas)

        self._answers.save_many(
            [
                respuesta.graded(
                    resultado.by_question[respuesta.question_id].is_correct,
                    resultado.by_question[respuesta.question_id].points,
                )
                for respuesta in respuestas
                if respuesta.question_id in resultado.by_question
            ]
        )
        # La nota va en la escala del examen (20 en Perú), no en puntos sueltos:
        # el docente pone los puntos que quiera a cada pregunta y el reparto lo
        # hace el sistema.
        escala = sesion.max_score if sesion is not None else DEFAULT_MAX_SCORE
        return participante.with_score(float(resultado.on_scale(escala)))


def ensure_can_take_exam(
    participants: ParticipantRepository | None,
    session_id: UUID,
    actor: AuthenticatedUser | None,
    fallback_student_id: UUID | None = None,
) -> None:
    """Comprueba que quien pide el examen esté matriculado y pueda rendirlo.

    **Esta es la comprobación que faltaba.** Sin ella, cualquier estudiante que
    conociera un `session_id` podía descargar las preguntas de un examen en el
    que no estaba matriculado, siempre que estuviera abierto.

    En modo sin autenticación se usa `fallback_student_id` (el estudiante de
    desarrollo). Así el flujo se comporta **igual** en local que en producción:
    si la comprobación solo existiera con autenticación activa, un fallo aquí no
    aparecería hasta el despliegue.

    `participants` es `None` solo cuando no hay con qué comprobar.

    Raises:
        AuthorizationError: si no está matriculado, si no consintió, si su
            identidad no está resuelta, o si ya entregó.
    """
    if participants is None:
        return

    quien = actor.id if actor is not None else fallback_student_id
    if quien is None:
        return

    participante = participants.find(session_id, quien)
    if participante is None:
        raise AuthorizationError(
            "No estas matriculado en este examen. Entra con el codigo de acceso."
        )

    if not participante.has_consented:
        raise ConsentRequiredError("Tienes que aceptar la supervision antes de empezar")

    if participante.has_submitted:
        raise AuthorizationError("Ya entregaste este examen")

    if not participante.can_take_exam:
        raise AuthorizationError(
            "Tu identidad todavia no esta verificada. Espera a que tu docente te admita."
        )


__all__ = [
    "DEFAULT_DEV_STUDENT_ID",
    "ConsentRequiredError",
    "EnrollInExam",
    "EnrollmentResult",
    "ExamNotStartedError",
    "InvalidEnrollmentError",
    "ListSessionParticipants",
    "ListSessionParticipantsWithNames",
    "ParticipantEntry",
    "ReviewParticipantIdentity",
    "SubmitExam",
    "ensure_can_take_exam",
]
