"""Las pruebas no heredan la configuracion de quien las ejecuta."""

from __future__ import annotations

from proctoring_api.application.use_cases.create_exam_session import DEFAULT_DEV_TEACHER_ID
from proctoring_api.application.use_cases.manage_enrollment import DEFAULT_DEV_STUDENT_ID

from tests.conftest import _settings


def test_las_pruebas_no_leen_el_env_del_desarrollador() -> None:
    """La suite depende solo de lo que declara `_settings`.

    Sin `_env_file=None`, `Settings` lee el `.env` de la raiz y las pruebas
    heredan la configuracion real de la maquina: su DEV_TEACHER_ID, su
    INTERNAL_API_TOKEN. Paso de verdad: al generar el secreto interno,
    diecisiete pruebas se pusieron rojas sin que nadie tocara su codigo, y el
    motivo no estaba en el repositorio.
    """
    settings = _settings()

    assert settings.internal_api_token == ""
    assert settings.dev_teacher_id == DEFAULT_DEV_TEACHER_ID
    assert settings.dev_student_id == DEFAULT_DEV_STUDENT_ID
    assert settings.event_repository == "memory"
    assert settings.auth_enabled is False
