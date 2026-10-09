from decimal import Decimal
from pathlib import Path

import pytest

from spikes.qti_import import MAX_XML_BYTES, NS, parse_qti

FIXTURES = Path(__file__).parent / "fixtures" / "qti"


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.xml").read_text(encoding="utf-8")


def test_numeric_absolute_tolerance_and_points() -> None:
    result = parse_qti(fixture("numeric_tolerance"))
    assert not result.issues
    assert result.questions[0]["numeric_tolerance"] == Decimal("0.01")
    assert result.questions[0]["points"] == Decimal(2)


@pytest.mark.parametrize(
    "before,after",
    [
        ('tolerance="0.01"', 'tolerance="-1"'),
        ('toleranceMode="absolute"', 'toleranceMode="relative"'),
        ("<equal ", '<equal includeLowerBound="false" '),
        (">0</baseValue>", ">1</baseValue>"),
        ('<correct identifier="RESPONSE"', '<correct identifier="OTHER"'),
    ],
)
def test_reject_unrepresentable_numeric_rules(before: str, after: str) -> None:
    result = parse_qti(fixture("numeric_tolerance").replace(before, after))
    assert not result.questions
    assert result.issues


@pytest.mark.parametrize(
    "kind", ["multiple_choice", "true_false", "numeric", "fill_blank", "essay"]
)
def test_five_types(kind: str) -> None:
    result = parse_qti(fixture(kind))
    assert not result.issues
    question = result.questions[0]
    assert question["question_type"] == kind
    assert question["points"] == Decimal(1)
    assert question["source_format"] == "qti"
    if kind == "multiple_choice":
        assert question["options"] == [("Primaria", True), ("Foránea", False)]
        assert question["statement"] == "¿Qué clave identifica una fila?"
    elif kind == "true_false":
        assert question["options"] == [("Verdadero", False), ("Falso", True)]
    elif kind == "numeric":
        assert question["correct_numeric_answer"] == Decimal("3.14")
        assert question["numeric_tolerance"] == 0
    elif kind == "fill_blank":
        assert question["correct_text_answer"] == "primaria"
        assert "____" in question["statement"]
        assert result.warnings and "Target API" in result.warnings[0].reason
    else:
        assert question["correct_text_answer"] is None


@pytest.mark.parametrize(
    "before,after",
    [
        ('maxChoices="1"', 'maxChoices="2"'),
        (
            'cardinality="single" baseType="identifier"',
            'cardinality="multiple" baseType="identifier"',
        ),
        ("<value>A</value>", "<value>Z</value>"),
        ('identifier="B"', 'identifier="A"'),
        ("Foránea", "Primaria"),
        ('normalMaximum="1"', 'normalMaximum="NaN"'),
        ('normalMaximum="1"', 'normalMaximum="2"'),
        ('responseIdentifier="RESPONSE"', 'responseIdentifier="OTHER"'),
        ("<prompt>", '<prompt><img src="remote.jpg"/>'),
        ("rptemplates/match_correct", "rptemplates/map_response"),
    ],
)
def test_unsupported_items_have_diagnostics(before: str, after: str) -> None:
    result = parse_qti(fixture("multiple_choice").replace(before, after))
    assert not result.questions
    assert len(result.issues) == 1
    assert result.issues[0].reason


def test_skip_bad_item_keep_good_and_report_duplicate() -> None:
    good = fixture("essay").split("?>", 1)[1]
    bad = fixture("numeric").split("?>", 1)[1].replace("3.14", "Infinity")
    result = parse_qti(f"<items>{good}{bad}{good}</items>")
    assert len(result.questions) == 1
    assert len(result.issues) == 2


@pytest.mark.parametrize(
    "xml",
    [
        '<!DOCTYPE x [<!ENTITY x "injected">]><x>&x;</x>',
        '<!DOCTYPE x SYSTEM "file:///etc/passwd"><x/>',
        "<broken>",
        "<manifest/>",
        "<x/>",
        fixture("essay").replace(NS, "http://example.com/not-qti"),
    ],
)
def test_reject_invalid_documents(xml: str) -> None:
    with pytest.raises(ValueError):
        parse_qti(xml)


def test_size_encoding_and_item_limits() -> None:
    for xml in [b" " * (MAX_XML_BYTES + 1), b"\xff", fixture("essay").encode("utf-16")]:
        with pytest.raises(ValueError):
            parse_qti(xml)
    item = fixture("essay").split("?>", 1)[1]
    with pytest.raises(ValueError, match="200"):
        parse_qti(f"<items>{item * 201}</items>")
    with pytest.raises(ValueError, match="nesting"):
        parse_qti("<x>" * 70 + item + "</x>" * 70)


def test_inline_text_and_two_non_boolean_options() -> None:
    xml = fixture("multiple_choice").replace("Primaria", "<em>Primaria</em>")
    question = parse_qti(xml).questions[0]
    assert question["question_type"] == "multiple_choice"
    assert question["options"][0] == ("Primaria", True)


def test_multiple_interactions_not_silently_truncated() -> None:
    xml = fixture("fill_blank").replace(
        "</itemBody>", '<textEntryInteraction responseIdentifier="RESPONSE"/></itemBody>'
    )
    assert parse_qti(xml).issues
