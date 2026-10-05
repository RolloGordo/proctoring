"""La decisión del docente sobre un caso.

Es la pieza que distingue a este sistema de un vigilante automático: el sistema
**audita** —calcula un riesgo, reúne la evidencia— y quien **decide** es el
docente, con una justificación escrita. Nada aquí anula un examen por su cuenta.

La justificación no es un trámite: es lo que le da sentido a la decisión cuando
alguien, meses después, pregunta por qué se tomó. Por eso es obligatoria y tiene
un mínimo, igual que la restricción `CHECK` de la tabla `decisions`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from proctoring_api.domain.errors import DomainError

#: Mismo mínimo que `decisions.justification` en la base. Una justificación de
#: tres letras no justifica nada.
MIN_JUSTIFICATION_LENGTH = 10
MAX_JUSTIFICATION_LENGTH = 2000


class InvalidDecisionError(DomainError):
    """La decisión no cumple las reglas del dominio."""


class DecisionType(StrEnum):
    """Mismos valores que el enum `decision_type` de PostgreSQL."""

    #: El docente revisó la evidencia y confirma que hubo una infracción.
    CONFIRMED = "confirmed"
    #: El docente revisó la evidencia y concluye que no hubo infracción: las
    #: señales tenían otra explicación. Es tan legítimo como el anterior, y el
    #: sistema no debe empujar hacia ninguno.
    DISMISSED = "dismissed"
    #: No se confirma ni se descarta: se le da al estudiante otra oportunidad.
    RETAKE = "retake"


@dataclass(frozen=True, slots=True)
class Decision:
    """Una decisión registrada. Es evidencia: no se edita ni se borra.

    Si el docente cambia de parecer, se registra **otra** decisión. El historial
    completo es lo que se puede auditar.
    """

    id: UUID
    session_id: UUID
    student_id: UUID
    teacher_id: UUID
    decision: DecisionType
    justification: str
    decided_at: datetime

    @classmethod
    def create(
        cls,
        *,
        session_id: UUID,
        student_id: UUID,
        teacher_id: UUID,
        decision: DecisionType,
        justification: str,
        decided_at: datetime,
        decision_id: UUID | None = None,
    ) -> Decision:
        """Crea una decisión validada.

        Raises:
            InvalidDecisionError: si la justificación es demasiado corta o larga,
                o si la fecha no trae zona horaria.
        """
        clean = justification.strip()
        if len(clean) < MIN_JUSTIFICATION_LENGTH:
            raise InvalidDecisionError(
                f"La justificacion debe tener al menos {MIN_JUSTIFICATION_LENGTH} caracteres: "
                "explica por que decides asi."
            )
        if len(clean) > MAX_JUSTIFICATION_LENGTH:
            raise InvalidDecisionError(
                f"La justificacion supera los {MAX_JUSTIFICATION_LENGTH} caracteres"
            )
        if decided_at.tzinfo is None or decided_at.utcoffset() is None:
            raise InvalidDecisionError("decided_at debe traer zona horaria")

        return cls(
            id=decision_id if decision_id is not None else uuid4(),
            session_id=session_id,
            student_id=student_id,
            teacher_id=teacher_id,
            decision=decision,
            justification=clean,
            decided_at=decided_at,
        )
