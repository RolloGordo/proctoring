"""Leer un paquete QTI/SCORM (`.zip`).

`parse_manifest` es puro y nunca abre un archivo; abrir el zip es trabajo del
adaptador, y es justo el paso donde se cuelan las bombas de descompresión y las
rutas que se escapan. Eso es lo que se prueba aquí.
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from proctoring_api.adapters.inbound.qti.package import (
    MAX_ENTRIES,
    looks_like_package,
    parse_package,
    parse_upload,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "qti"

MANIFIESTO = (
    '<manifest xmlns="http://www.imsglobal.org/xsd/imscp_v1p1"><resources>'
    '<resource identifier="r1" type="imsqti_item_xmlv2p1" href="items/uno.xml"/>'
    "</resources></manifest>"
)


def zip_con(archivos: dict[str, bytes | str]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, datos in archivos.items():
            z.writestr(nombre, datos)
    return buffer.getvalue()


def pregunta() -> bytes:
    return (FIXTURES / "multiple_choice.xml").read_bytes()


def paquete_valido() -> bytes:
    return zip_con({"imsmanifest.xml": MANIFIESTO, "items/uno.xml": pregunta()})


class TestReconocerElFormato:
    def test_un_zip_se_reconoce(self) -> None:
        assert looks_like_package(paquete_valido())

    def test_un_xml_suelto_no(self) -> None:
        assert not looks_like_package(pregunta())

    def test_parse_upload_acepta_los_dos(self) -> None:
        """El docente no tiene que elegir el formato en la pantalla."""
        assert len(parse_upload(pregunta()).questions) == 1
        assert len(parse_upload(paquete_valido()).questions) == 1


class TestPaqueteValido:
    def test_la_pregunta_del_paquete_llega_entera(self) -> None:
        resultado = parse_package(paquete_valido())

        [importada] = resultado.questions
        assert importada["question_type"] == "multiple_choice"
        assert len(importada["options"]) == 2
        assert not resultado.issues

    def test_varias_preguntas_en_un_paquete(self) -> None:
        manifiesto = (
            '<manifest xmlns="http://www.imsglobal.org/xsd/imscp_v1p1"><resources>'
            '<resource identifier="r1" type="imsqti_item_xmlv2p1" href="a.xml"/>'
            '<resource identifier="r2" type="imsqti_item_xmlv2p1" href="b.xml"/>'
            "</resources></manifest>"
        )
        datos = zip_con(
            {
                "imsmanifest.xml": manifiesto,
                "a.xml": (FIXTURES / "essay.xml").read_bytes(),
                "b.xml": (FIXTURES / "numeric.xml").read_bytes(),
            }
        )

        resultado = parse_package(datos)

        assert [q["question_type"] for q in resultado.questions] == ["essay", "numeric"]

    def test_las_carpetas_del_zip_no_estorban(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("items/", "")
            z.writestr("imsmanifest.xml", MANIFIESTO)
            z.writestr("items/uno.xml", pregunta())

        assert len(parse_package(buffer.getvalue()).questions) == 1


class TestPaquetesMalos:
    def test_algo_que_no_es_un_zip(self) -> None:
        with pytest.raises(ValueError, match="comprimido"):
            parse_package(b"PK\x03\x04 pero roto")

    def test_sin_manifiesto_se_explica_que_hacer(self) -> None:
        """Es el error más probable: exportar solo las preguntas y subir el zip."""
        datos = zip_con({"items/uno.xml": pregunta()})

        with pytest.raises(ValueError, match="sube el XML"):
            parse_package(datos)

    def test_el_manifiesto_tiene_que_estar_en_la_raiz(self) -> None:
        datos = zip_con({"paquete/imsmanifest.xml": MANIFIESTO, "items/uno.xml": pregunta()})

        with pytest.raises(ValueError, match="no trae imsmanifest"):
            parse_package(datos)

    def test_demasiados_archivos(self) -> None:
        archivos: dict[str, bytes | str] = {"imsmanifest.xml": MANIFIESTO}
        for n in range(MAX_ENTRIES + 1):
            archivos[f"relleno/{n}.txt"] = "x"

        with pytest.raises(ValueError, match="mas de"):
            parse_package(zip_con(archivos))

    def test_una_bomba_de_descompresion_se_rechaza(self) -> None:
        """Un megabyte comprimido que se expande a cientos. Sin este tope, abrirlo
        se come la memoria del servidor antes de que nadie mire su contenido."""
        datos = zip_con({"imsmanifest.xml": MANIFIESTO, "bomba.txt": b"\0" * 5_000_000})

        with pytest.raises(ValueError, match=r"expande demasiado|pasa de"):
            parse_package(datos)

    def test_una_ruta_que_se_escapa_se_descarta(self) -> None:
        """Nada se escribe en disco, pero aun así no se le entrega al manifiesto."""
        datos = zip_con(
            {
                "imsmanifest.xml": MANIFIESTO,
                "items/uno.xml": pregunta(),
                "../fuera.xml": pregunta(),
            }
        )

        resultado = parse_package(datos)

        assert len(resultado.questions) == 1

    def test_un_recurso_que_falta_se_reporta_sin_tumbar_el_resto(self) -> None:
        manifiesto = (
            '<manifest xmlns="http://www.imsglobal.org/xsd/imscp_v1p1"><resources>'
            '<resource identifier="r1" type="imsqti_item_xmlv2p1" href="existe.xml"/>'
            '<resource identifier="r2" type="imsqti_item_xmlv2p1" href="no-existe.xml"/>'
            "</resources></manifest>"
        )
        datos = zip_con({"imsmanifest.xml": manifiesto, "existe.xml": pregunta()})

        resultado = parse_package(datos)

        assert len(resultado.questions) == 1
        assert [i.item_id for i in resultado.issues] == ["r2"]
        assert "no trae el archivo" in resultado.issues[0].reason
