"""Importar un archivo QTI a un banco de preguntas.

El docente sube el XML que exportó su plataforma y las preguntas caen en su
banco. Es lo que sustituye a escribirlas una por una, que es de donde salió todo
esto.

El análisis lo hace el importador de `adapters/inbound/qti`, que es puro. Aquí
solo se traduce su salida a `NewQuestion` y se decide qué hacer con lo que no se
pudo convertir.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from proctoring_api.application.ports.qti_parser import QtiParser
from proctoring_api.application.use_cases.manage_banks import AddQuestionsToBank
from proctoring_api.application.use_cases.manage_questions import NewQuestion
from proctoring_api.domain.errors import DomainError
from proctoring_api.domain.question import Question, QuestionType
from proctoring_api.domain.user import AuthenticatedUser

#: De dónde vino la pregunta. Queda en `questions.source_format` y es lo que
#: permite responder después "esto se importó, no lo escribí yo".
SOURCE_FORMAT = "qti"


class QtiImportError(DomainError):
    """El archivo no se pudo leer como QTI 2.1."""


@dataclass(frozen=True, slots=True)
class SkippedItem:
    """Un ítem que no se pudo convertir, y por qué."""

    item_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class QtiImportResult:
    """Qué entró, qué se quedó fuera y de qué hay que avisar.

    Los tres van juntos a propósito: un docente que importa cuarenta preguntas y
    recibe solo "38 importadas" no sabe qué perdió ni dónde buscarlo.
    """

    #: Las preguntas guardadas, en el banco y con su posición ya asignada.
    imported: Sequence[Question]
    #: Ítems que el importador no supo representar sin cambiarles el significado.
    skipped: Sequence[SkippedItem]
    #: Avisos sobre preguntas que **sí** entraron pero se califican distinto aquí
    #: que en la plataforma de origen.
    warnings: Sequence[SkippedItem]


class ImportQtiIntoBank:
    """Convierte un QTI en preguntas de un banco."""

    def __init__(self, add_questions: AddQuestionsToBank, parse: QtiParser) -> None:
        self._add_questions = add_questions
        #: El analizador se inyecta para poder probar este caso de uso sin XML.
        self._parse = parse

    def execute(
        self,
        bank_id: UUID,
        xml: bytes,
        *,
        actor: AuthenticatedUser | None = None,
        dry_run: bool = False,
    ) -> QtiImportResult:
        """Lee el archivo y guarda lo que se pueda representar.

        Con `dry_run` no guarda nada: devuelve lo que entraría. Sirve para que el
        docente vea el resultado antes de meter cuarenta preguntas en su banco.

        Un archivo del que no sale **ninguna** pregunta es un error, no un éxito
        vacío: casi siempre significa que subió el archivo equivocado, y
        responderle "0 importadas, todo bien" lo dejaría buscando sus preguntas.

        Raises:
            QtiImportError: si el XML no es QTI 2.1 legible, o si no produce
                ninguna pregunta.
            AuthorizationError: si el banco no es de ese docente.
            InvalidQuestionError: si alguna pregunta viola una regla del dominio.
        """
        try:
            analizado = self._parse(xml)
        except ValueError as error:
            raise QtiImportError(str(error)) from error

        nuevas = [_a_nueva_pregunta(item) for item in analizado.questions]
        descartados = [SkippedItem(i.item_id, i.reason) for i in analizado.issues]
        avisos = [SkippedItem(i.item_id, i.reason) for i in analizado.warnings]

        if not nuevas:
            detalle = f" Se descartaron {len(descartados)} items." if descartados else ""
            raise QtiImportError(
                "El archivo no trae ninguna pregunta que se pueda importar." + detalle
            )

        if dry_run:
            return QtiImportResult(imported=(), skipped=descartados, warnings=avisos)

        # Si una sola viola una regla no se guarda ninguna: es la misma promesa
        # que ya hace `AddQuestionsToBank`, y es la que evita que importar
        # cuarenta deje veintinueve a medias.
        guardadas = self._add_questions.execute(bank_id, nuevas, actor=actor)
        return QtiImportResult(imported=guardadas, skipped=descartados, warnings=avisos)


def _a_nueva_pregunta(item: Mapping[str, Any]) -> NewQuestion:
    """La salida del importador, con los tipos del dominio.

    El importador entrega `question_type` como texto porque es puro y no conoce
    el dominio. Un tipo que no exista aquí es un fallo de programación, no del
    archivo: el importador solo produce los cinco que sabemos representar.
    """
    return NewQuestion(
        question_type=QuestionType(item["question_type"]),
        statement=item["statement"],
        points=item["points"],
        options=list(item["options"]),
        correct_numeric_answer=item["correct_numeric_answer"],
        numeric_tolerance=item["numeric_tolerance"],
        correct_text_answer=item["correct_text_answer"],
        source_format=item.get("source_format") or SOURCE_FORMAT,
    )


__all__ = [
    "SOURCE_FORMAT",
    "ImportQtiIntoBank",
    "QtiImportError",
    "QtiImportResult",
    "SkippedItem",
]
