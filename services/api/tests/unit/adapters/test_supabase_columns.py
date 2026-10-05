"""Que lo que un adaptador de Supabase escribe, también lo lea.

Nació de un error real: se añadieron `is_correct` y `points_awarded` al escribir una
respuesta, pero no a la lista de columnas que se piden al leerla. Las pruebas en
memoria pasaban porque no usan esa lista, y en la base real la corrección se perdía
sin ningún error: se guardaba y volvía como `None`.

No sustituye probar contra la base de verdad, pero atrapa este tipo de olvido sin
necesitar red.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from proctoring_api.adapters.outbound.supabase import answer_repository, participant_repository
from proctoring_api.domain.answer import Answer
from proctoring_api.domain.participant import SessionParticipant

NOW = datetime(2026, 10, 5, 15, 0, tzinfo=UTC)


def columnas(texto: str) -> set[str]:
    return {c.strip() for c in texto.split(",")}


def test_las_respuestas_leen_todo_lo_que_escriben() -> None:
    respuesta = Answer(
        id=uuid4(),
        participant_id=uuid4(),
        question_id=uuid4(),
        answered_at=NOW,
        selected_option_id=uuid4(),
        text_answer="x",
        numeric_answer=Decimal(1),
        is_correct=True,
        points_awarded=Decimal(2),
    )

    escritas = set(answer_repository._to_row(respuesta))

    assert escritas <= columnas(answer_repository.COLUMNS), (
        "Columnas que se escriben pero no se leen: "
        f"{escritas - columnas(answer_repository.COLUMNS)}"
    )


def test_los_participantes_leen_todo_lo_que_escriben() -> None:
    participante = SessionParticipant.enroll(
        session_id=uuid4(), student_id=uuid4(), consented_at=NOW
    ).with_score(3.0)

    escritas = set(participant_repository._to_row(participante))

    assert escritas <= columnas(participant_repository.COLUMNS), (
        "Columnas que se escriben pero no se leen: "
        f"{escritas - columnas(participant_repository.COLUMNS)}"
    )
