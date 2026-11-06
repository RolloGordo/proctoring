"""Las rutas de las portadas: cada curso solo apunta a imágenes suyas."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from proctoring_api.domain.course import (
    Course,
    InvalidCourseError,
    cover_path_for,
    is_cover_of,
)

from tests.conftest import NOW

CURSO = UUID("11111111-1111-4111-8111-111111111111")
OTRO = UUID("22222222-2222-4222-8222-222222222222")


@pytest.mark.parametrize(
    ("formato", "extension"),
    [("image/webp", "webp"), ("image/jpeg", "jpg"), ("image/png", "png")],
)
def test_la_ruta_va_dentro_de_la_carpeta_del_curso(formato: str, extension: str) -> None:
    ruta = cover_path_for(CURSO, formato, object_id=UUID(int=7))

    assert ruta == f"{CURSO}/{UUID(int=7).hex}.{extension}"
    assert is_cover_of(CURSO, ruta)


def test_cada_subida_estrena_nombre() -> None:
    assert cover_path_for(CURSO, "image/webp") != cover_path_for(CURSO, "image/webp")


@pytest.mark.parametrize("formato", ["image/gif", "image/svg+xml", "application/pdf", ""])
def test_solo_imagenes_admitidas(formato: str) -> None:
    # SVG fuera a propósito: puede llevar script dentro.
    with pytest.raises(InvalidCourseError):
        cover_path_for(CURSO, formato)


@pytest.mark.parametrize(
    "ruta",
    [
        f"{OTRO}/{'a' * 32}.webp",  # la portada de otro curso
        f"{CURSO}/../{OTRO}/{'a' * 32}.webp",  # salir de la carpeta
        f"{CURSO}/{'a' * 32}.svg",
        f"{CURSO}/{'a' * 31}.webp",
        f"{CURSO}/{'A' * 32}.webp",
        f"evidences/{CURSO}/{'a' * 32}.webp",
        f"{CURSO}/{'a' * 32}.webp/extra",
    ],
)
def test_rechaza_rutas_que_no_son_de_este_curso(ruta: str) -> None:
    assert not is_cover_of(CURSO, ruta)


def test_with_cover_valida_la_ruta() -> None:
    curso = Course.create(teacher_id=uuid4(), name="Taller", created_at=NOW, course_id=CURSO)
    ruta = cover_path_for(CURSO, "image/webp")

    assert curso.with_cover(ruta).cover_path == ruta
    assert curso.with_cover(ruta).with_cover(None).cover_path is None
    with pytest.raises(InvalidCourseError):
        curso.with_cover(f"{OTRO}/{'a' * 32}.webp")
