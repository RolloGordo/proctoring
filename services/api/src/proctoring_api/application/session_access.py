"""Regla de acceso a una sesion de examen.

Vive aparte porque la comparten los casos de uso que leen datos de una sesion
(eventos y alertas), y duplicarla seria la forma mas facil de que uno de los dos
se quede sin ella.
"""

from __future__ import annotations

from uuid import UUID

from proctoring_api.application.ports.session_repository import SessionRepository
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.user import AuthenticatedUser


def ensure_teacher_owns_session(
    sessions: SessionRepository | None,
    session_id: UUID,
    actor: AuthenticatedUser | None,
) -> None:
    """Un docente solo accede a las sesiones que el creo.

    Sin esto, cualquier docente del sistema puede leer la evidencia y las alertas
    de los examenes de sus colegas con solo conocer un `session_id`. Es
    informacion sobre estudiantes concretos y sobre decisiones academicas ajenas.

    No aplica a estudiantes: a ellos los limita el filtro por su propio id.

    `sessions` es `None` cuando no hay con que comprobar (modo memoria en
    desarrollo), igual que ocurre con el banco de preguntas. `actor` es `None`
    con la autenticacion desactivada.

    Raises:
        AuthorizationError: si el docente no es dueno de la sesion, o si la
            sesion no existe. Se responde lo mismo en ambos casos a proposito:
            distinguirlos permitiria averiguar que sesiones existen.
    """
    if actor is None or sessions is None or not actor.is_teacher:
        return

    owner_id = sessions.find_teacher_id(session_id)
    if owner_id != actor.id:
        raise AuthorizationError("No tienes acceso a esta sesion de examen")
