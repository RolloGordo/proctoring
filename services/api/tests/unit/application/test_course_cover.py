"""La portada de un curso: solo su docente la cambia y la vieja no se queda en el bucket."""

from __future__ import annotations

from uuid import uuid4

import pytest

from proctoring_api.adapters.outbound.memory.course_repository import InMemoryCourseRepository
from proctoring_api.adapters.outbound.memory.evidence_storage import InMemoryEvidenceStorage
from proctoring_api.adapters.outbound.memory.exam_session_repository import (
    InMemoryExamSessionRepository,
)
from proctoring_api.adapters.outbound.memory.question_bank_repository import (
    InMemoryQuestionBankRepository,
)
from proctoring_api.application.course_covers import CourseCovers
from proctoring_api.application.use_cases.course_cover import (
    RequestCourseCoverUpload,
    SetCourseCover,
)
from proctoring_api.application.use_cases.manage_courses import (
    DeleteEmptyCourse,
    GetCourse,
    ListTeacherCourses,
)
from proctoring_api.domain.course import Course, InvalidCourseError
from proctoring_api.domain.errors import AuthorizationError
from proctoring_api.domain.user import AuthenticatedUser, UserRole

from tests.conftest import NOW

BUCKET = "course-covers"
DOCENTE = AuthenticatedUser(id=uuid4(), role=UserRole.TEACHER)
OTRO_DOCENTE = AuthenticatedUser(id=uuid4(), role=UserRole.TEACHER)
ESTUDIANTE = AuthenticatedUser(id=uuid4(), role=UserRole.STUDENT)


class Mundo:
    def __init__(self) -> None:
        self.cursos = InMemoryCourseRepository()
        self.storage = InMemoryEvidenceStorage()
        self.portadas = CourseCovers(self.storage, BUCKET)
        self.pedir = RequestCourseCoverUpload(self.cursos, self.portadas)
        self.fijar = SetCourseCover(self.cursos, self.portadas)
        self.curso = Course.create(teacher_id=DOCENTE.id, name="Taller", created_at=NOW)
        self.cursos.save(self.curso)

    def subir(self, formato: str = "image/webp") -> str:
        return self.pedir.execute(self.curso.id, formato, actor=DOCENTE).path


@pytest.fixture
def mundo() -> Mundo:
    return Mundo()


def test_la_subida_es_a_una_ruta_nueva_del_curso(mundo: Mundo) -> None:
    firma = mundo.pedir.execute(mundo.curso.id, "image/webp", actor=DOCENTE)

    assert firma.path.startswith(f"{mundo.curso.id}/")
    assert firma.path.endswith(".webp")
    assert mundo.storage.issued == [(BUCKET, firma.path)]


@pytest.mark.parametrize("quien", [OTRO_DOCENTE, ESTUDIANTE])
def test_nadie_mas_pide_subir_ni_fija_la_portada(mundo: Mundo, quien: AuthenticatedUser) -> None:
    ruta = mundo.subir()

    with pytest.raises(AuthorizationError):
        mundo.pedir.execute(mundo.curso.id, "image/webp", actor=quien)
    with pytest.raises(AuthorizationError):
        mundo.fijar.execute(mundo.curso.id, ruta, actor=quien)
    assert mundo.cursos.find_by_id(mundo.curso.id).cover_path is None  # type: ignore[union-attr]


def test_un_formato_no_admitido_no_recibe_firma(mundo: Mundo) -> None:
    with pytest.raises(InvalidCourseError):
        mundo.pedir.execute(mundo.curso.id, "image/svg+xml", actor=DOCENTE)
    assert mundo.storage.issued == []


def test_fijar_devuelve_el_curso_con_su_url(mundo: Mundo) -> None:
    ruta = mundo.subir()

    resultado = mundo.fijar.execute(mundo.curso.id, ruta, actor=DOCENTE)

    assert resultado.course.cover_path == ruta
    assert resultado.cover_url is not None and ruta in resultado.cover_url


def test_no_se_fija_la_portada_de_otro_curso(mundo: Mundo) -> None:
    ajeno = Course.create(teacher_id=DOCENTE.id, name="Otro", created_at=NOW)
    mundo.cursos.save(ajeno)
    ruta_ajena = mundo.pedir.execute(ajeno.id, "image/webp", actor=DOCENTE).path

    with pytest.raises(InvalidCourseError):
        mundo.fijar.execute(mundo.curso.id, ruta_ajena, actor=DOCENTE)


def test_reemplazar_borra_la_imagen_anterior(mundo: Mundo) -> None:
    primera = mundo.subir()
    mundo.fijar.execute(mundo.curso.id, primera, actor=DOCENTE)
    segunda = mundo.subir("image/jpeg")

    mundo.fijar.execute(mundo.curso.id, segunda, actor=DOCENTE)

    assert mundo.storage.removed == {(BUCKET, primera)}


def test_volver_a_fijar_la_misma_no_la_borra(mundo: Mundo) -> None:
    ruta = mundo.subir()
    mundo.fijar.execute(mundo.curso.id, ruta, actor=DOCENTE)

    mundo.fijar.execute(mundo.curso.id, ruta, actor=DOCENTE)

    assert mundo.storage.removed == set()


def test_quitar_la_portada_la_borra_del_bucket(mundo: Mundo) -> None:
    ruta = mundo.subir()
    mundo.fijar.execute(mundo.curso.id, ruta, actor=DOCENTE)

    resultado = mundo.fijar.execute(mundo.curso.id, None, actor=DOCENTE)

    assert resultado.course.cover_path is None
    assert resultado.cover_url is None
    assert mundo.storage.removed == {(BUCKET, ruta)}


def test_si_storage_falla_al_borrar_la_portada_nueva_queda(mundo: Mundo) -> None:
    class StorageQueNoBorra(InMemoryEvidenceStorage):
        def remove(self, bucket: str, paths: object) -> None:
            raise RuntimeError("Storage caído")

    mundo.storage = StorageQueNoBorra()
    mundo.portadas = CourseCovers(mundo.storage, BUCKET)
    fijar = SetCourseCover(mundo.cursos, mundo.portadas)
    primera = mundo.subir()
    fijar.execute(mundo.curso.id, primera, actor=DOCENTE)
    segunda = mundo.subir()

    resultado = fijar.execute(mundo.curso.id, segunda, actor=DOCENTE)

    assert resultado.course.cover_path == segunda


def test_la_lista_firma_solo_las_portadas_que_existen(mundo: Mundo) -> None:
    sin_portada = Course.create(teacher_id=DOCENTE.id, name="Sin portada", created_at=NOW)
    mundo.cursos.save(sin_portada)
    ruta = mundo.subir()
    mundo.fijar.execute(mundo.curso.id, ruta, actor=DOCENTE)
    listar = ListTeacherCourses(mundo.cursos, covers=mundo.portadas)

    por_id = {c.course.id: c for c in listar.execute(actor=DOCENTE)}

    assert por_id[mundo.curso.id].cover_url is not None
    assert por_id[sin_portada.id].cover_url is None


def test_una_imagen_que_ya_no_esta_se_ve_como_sin_portada(mundo: Mundo) -> None:
    ruta = mundo.subir()
    mundo.fijar.execute(mundo.curso.id, ruta, actor=DOCENTE)
    mundo.storage.remove(BUCKET, [ruta])

    curso = GetCourse(mundo.cursos, mundo.portadas).execute(mundo.curso.id, actor=DOCENTE)

    assert curso.cover_url is None


def test_al_borrar_el_curso_se_borra_su_portada(mundo: Mundo) -> None:
    ruta = mundo.subir()
    mundo.fijar.execute(mundo.curso.id, ruta, actor=DOCENTE)
    borrar = DeleteEmptyCourse(
        mundo.cursos,
        InMemoryExamSessionRepository(),
        InMemoryQuestionBankRepository(),
        mundo.portadas,
    )

    borrar.execute(mundo.curso.id, actor=DOCENTE)

    assert mundo.storage.removed == {(BUCKET, ruta)}
