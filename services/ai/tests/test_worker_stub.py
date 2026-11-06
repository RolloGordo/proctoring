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


def test_salud_avisa_sin_fallar_cuando_hay_respaldo_sin_clave(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for nombre in REQUERIDAS:
        monkeypatch.setenv(nombre, "puesta")
    monkeypatch.setenv("ASR_PROVIDER", "faster-whisper")
    monkeypatch.setenv("ASR_FALLBACK_PROVIDER", "deepgram")
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)

    estado: dict[str, Any] = _estado(_RedisFalso(responde=True))  # type: ignore[arg-type]

    assert estado["queue"] is True
    assert estado["missing"] == []
    assert estado["asr_provider"] == "faster-whisper"
    assert estado["asr_fallback_provider"] == "deepgram"
    assert estado["asr_mode"] == "local-with-deepgram-fallback"
    assert any("DEEPGRAM_API_KEY" in w for w in estado["warnings"])


def test_precargar_modelos_respeta_modo_fork_vs_simple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import worker_stub

    monkeypatch.setenv("ASR_PROVIDER", "faster-whisper")
    asr_calls: list[int] = []
    sim_calls: list[int] = []
    monkeypatch.setattr(worker_stub, "_get_local_asr", lambda: asr_calls.append(1))
    monkeypatch.setattr(worker_stub, "similarity_model", lambda: sim_calls.append(1))

    # En modo fork (Worker en Linux), solo SimilarityModel se precarga en el padre
    # porque CTranslate2 ReplicaPool no es fork-safe.
    res_fork = worker_stub.precargar_modelos(fork_worker=True)
    assert res_fork["fork_worker"] is True
    assert res_fork["asr_preloaded"] is False
    assert res_fork["similarity_preloaded"] is True
    assert len(asr_calls) == 0
    assert len(sim_calls) == 1

    # En modo SimpleWorker (sin fork), se precargan ambos en el proceso padre.
    res_simple = worker_stub.precargar_modelos(fork_worker=False)
    assert res_simple["fork_worker"] is False
    assert res_simple["asr_preloaded"] is True
    assert res_simple["similarity_preloaded"] is True
    assert len(asr_calls) == 1
    assert len(sim_calls) == 2


def test_salud_expone_backend_de_similitud_y_aviso_de_memoria(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import audio_runtime

    for nombre in REQUERIDAS:
        monkeypatch.setenv(nombre, "puesta")
    monkeypatch.setenv("ASR_PROVIDER", "faster-whisper")
    monkeypatch.setenv("ASR_LOCAL_MODEL", "small")
    monkeypatch.setenv("SIMILARITY_BACKEND", "onnx-int8")
    monkeypatch.setattr(audio_runtime, "detect_memory_limit_bytes", lambda: 512 * 1024 * 1024)

    estado: dict[str, Any] = _estado(_RedisFalso(responde=True))  # type: ignore[arg-type]

    assert estado["similarity_backend"] == "onnx-int8"
    assert estado["memory_enforce"] is False
    assert estado["memory_limit_mib"] == 512.0
    assert estado["required_memory_mib"] == 1150.0
    assert estado["memory_sufficient"] is False
    assert any("Insufficient container memory" in w for w in estado["warnings"])
