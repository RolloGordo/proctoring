"""Que lo que un adaptador de Supabase escribe, también lo lea.

Nació de un error real: se añadieron `is_correct` y `points_awarded` al escribir una
respuesta, pero no a la lista de columnas que se piden al leerla. Las pruebas en
memoria pasaban porque no usan esa lista, y en la base real la corrección se perdía
sin ningún error: se guardaba y volvía como `None`.

No sustituye probar contra la base de verdad, pero atrapa este tipo de olvido sin
necesitar red. Y cubre **todos** los adaptadores a la vez: si alguien añade uno
nuevo con `_to_row` y se olvida de probarlo,
`test_ningun_adaptador_se_queda_sin_probar` se pone rojo.
"""

from __future__ import annotations

import importlib
import pkgutil
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import ModuleType
from uuid import uuid4

import pytest

from proctoring_api.adapters.outbound import supabase as supabase_package
from proctoring_api.adapters.outbound.supabase import (
    alert_repository,
    answer_repository,
    audio_analysis_repository,
    decision_repository,
    event_repository,
    exam_session_repository,
    participant_repository,
    question_bank_repository,
    reference_face_repository,
)
from proctoring_api.application.ports.reference_face_repository import ReferenceFace
from proctoring_api.domain.alert import Alert
from proctoring_api.domain.answer import Answer
from proctoring_api.domain.audio_analysis import AudioAnalysis
from proctoring_api.domain.decision import Decision, DecisionType
from proctoring_api.domain.event import EventType, ProctoringEvent
from proctoring_api.domain.exam_session import ExamSession, SupervisionPreset
from proctoring_api.domain.participant import SessionParticipant
from proctoring_api.domain.question_bank import QuestionBank
from proctoring_api.domain.severity import Severity

NOW = datetime(2026, 10, 5, 15, 0, tzinfo=UTC)

#: El examen sale aparte porque dos pruebas lo miran de cerca, y con el tipo
#: puesto en vez de `object`.
EXAMEN = ExamSession.create(
    teacher_id=uuid4(),
    title="Parcial de bases de datos",
    starts_at=NOW,
    duration_minutes=90,
    access_code="ABC123",
    course_id=uuid4(),
    description="Unidades 1 a 4",
    preset=SupervisionPreset.STRICT,
    question_pool_size=20,
)

#: Un ejemplo por adaptador, con **todos** los campos opcionales puestos: un
#: campo dejado en `None` no aparecería en la fila y el olvido pasaría de largo.
EJEMPLOS: dict[ModuleType, object] = {
    answer_repository: Answer(
        id=uuid4(),
        participant_id=uuid4(),
        question_id=uuid4(),
        answered_at=NOW,
        selected_option_id=uuid4(),
        text_answer="x",
        numeric_answer=Decimal(1),
        is_correct=True,
        points_awarded=Decimal(2),
    ),
    participant_repository: SessionParticipant.enroll(
        session_id=uuid4(), student_id=uuid4(), consented_at=NOW
    )
    .verified(NOW)
    .with_score(3.0),
    decision_repository: Decision.create(
        session_id=uuid4(),
        student_id=uuid4(),
        teacher_id=uuid4(),
        decision=DecisionType.RETAKE,
        justification="Hubo un corte de energia a mitad del examen.",
        decided_at=NOW,
    ),
    alert_repository: Alert(
        id=uuid4(),
        event_id=uuid4(),
        session_id=uuid4(),
        student_id=uuid4(),
        severity=Severity.HIGH,
        reason="Consulta a un asistente de IA por voz",
        created_at=NOW,
    ),
    event_repository: ProctoringEvent.create(
        session_id=uuid4(),
        student_id=uuid4(),
        event_type=EventType.FOCUS_LOST,
        started_at=NOW,
        question_id=uuid4(),
        duration_ms=1200,
        metadata={"veces": 2},
        evidence_path="evidences/una.jpg",
    ),
    audio_analysis_repository: AudioAnalysis(
        id=uuid4(),
        event_id=uuid4(),
        transcript="como se calcula la mediana",
        similarity=0.91,
        synthetic_voice_score=0.88,
        matched_question_id=uuid4(),
        processing_ms=2400,
        model_versions={"whisper": "large-v3", "similitud": "paraphrase-multilingual"},
        processed_at=NOW,
    ),
    reference_face_repository: ReferenceFace(
        student_id=uuid4(),
        storage_path="reference-faces/uno.jpg",
        embedding=[0.1, 0.2, 0.3],
        model_version="arcface-r100",
        registered_at=NOW,
    ),
    exam_session_repository: EXAMEN,
    question_bank_repository: QuestionBank.create(
        teacher_id=uuid4(),
        name="Banco de SQL",
        course_id=uuid4(),
        description="Preguntas de los ultimos tres ciclos",
        created_at=NOW,
    ),
}


def columnas(texto: str) -> set[str]:
    return {c.strip() for c in texto.split(",")}


def adaptadores_con_to_row() -> list[str]:
    """Los módulos del paquete de Supabase que escriben filas."""
    nombres = []
    for info in pkgutil.iter_modules(supabase_package.__path__):
        modulo = importlib.import_module(f"{supabase_package.__name__}.{info.name}")
        if hasattr(modulo, "_to_row"):
            nombres.append(info.name)
    return sorted(nombres)


@pytest.mark.parametrize(
    "modulo", list(EJEMPLOS), ids=lambda m: str(m.__name__).rsplit(".", maxsplit=1)[-1]
)
def test_lee_todo_lo_que_escribe(modulo: ModuleType) -> None:
    entidad = EJEMPLOS[modulo]

    escritas = set(modulo._to_row(entidad))
    leidas = columnas(modulo.COLUMNS)

    assert escritas <= leidas, f"Columnas que se escriben pero no se leen: {escritas - leidas}"


def test_ningun_adaptador_se_queda_sin_probar() -> None:
    """Un adaptador nuevo sin ejemplo aquí no estaría probado y nadie lo notaría."""
    probados = {str(m.__name__).rsplit(".", maxsplit=1)[-1] for m in EJEMPLOS}

    assert set(adaptadores_con_to_row()) == probados


def test_el_ejemplo_del_examen_trae_los_campos_opcionales() -> None:
    """Con un ejemplo a medias, olvidar una columna opcional pasaría de largo.

    `question_pool_size` es el caso concreto: se añadió a la escritura y a la
    lectura al mismo tiempo, y esta prueba es la que lo sostiene.
    """
    fila = exam_session_repository._to_row(EXAMEN)

    assert fila["question_pool_size"] == 20
    assert fila["access_code"] == "ABC123"
    assert None not in fila.values()


def test_atrapa_una_columna_escrita_y_no_leida() -> None:
    """La prueba de arriba solo sirve si falla cuando debe."""

    class Falso:
        COLUMNS = "id, nombre"

        @staticmethod
        def _to_row(_: object) -> dict[str, object]:
            return {"id": "1", "nombre": "x", "olvidada": True}

    escritas = set(Falso._to_row(None))

    assert not escritas <= columnas(Falso.COLUMNS)
    assert escritas - columnas(Falso.COLUMNS) == {"olvidada"}


def test_las_sesiones_leen_los_modulos_aparte() -> None:
    """`session_modules` es otra tabla: sus columnas no están en `COLUMNS`.

    Se deja escrito para que nadie intente "arreglar" la ausencia metiéndolas ahí.
    """
    fila = exam_session_repository._to_row(EXAMEN)

    assert "modules" not in fila
    assert "preset" in fila


def test_una_decision_vieja_y_una_nueva_escriben_lo_mismo() -> None:
    """Dos decisiones distintas no pueden diferir en qué columnas escriben: si lo
    hicieran, el olvido aparecería solo con unos datos y no con otros."""
    primera = Decision.create(
        session_id=uuid4(),
        student_id=uuid4(),
        teacher_id=uuid4(),
        decision=DecisionType.CONFIRMED,
        justification="Se confirmo la consulta por voz.",
        decided_at=NOW,
    )
    segunda = Decision.create(
        session_id=uuid4(),
        student_id=uuid4(),
        teacher_id=uuid4(),
        decision=DecisionType.DISMISSED,
        justification="La alerta fue un falso positivo.",
        decided_at=NOW + timedelta(hours=1),
    )

    assert set(decision_repository._to_row(primera)) == set(decision_repository._to_row(segunda))
