"""Las pruebas no heredan la configuracion de quien las ejecuta."""

from __future__ import annotations

import logging

import pytest

from proctoring_api.application.use_cases.create_exam_session import DEFAULT_DEV_TEACHER_ID
from proctoring_api.application.use_cases.manage_enrollment import DEFAULT_DEV_STUDENT_ID
from proctoring_api.config import Settings

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


class TestLaUrlDeSupabase:
    """`SUPABASE_URL` se queda en el origen aunque traiga una ruta.

    El panel de Supabase ensena la direccion con `/rest/v1` en los ejemplos de
    la API. Con esa puesta, el JWKS que verifica los tokens se pide a
    `/rest/v1/auth/v1/.well-known/jwks.json`, que responde 401, y **todo el que
    inicie sesion** recibe "No se pudo verificar el token en este momento".
    """

    def test_quita_la_ruta_de_los_ejemplos_de_la_api(self) -> None:
        ajustes = Settings(supabase_url="https://abc.supabase.co/rest/v1/")

        assert ajustes.supabase_url == "https://abc.supabase.co"

    def test_quita_la_barra_final(self) -> None:
        assert Settings(supabase_url="https://abc.supabase.co/").supabase_url == (
            "https://abc.supabase.co"
        )

    def test_deja_intacto_lo_que_ya_esta_bien(self) -> None:
        assert Settings(supabase_url="https://abc.supabase.co").supabase_url == (
            "https://abc.supabase.co"
        )

    def test_sin_valor_sigue_vacio(self) -> None:
        # Es el modo sin Supabase, que usa el equipo en local.
        assert Settings(supabase_url="").supabase_url == ""

    def test_avisa_en_el_registro_al_corregirla(self, caplog: pytest.LogCaptureFixture) -> None:
        # Se corrige para no dejar a nadie fuera, pero queda constancia: una
        # configuracion arreglada en silencio vuelve en el siguiente despliegue.
        with caplog.at_level(logging.WARNING):
            Settings(supabase_url="https://abc.supabase.co/rest/v1")

        assert "SUPABASE_URL" in caplog.text
