"""Puerto de matrícula de estudiantes en una sesión de examen."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from proctoring_api.domain.participant import SessionParticipant


class ParticipantRepository(Protocol):
    """Guarda y recupera quién está matriculado en cada examen.

    `find` es la consulta más caliente del sistema: se hace en cada lectura de
    preguntas y en cada entrega, así que quien lo implemente debería cachear o
    apoyarse en el índice `(session_id, student_id, attempt)`.
    """

    def save(self, participant: SessionParticipant) -> None:
        """Crea o actualiza la matrícula."""
        ...

    def find(self, session_id: UUID, student_id: UUID) -> SessionParticipant | None:
        """La matrícula de ese estudiante en esa sesión, o `None` si no existe."""
        ...

    def list_by_student(self, student_id: UUID) -> Sequence[SessionParticipant]:
        """Todas las matriculas de un estudiante, en cualquier sesion.

        Es el panel del estudiante: a que examenes entro y en que estado esta
        cada uno.
        """
        ...

    def list_by_session(self, session_id: UUID) -> Sequence[SessionParticipant]:
        """Participantes de una sesión. Es la sala de espera del docente."""
        ...
