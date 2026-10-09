from pathlib import Path

import pytest

from proctoring_api.adapters.inbound.qti.importer import api_questions, parse_manifest, parse_qti

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "qti"


def manifest(href: str, kind: str = "imsqti_item_xmlv2p1") -> str:
    return (
        f'<manifest xmlns="http://www.imsglobal.org/xsd/imscp_v1p1"><resources>'
        f'<resource identifier="r1" type="{kind}" href="{href}"/>'
        "</resources></manifest>"
    )


def test_manifest_and_api_payload() -> None:
    result = parse_manifest(
        manifest("items/one.xml"),
        {"items/one.xml": (FIXTURES / "multiple_choice.xml").read_bytes()},
    )
    payload = api_questions(result)[0]
    assert not result.issues
    assert isinstance(payload["points"], str)
    assert set(payload["options"][0]) == {"option_text", "is_correct"}


@pytest.mark.parametrize(
    "path", ["../a.xml", "%2e%2e/a.xml", "https://evil/a.xml", "C:/a.xml", "/a.xml"]
)
def test_manifest_rejects_escape(path: str) -> None:
    result = parse_manifest(manifest(path), {path: b"never read"})
    assert not result.questions
    assert "no es segura" in result.issues[0].reason


def test_missing_and_unsupported_resources_reported() -> None:
    assert "no trae el archivo" in parse_manifest(manifest("a.xml"), {}).issues[0].reason
    assert (
        "no es una pregunta QTI"
        in parse_manifest(manifest("a.xml", "webcontent"), {}).issues[0].reason
    )


def test_manifest_rejects_entities() -> None:
    with pytest.raises(ValueError, match="DTD"):
        parse_manifest("<!DOCTYPE a><manifest/>", {})


@pytest.mark.parametrize(
    "name", ["essay", "fill_blank", "multiple_choice", "numeric", "numeric_tolerance", "true_false"]
)
def test_each_type_has_json_ready_payload(name: str) -> None:
    import json

    result = parse_qti((FIXTURES / f"{name}.xml").read_bytes())
    assert len(json.loads(json.dumps(api_questions(result)))) == 1
