"""Banco de preguntas: preguntas que viven fuera de un examen concreto.

Antes una pregunta pertenecía a **un** examen, así que el docente las reescribía
en cada uno. Un banco es un conjunto de preguntas del docente del que un examen
**extrae**.

El banco es del docente y el curso es **opcional**: puede tener uno general y
usarlo en varios cursos, o uno atado a un curso concreto.

## El sorteo

Un examen con 100 preguntas en su banco y `question_pool_size = 20` le da 20 a
cada estudiante. **El sorteo tiene que ser determinista por estudiante**: si
recarga la página a mitad del examen, tiene que recibir exactamente las mismas 20
y en el mismo orden. Si no, pierde lo respondido y, peor, podría ver preguntas
nuevas que no ha respondido.

Por eso no se usa `random` sin semilla: la semilla sale del participante y de la
sesión. Es reproducible, no hay que guardar qué le tocó a cada uno, y dos
estudiantes distintos reciben conjuntos distintos.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from proctoring_api.domain.errors import DomainError
from proctoring_api.domain.question import Question

MAX_NAME_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 1000


class InvalidQuestionBankError(DomainError):
    """El banco no cumple las reglas del dominio."""


@dataclass(frozen=True, slots=True)
class QuestionBank:
    """Un conjunto de preguntas reutilizable."""

    id: UUID
    teacher_id: UUID
    #: Opcional: un banco sin curso sirve para todos los del docente.
    course_id: UUID | None
    name: str
    description: str | None
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        teacher_id: UUID,
        name: str,
        created_at: datetime,
        course_id: UUID | None = None,
        description: str | None = None,
        bank_id: UUID | None = None,
    ) -> QuestionBank:
        """Crea un banco validado.

        Raises:
            InvalidQuestionBankError: si el nombre está vacío o es demasiado
                largo, o si la fecha no trae zona horaria.
        """
        limpio = " ".join(name.split())
        if not limpio:
            raise InvalidQuestionBankError("El banco necesita un nombre")
        if len(limpio) > MAX_NAME_LENGTH:
            raise InvalidQuestionBankError(f"El nombre supera los {MAX_NAME_LENGTH} caracteres")

        descripcion = (description or "").strip() or None
        if descripcion is not None and len(descripcion) > MAX_DESCRIPTION_LENGTH:
            raise InvalidQuestionBankError(
                f"La descripcion supera los {MAX_DESCRIPTION_LENGTH} caracteres"
            )

        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise InvalidQuestionBankError("created_at debe traer zona horaria")

        return cls(
            id=bank_id if bank_id is not None else uuid4(),
            teacher_id=teacher_id,
            course_id=course_id,
            name=limpio,
            description=descripcion,
            created_at=created_at,
        )


def _semilla(session_id: UUID, participant_id: UUID) -> int:
    """Semilla estable para un estudiante en un examen.

    Se usa un hash y no `hash()` de Python: `hash()` cambia entre ejecuciones por
    la aleatorización de PYTHONHASHSEED, y entonces recargar la página daría otro
    examen.
    """
    material = f"{session_id}:{participant_id}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def draw_questions(
    questions: Sequence[Question],
    *,
    session_id: UUID,
    participant_id: UUID,
    pool_size: int | None = None,
    shuffle: bool = False,
) -> list[Question]:
    """Las preguntas que le tocan a un estudiante, siempre las mismas.

    - `pool_size` es cuántas recibe. `None` o mayor que las disponibles significa
      "todas": un examen nunca se queda corto por pedir más de las que hay.
    - `shuffle` cambia el **orden**; sin él se respeta el de `position`.

    Dos estudiantes distintos reciben, en general, conjuntos distintos. El mismo
    estudiante recibe siempre lo mismo, aunque recargue o se le reinicie el
    equipo.
    """
    ordenadas = sorted(questions, key=lambda q: (q.position, str(q.id)))
    if not ordenadas:
        return []

    aleatorio = random.Random(_semilla(session_id, participant_id))

    elegidas = ordenadas
    if pool_size is not None and 0 < pool_size < len(ordenadas):
        elegidas = aleatorio.sample(ordenadas, pool_size)
        # Tras el sorteo se vuelve al orden original: barajar es otra decisión
        # (`shuffle_questions`) y el docente puede querer una sin la otra.
        elegidas = sorted(elegidas, key=lambda q: (q.position, str(q.id)))

    if shuffle:
        # Una copia: `shuffle` muta la lista y `elegidas` puede ser `ordenadas`.
        elegidas = list(elegidas)
        aleatorio.shuffle(elegidas)

    return list(elegidas)
