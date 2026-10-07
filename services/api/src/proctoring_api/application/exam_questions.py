"""Qué preguntas le tocan a un estudiante en un examen.

Vive aquí y no dentro de un caso de uso porque lo necesitan **dos**: el que le
entrega el examen al estudiante y el que lo califica al entregarlo. Si cada uno
tuviera su copia y se separaran, se calificaría a alguien por preguntas que
nunca llegó a ver. Que el sorteo sea determinista es lo que permite que el
segundo reproduzca exactamente lo que mostró el primero, sin guardar nada.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from proctoring_api.application.ports.question_bank_repository import QuestionBankRepository
from proctoring_api.application.ports.question_repository import QuestionRepository
from proctoring_api.domain.exam_session import ExamSession
from proctoring_api.domain.question import Question
from proctoring_api.domain.question_bank import draw_questions


def questions_for(
    session: ExamSession,
    participant_id: UUID,
    questions: QuestionRepository,
    banks: QuestionBankRepository | None = None,
) -> Sequence[Question]:
    """Las preguntas de ese estudiante en ese examen.

    Sin bancos atados, las del propio examen y en su orden: es como funcionaba
    antes de que existieran los bancos, y los exámenes ya creados siguen igual.

    Con bancos, se sortean. La semilla es la **matrícula**, no el estudiante, así
    que un segundo intento del mismo examen trae otras preguntas.
    """
    atados = banks.list_session_banks(session.id) if banks is not None else []
    if not atados:
        return questions.list_by_session(session.id)

    disponibles = questions.list_by_banks([banco.id for banco in atados])
    return draw_questions(
        disponibles,
        session_id=session.id,
        participant_id=participant_id,
        pool_size=session.question_pool_size,
        shuffle=session.shuffle_questions,
    )
