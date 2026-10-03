"""Matrícula de un estudiante en una sesión de examen.

Una fila en `session_participants` significa que el estudiante **entró** al
examen: aceptó que se le supervise y el sistema lo reconoce como participante.
Sin esa fila no puede recibir las preguntas, por mucho que conozca el id de la
sesión.

El consentimiento no es un trámite. El sistema observa cámara, micrófono,
pantalla y procesos de una persona; que esa persona sepa qué se observa y lo
acepte antes de empezar es la diferencia entre supervisar y espiar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from proctoring_api.domain.errors import DomainError


class InvalidEnrollmentError(DomainError):
    """La matrícula no cumple las reglas del dominio."""


class VerificationStatus(StrEnum):
    """Mismos valores que el enum `verification_status` de PostgreSQL."""

    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    #: El docente lo admitió a mano tras una verificación fallida. Existe porque
    #: un reconocimiento facial que falla no puede costarle el examen a nadie:
    #: la última palabra es del docente.
    MANUALLY_APPROVED = "manually_approved"
    REJECTED = "rejected"


#: Estados que permiten rendir el examen.
CAN_TAKE_EXAM = frozenset({VerificationStatus.VERIFIED, VerificationStatus.MANUALLY_APPROVED})


@dataclass(frozen=True, slots=True)
class SessionParticipant:
    """Un estudiante dentro de una sesión de examen."""

    id: UUID
    session_id: UUID
    student_id: UUID
    attempt: int
    verification_status: VerificationStatus
    consent_at: datetime | None
    verified_at: datetime | None = None
    verification_reviewed_by: UUID | None = None
    requested_in_person: bool = False
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    score: float | None = None

    @classmethod
    def enroll(
        cls,
        *,
        session_id: UUID,
        student_id: UUID,
        consented_at: datetime,
        attempt: int = 1,
        participant_id: UUID | None = None,
    ) -> SessionParticipant:
        """Matricula a un estudiante que acaba de aceptar la supervisión.

        `consented_at` es obligatorio: no existe una matrícula sin consentimiento.
        Hacerlo opcional dejaría que alguien creara participantes sin él.

        Raises:
            InvalidEnrollmentError: si el intento no es válido o la fecha de
                consentimiento no trae zona horaria.
        """
        if attempt <= 0:
            raise InvalidEnrollmentError("El numero de intento debe ser mayor que cero")
        if consented_at.tzinfo is None or consented_at.utcoffset() is None:
            raise InvalidEnrollmentError("consented_at debe traer zona horaria")

        return cls(
            id=participant_id if participant_id is not None else uuid4(),
            session_id=session_id,
            student_id=student_id,
            attempt=attempt,
            # Entra pendiente de verificar: la verificación facial es el paso
            # siguiente, y hasta que ocurra no debería ver las preguntas.
            verification_status=VerificationStatus.PENDING,
            consent_at=consented_at,
        )

    @property
    def has_consented(self) -> bool:
        return self.consent_at is not None

    @property
    def can_take_exam(self) -> bool:
        """Si puede recibir las preguntas y responder.

        Hace falta consentimiento, identidad resuelta y no haber entregado ya.
        """
        return (
            self.has_consented
            and self.verification_status in CAN_TAKE_EXAM
            and self.submitted_at is None
        )

    @property
    def has_submitted(self) -> bool:
        return self.submitted_at is not None

    def verified(self, moment: datetime) -> SessionParticipant:
        """Marca la identidad como verificada por el sistema."""
        return self._replace(verification_status=VerificationStatus.VERIFIED, verified_at=moment)

    def approved_by_teacher(self, teacher_id: UUID, moment: datetime) -> SessionParticipant:
        """El docente lo admite a mano tras una verificación fallida.

        Queda registrado quién lo admitió: es una decisión con consecuencias y
        tiene que tener un responsable.
        """
        return self._replace(
            verification_status=VerificationStatus.MANUALLY_APPROVED,
            verified_at=moment,
            verification_reviewed_by=teacher_id,
        )

    def verification_failed(self) -> SessionParticipant:
        """La verificación no pasó. **No lo expulsa**: lo deja a la espera.

        Un reconocimiento facial que falla con mala luz no puede costarle el
        examen a nadie. El docente decide.
        """
        return self._replace(verification_status=VerificationStatus.FAILED)

    def started(self, moment: datetime) -> SessionParticipant:
        if self.started_at is not None:
            return self
        return self._replace(started_at=moment)

    def submitted(self, moment: datetime) -> SessionParticipant:
        """Entrega el examen.

        Raises:
            InvalidEnrollmentError: si ya lo había entregado. Reenviar
                sobrescribiría la hora de entrega, que es parte de la evidencia.
        """
        if self.submitted_at is not None:
            raise InvalidEnrollmentError("Este examen ya fue entregado")
        return self._replace(submitted_at=moment)

    def _replace(self, **cambios: object) -> SessionParticipant:
        from dataclasses import replace

        return replace(self, **cambios)  # type: ignore[arg-type]
