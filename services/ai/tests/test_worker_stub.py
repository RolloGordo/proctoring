"""Que el worker sepa decir que le falta, sin decir lo que vale."""

from __future__ import annotations

from typing import Any

import pytest

from worker_stub import REQUERIDAS, _configuracion, _estado


class _RedisFalso:
    def __init__(self, *, responde: bool) -> None:
        self._responde = responde

    def ping(self) -> bool:
        if not self._responde:
            raise ConnectionError("sin cola")
        return True


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch: pytest.MonkeyPatch) -> None:
    for nombre in REQUERIDAS:
        monkeypatch.delenv(nombre, raising=False)


def test_dice_que_falta_todo_cuando_no_hay_nada() -> None:
    estado = _estado(_RedisFalso(responde=True))  # type: ignore[arg-type]

    assert estado["missing"] == sorted(REQUERIDAS)


def test_una_variable_vacia_cuenta_como_ausente(monkeypatch: pytest.MonkeyPatch) -> None:
    # Render guarda sin quejarse una variable con solo espacios, y entonces
    # existe pero no sirve. Darla por buena manda el fallo mas adelante, donde
    # es mas dificil de leer.
    monkeypatch.setenv("SUPABASE_URL", "   ")

    assert _configuracion()["SUPABASE_URL"] is False


def test_no_se_devuelve_el_valor_de_ninguna_clave(monkeypatch: pytest.MonkeyPatch) -> None:
    # **El endpoint de salud es publico.** Lo sondea la plataforma, asi que
    # devolver aqui la clave de servicio seria regalarla.
    secreto = "service-role-de-mentira-pero-con-pinta-de-verdadera"
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", secreto)

    estado: dict[str, Any] = _estado(_RedisFalso(responde=True))  # type: ignore[arg-type]

    assert secreto not in repr(estado)
    assert estado["config"]["SUPABASE_SERVICE_ROLE_KEY"] is True  # type: ignore[index]


def test_con_todo_puesto_no_falta_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    for nombre in REQUERIDAS:
        monkeypatch.setenv(nombre, "puesta")

    estado = _estado(_RedisFalso(responde=True))  # type: ignore[arg-type]

    assert estado["missing"] == []
    assert estado["queue"] is True


def test_la_cola_caida_sigue_notandose(monkeypatch: pytest.MonkeyPatch) -> None:
    # Lo nuevo no puede tapar lo de antes: sin Redis el worker es inservible
    # aunque tenga toda la configuracion.
    for nombre in REQUERIDAS:
        monkeypatch.setenv(nombre, "puesta")

    estado = _estado(_RedisFalso(responde=False))  # type: ignore[arg-type]

    assert estado["queue"] is False
