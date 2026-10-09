"""Importador conservador de QTI 2.1. Puro: sin disco, sin red, sin la API.

Escrito por Pierreluiggi Zevallos como spike en `services/ai/spikes/` y movido
aqui al conectarlo: los dos servicios Python no pueden importarse entre si, y
esto es analisis puro de la biblioteca estandar, sin modelos ni cola, asi que su
sitio es el adaptador de entrada de la API y no una llamada de red.

Solo son representables en `NewQuestion` los items de respuesta unica y de texto.
Un item que no lo sea vuelve como diagnostico en vez de cambiarle en silencio su
forma de calificar. Quien llame convierte `question_type` a `QuestionType`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from xml.etree import ElementTree as ET

NS = "http://www.imsglobal.org/xsd/imsqti_v2p1"
MAX_XML_BYTES = 1_000_000


@dataclass(frozen=True)
class ImportIssue:
    item_id: str
    reason: str


@dataclass(frozen=True)
class ImportResult:
    questions: tuple[dict[str, Any], ...]
    issues: tuple[ImportIssue, ...]
    warnings: tuple[ImportIssue, ...] = ()


def _tag(name: str) -> str:
    return f"{{{NS}}}{name}"


def _decimal(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Un numero no se entiende") from error
    if not result.is_finite():
        raise ValueError("Un numero no es finito")
    return result


def _text(element: ET.Element) -> str:
    # Preserve inline boundaries: <em>primaria</em> is not a new word separator.
    return " ".join("".join(element.itertext()).split())


def _statement(element: ET.Element) -> str:
    parts = [element.text or ""]
    for child in element:
        local = child.tag.rsplit("}", 1)[-1]
        if local == "simpleChoice":
            pass
        elif local in {"textEntryInteraction", "extendedTextInteraction"}:
            parts.append(" ____ ")
        else:
            parts.append(_statement(child))
        parts.append(child.tail or "")
        if local in {"p", "div", "br", "prompt"}:
            parts.append(" ")
    return "".join(parts)


def _parse_item(item: ET.Element) -> dict[str, Any]:
    if item.get("adaptive", "false") != "false":
        raise ValueError("Las preguntas adaptativas no se pueden importar")
    body = item.find(_tag("itemBody"))
    if body is None:
        raise ValueError("A la pregunta le falta el enunciado")
    allowed = {
        "itemBody",
        "p",
        "div",
        "span",
        "em",
        "strong",
        "b",
        "i",
        "u",
        "br",
        "prompt",
        "choiceInteraction",
        "simpleChoice",
        "textEntryInteraction",
        "extendedTextInteraction",
    }
    if any(node.tag not in {_tag(name) for name in allowed} for node in body.iter()):
        raise ValueError(
            "El enunciado lleva imagenes, formulas u otra interaccion que no sabemos representar"
        )
    interactions = [node for node in body.iter() if node.tag.endswith("Interaction")]
    if len(interactions) != 1:
        raise ValueError("La pregunta tiene que pedir una sola respuesta")
    interaction = interactions[0]
    response_id = interaction.get("responseIdentifier")
    declarations = item.findall(_tag("responseDeclaration"))
    if len(declarations) != 1 or not response_id:
        raise ValueError("La pregunta tiene que declarar una sola respuesta")
    response = declarations[0]
    if response.get("identifier") != response_id or response.get("cardinality") != "single":
        raise ValueError("La respuesta esta declarada de una forma que no sabemos leer")
    statement = " ".join(_statement(body).split())
    if not statement or statement == "____" or len(statement) > 5000:
        raise ValueError("El enunciado esta vacio o pasa de 5000 caracteres")
    points = Decimal(1)
    score = item.find(f"{_tag('outcomeDeclaration')}[@identifier='SCORE']")
    if score is not None:
        # normalMaximum describes the maximum, defaultValue is NOT the maximum.
        points = _decimal(score.get("normalMaximum", "1"))
    if points < 0:
        raise ValueError("Negative points")
    result: dict[str, Any] = {
        "question_type": "essay",
        "statement": statement,
        "points": points,
        "options": [],
        "correct_numeric_answer": None,
        "numeric_tolerance": None,
        "correct_text_answer": None,
        "source_format": "qti",
    }
    processing = item.find(_tag("responseProcessing"))
    numeric_rule = processing is not None and bool(list(processing))
    if numeric_rule:
        # Recognize only a complete, two-branch absolute numeric comparison.
        # Any additional operators or scoring rules require a richer domain model.
        assert processing is not None
        condition = processing.find(_tag("responseCondition"))
        if len(processing) != 1 or condition is None or len(condition) != 2:
            raise ValueError("Usa una forma de calificar que no podemos reproducir")
        yes, no = list(condition)
        if yes.tag != _tag("responseIf") or no.tag != _tag("responseElse"):
            raise ValueError("Usa una forma de calificar con ramas que no podemos reproducir")
        if len(yes) != 2 or len(no) != 1:
            raise ValueError("Usa instrucciones de calificacion que no podemos reproducir")
        comparison, award = list(yes)
        if (
            interaction.tag != _tag("textEntryInteraction")
            or response.get("baseType") not in {"float", "integer"}
            or comparison.tag != _tag("equal")
            or comparison.get("toleranceMode") != "absolute"
            or comparison.get("includeLowerBound", "true") != "true"
            or comparison.get("includeUpperBound", "true") != "true"
        ):
            raise ValueError("Solo admitimos tolerancia numerica absoluta e inclusiva")
        operands = list(comparison)
        if (
            len(operands) != 2
            or operands[0].tag != _tag("variable")
            or operands[0].get("identifier") != response_id
            or operands[1].tag != _tag("correct")
            or operands[1].get("identifier") != response_id
        ):
            raise ValueError("La comparacion numerica no se puede reproducir")
        tolerance = _decimal(comparison.get("tolerance", ""))
        if tolerance < 0:
            raise ValueError("La tolerancia es negativa")
        for setter, expected in ((award, points), (no[0], Decimal(0))):
            if (
                setter.tag != _tag("setOutcomeValue")
                or setter.get("identifier") != "SCORE"
                or len(setter) != 1
                or setter[0].tag != _tag("baseValue")
                or _decimal(_text(setter[0])) != expected
            ):
                raise ValueError("Asigna el puntaje de una forma que no sabemos leer")
        result["numeric_tolerance"] = tolerance
    elif processing is not None:
        templates = {
            "http://www.imsglobal.org/question/qti_v2p1/rptemplates/match_correct",
            "http://www.imsglobal.org/question/qti_v2p1/rptemplates/match_correct.xml",
        }
        if list(processing) or processing.get("template") not in templates:
            raise ValueError(
                "Su forma de calificar no se puede importar sin cambiarle el significado"
            )
        if points != 1:
            raise ValueError("match_correct awards one point; inconsistent normalMaximum")
    if response.find(_tag("mapping")) is not None:
        raise ValueError("No admitimos puntaje parcial por opcion")
    values = response.findall(f"{_tag('correctResponse')}/{_tag('value')}")
    base_type = response.get("baseType")
    if interaction.tag == _tag("extendedTextInteraction"):
        if base_type != "string" or values or processing is not None:
            raise ValueError("Un desarrollo tiene que calificarse a mano y responderse con texto")
        return result
    if len(values) != 1 or not _text(values[0]):
        raise ValueError("Tiene que haber una sola respuesta correcta")
    answer = _text(values[0])
    if interaction.tag == _tag("choiceInteraction"):
        if base_type != "identifier" or interaction.get("maxChoices") != "1":
            raise ValueError("Solo admitimos preguntas de una sola alternativa")
        choices = interaction.findall(_tag("simpleChoice"))
        ids = [choice.get("identifier") for choice in choices]
        labels = [_text(choice) for choice in choices]
        if (
            not 2 <= len(choices) <= 10
            or None in ids
            or "" in ids
            or len(set(ids)) != len(ids)
            or len({label.casefold() for label in labels}) != len(labels)
            or answer not in ids
            or any(not label or len(label) > 1000 for label in labels)
        ):
            raise ValueError("Invalid choices or correct identifier")
        result["options"] = [
            (label, identifier == answer) for identifier, label in zip(ids, labels, strict=True)
        ]
        normalized = {label.casefold() for label in labels}
        result["question_type"] = (
            "true_false"
            if normalized in ({"true", "false"}, {"verdadero", "falso"})
            else "multiple_choice"
        )
    elif base_type in {"integer", "float"}:
        number = _decimal(answer)
        if base_type == "integer" and number != number.to_integral_value():
            raise ValueError("Integer response contains a fraction")
        result.update(
            question_type="numeric",
            correct_numeric_answer=number,
            numeric_tolerance=result["numeric_tolerance"] or Decimal(0),
        )
    elif base_type == "string":
        result.update(question_type="fill_blank", correct_text_answer=answer)
    else:
        raise ValueError("Unsupported response baseType")
    return result


def parse_qti(xml: str | bytes) -> ImportResult:
    """Convert one assessmentItem or a wrapper of items to NewQuestion kwargs.

    Malformed/unsafe documents raise ValueError. Unsupported individual items are
    skipped with an issue. No external entities or resource links are resolved.
    UTF-8 only; the size limit is checked before XML parsing.
    """
    raw = xml.encode("utf-8") if isinstance(xml, str) else xml
    if len(raw) > MAX_XML_BYTES:
        raise ValueError("El archivo pasa de 1 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("El archivo tiene que estar en UTF-8") from error
    if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ValueError("El archivo usa DTD o entidades XML, que no se aceptan por seguridad")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError(f"El XML esta mal formado: {error}") from error
    stack = [(root, 0)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if depth > 64 or count > 20000:
            raise ValueError(
                "El archivo esta anidado demasiado profundo o tiene demasiados elementos"
            )
        stack.extend((child, depth + 1) for child in node)
    items = list(root.iter(_tag("assessmentItem")))
    if not items:
        raise ValueError(
            "No se encontro ninguna pregunta QTI 2.1. Si subiste el manifiesto "
            "del paquete, sube el archivo de preguntas"
        )
    if len(items) > 200:
        raise ValueError("Un archivo admite como maximo 200 preguntas")
    questions: list[dict[str, Any]] = []
    issues: list[ImportIssue] = []
    warnings: list[ImportIssue] = []
    seen: set[str] = set()
    for item in items:
        identifier = item.get("identifier", "")
        try:
            if not identifier or identifier in seen:
                raise ValueError("La pregunta no tiene identificador, o esta repetido")
            seen.add(identifier)
            question = _parse_item(item)
            questions.append(question)
            if question["question_type"] == "fill_blank":
                warnings.append(
                    ImportIssue(
                        identifier,
                        "Al calificar ignoramos mayusculas, tildes (la ñ no) y los "
                        "espacios de sobra, mientras que QTI exige coincidencia exacta. "
                        "Revisa esa diferencia antes de usar esta pregunta",
                    )
                )
        except ValueError as error:
            issues.append(ImportIssue(identifier, str(error)))
    return ImportResult(tuple(questions), tuple(issues), tuple(warnings))
