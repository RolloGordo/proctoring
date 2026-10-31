from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

import audio_runtime
import deepgram_transcriber
import tasks
from spikes.transcribe import Transcriber

EVENT = "00000000-0000-4000-8000-000000000001"


def test_worker_downloads_measures_posts_and_cleans(monkeypatch):
    paths = []

    def download(job, path):
        paths.append(path)
        path.write_bytes(b"test fixture")

    measurement = {
        "transcript": "pregunta",
        "similarity": 0.99,
        "synthetic_voice_score": 0.01,
        "model_versions": {"asr": "fake-test"},
    }
    post = Mock(return_value={"alerted": False})
    monkeypatch.setattr(tasks, "INTERNAL_TOKEN", "test-only")
    monkeypatch.setattr(
        tasks,
        "_get",
        lambda _: {
            "question_statement": "pregunta",
            "similarity_threshold": 0.6,
            "synthetic_threshold": 0.5,
        },
    )
    monkeypatch.setattr(tasks, "download_audio", download)
    monkeypatch.setattr(tasks, "measure_audio", lambda p, q: measurement)
    monkeypatch.setattr(tasks, "_post", post)
    assert tasks.analyze_audio(EVENT) == {"alerted": False}
    assert not paths[0].exists()
    assert post.call_args.args[1]["processing_ms"] >= 0
    assert "alerted" not in post.call_args.args[1]


def test_download_failure_never_posts_empty_success(monkeypatch):
    monkeypatch.setattr(tasks, "INTERNAL_TOKEN", "test-only")
    monkeypatch.setattr(tasks, "_get", lambda _: {})
    monkeypatch.setattr(tasks, "download_audio", Mock(side_effect=OSError("unavailable")))
    post = Mock()
    monkeypatch.setattr(tasks, "_post", post)
    with pytest.raises(OSError):
        tasks.analyze_audio(EVENT)
    post.assert_not_called()


@pytest.mark.parametrize("question", [None, "", "  "])
def test_missing_question_and_disabled_synthetic_stay_null(monkeypatch, question):
    import spikes.synthetic_voice

    monkeypatch.setattr(spikes.synthetic_voice, "decode_audio", lambda _: [0.0] * 1600)
    monkeypatch.setattr(
        audio_runtime, "asr_model", lambda: Mock(transcribe=lambda _: {"transcript": "hola"})
    )
    similarity = Mock()
    monkeypatch.setattr(audio_runtime, "similarity_model", similarity)
    monkeypatch.setattr(audio_runtime, "synthetic_model", lambda: None)
    measured = audio_runtime.measure_audio(Path("unused"), question)
    assert measured["similarity"] is None
    assert measured["synthetic_voice_score"] is None
    similarity.assert_not_called()


def test_a_missing_similarity_model_does_not_destroy_the_analysis(monkeypatch):
    """Sin modelo no hay similitud, pero el fragmento y su transcripcion si.

    Esto subia hasta RQ y mataba el trabajo entero: el docente no recibia ni la
    transcripcion, y el expediente se leia igual que si nadie hubiera hablado.
    Es el fallo que se vio en produccion el 30/10, en cuanto el enunciado
    empezo a llegar al worker y la similitud se intento por primera vez.
    """
    import spikes.synthetic_voice

    monkeypatch.setattr(spikes.synthetic_voice, "decode_audio", lambda _: [0.0] * 1600)
    monkeypatch.setattr(
        audio_runtime, "asr_model", lambda: Mock(transcribe=lambda _: {"transcript": "hola"})
    )
    monkeypatch.setattr(audio_runtime, "synthetic_model", lambda: None)

    def sin_modelo():
        raise RuntimeError("Similarity model could not be loaded offline.")

    monkeypatch.setattr(audio_runtime, "similarity_model", sin_modelo)

    measured = audio_runtime.measure_audio(Path("unused"), "Que es la elasticidad precio")

    assert measured["transcript"] == "hola"
    assert measured["similarity"] is None
    assert measured["model_versions"]["sim"] == "unavailable:model-not-loaded"
    assert "offline" in measured["model_versions"]["sim_error"]


@pytest.mark.parametrize("path", ["../secret", "/absolute", "a/../b", "a\\b", "a//b"])
def test_storage_path_validation(monkeypatch, tmp_path, path):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    with pytest.raises(ValueError, match="path"):
        audio_runtime.download_audio(
            {"audio_bucket": "audio-segments", "audio_path": path}, tmp_path / "audio"
        )


def test_invalid_event_rejected_before_network():
    with pytest.raises(ValueError):
        tasks.analyze_audio("../../bad")


def test_disabled_detector_is_not_zero(monkeypatch):
    audio_runtime.synthetic_model.cache_clear()
    monkeypatch.delenv("AUDIO_SYNTHETIC_MODE", raising=False)
    assert audio_runtime.synthetic_model() is None
    audio_runtime.synthetic_model.cache_clear()


# --- ASR provider selection (SPEC-008). Every Deepgram response is simulated. -------------

FAKE_KEY = "dg-test-key-not-real-0123456789"


@pytest.fixture
def asr_env(monkeypatch):
    """Clean provider configuration and a hard stop on any real network request."""
    monkeypatch.delenv("ASR_PROVIDER", raising=False)
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPGRAM_TIMEOUT_SECONDS", raising=False)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("A real network request was attempted")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    return monkeypatch


@pytest.fixture
def local_asr(asr_env):
    """Stands in for the cached Faster-Whisper model: no model is ever loaded in tests."""
    local = Mock(name="local-faster-whisper")
    factory = Mock(return_value=local)
    asr_env.setattr(audio_runtime, "_local_asr_model", factory)
    local.factory = factory  # lets tests prove the local engine was never requested
    return local


@pytest.mark.parametrize("value", [None, "", "   "])
def test_default_provider_is_deepgram(asr_env, local_asr, value):
    if value is not None:
        asr_env.setenv("ASR_PROVIDER", value)
    asr_env.setenv("DEEPGRAM_API_KEY", FAKE_KEY)
    assert audio_runtime.DEFAULT_ASR_PROVIDER == "deepgram"
    assert audio_runtime.asr_provider() == "deepgram"
    model = audio_runtime.asr_model()
    assert isinstance(model, deepgram_transcriber.DeepgramTranscriber)
    assert model.version == "deepgram-nova-3-es"
    local_asr.factory.assert_not_called()


@pytest.mark.parametrize("value", ["faster-whisper", "Faster-Whisper", " faster-whisper "])
def test_faster_whisper_can_be_selected_explicitly(asr_env, local_asr, value):
    asr_env.setenv("ASR_PROVIDER", value)
    assert audio_runtime.asr_model() is local_asr


def test_default_without_key_fails_clearly_and_never_falls_back(asr_env, local_asr):
    # TA-070: a missing key is an explicit error, not a silent switch to another engine.
    with pytest.raises(deepgram_transcriber.DeepgramError, match="DEEPGRAM_API_KEY is required"):
        audio_runtime.asr_model()
    local_asr.factory.assert_not_called()


def test_faster_whisper_without_its_extra_fails_with_an_actionable_message(asr_env):
    real_find_spec = audio_runtime.importlib.util.find_spec

    def find_spec(name, *args, **kwargs):
        return None if name == "faster_whisper" else real_find_spec(name, *args, **kwargs)

    asr_env.setenv("ASR_PROVIDER", "faster-whisper")
    asr_env.setattr(audio_runtime.importlib.util, "find_spec", find_spec)
    audio_runtime._local_asr_model.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="uv sync --extra asr-local"):
            audio_runtime.asr_model()
    finally:
        audio_runtime._local_asr_model.cache_clear()


def test_deepgram_can_be_selected(asr_env, local_asr):
    asr_env.setenv("ASR_PROVIDER", "deepgram")
    asr_env.setenv("DEEPGRAM_API_KEY", FAKE_KEY)
    model = audio_runtime.asr_model()
    assert isinstance(model, deepgram_transcriber.DeepgramTranscriber)
    assert model.version == "deepgram-nova-3-es"
    assert FAKE_KEY not in repr(model)


def test_unknown_provider_fails_explicitly_without_echoing_it(asr_env, local_asr):
    asr_env.setenv("ASR_PROVIDER", "whisper-cloud-secret-123")
    with pytest.raises(ValueError, match="Unknown ASR_PROVIDER") as caught:
        audio_runtime.asr_model()
    assert "secret-123" not in str(caught.value)
    assert "faster-whisper" in str(caught.value) and "deepgram" in str(caught.value)
    with pytest.raises(ValueError, match="Unknown ASR_PROVIDER"):
        audio_runtime.asr_provider()


def test_deepgram_without_key_fails_before_any_request(asr_env, local_asr):
    asr_env.setenv("ASR_PROVIDER", "deepgram")
    with pytest.raises(deepgram_transcriber.DeepgramError, match="DEEPGRAM_API_KEY is required"):
        audio_runtime.asr_model()
    asr_env.setenv("DEEPGRAM_API_KEY", "  ")
    with pytest.raises(deepgram_transcriber.DeepgramError, match="DEEPGRAM_API_KEY is required"):
        audio_runtime.asr_model()
    # asr_env turns any real request into a failure, so reaching here proves none was made.


def test_changing_configuration_is_never_masked_by_a_cache(asr_env, local_asr):
    asr_env.setenv("ASR_PROVIDER", "faster-whisper")
    assert audio_runtime.asr_model() is local_asr
    asr_env.setenv("ASR_PROVIDER", "deepgram")
    asr_env.setenv("DEEPGRAM_API_KEY", FAKE_KEY)
    first = audio_runtime.asr_model()
    assert isinstance(first, deepgram_transcriber.DeepgramTranscriber)
    assert audio_runtime.asr_model() is not first  # built fresh: key/timeout always current
    asr_env.setenv("ASR_PROVIDER", "faster-whisper")
    assert audio_runtime.asr_model() is local_asr
    asr_env.setenv("ASR_PROVIDER", "deepgram")
    asr_env.delenv("DEEPGRAM_API_KEY")
    with pytest.raises(deepgram_transcriber.DeepgramError):
        audio_runtime.asr_model()  # the previous Deepgram instance is not reused


def test_only_the_local_model_is_cached(asr_env):
    assert audio_runtime._local_asr_model.cache_info().maxsize == 1
    assert not hasattr(audio_runtime.asr_model, "cache_info")


def test_faster_whisper_version_keeps_its_historical_identifier():
    small = Transcriber.__new__(Transcriber)
    small.model = "small"
    assert small.version == "faster-whisper-small-cpu-int8"
    base = Transcriber.__new__(Transcriber)
    base.model = "base"
    assert base.version == "faster-whisper-base-cpu-int8"


@pytest.fixture
def measure_env(asr_env):
    import spikes.synthetic_voice

    asr_env.setattr(spikes.synthetic_voice, "decode_audio", lambda _: [0.0] * 1600)
    asr_env.setattr(audio_runtime, "synthetic_model", lambda: None)
    return asr_env


def test_measure_audio_records_the_local_version_when_selected(measure_env):
    measure_env.setenv("ASR_PROVIDER", "faster-whisper")
    local = Transcriber.__new__(Transcriber)
    local.model = "small"
    local.transcribe = lambda _path: {"transcript": "hola"}  # type: ignore[method-assign]
    measure_env.setattr(audio_runtime, "_local_asr_model", lambda: local)
    measured = audio_runtime.measure_audio(Path("unused"), None)
    assert measured["transcript"] == "hola"
    assert measured["model_versions"]["asr"] == "faster-whisper-small-cpu-int8"


def test_measure_audio_records_the_selected_provider_version(measure_env):
    fake = SimpleNamespace(transcribe=lambda _p: {"transcript": "hola"}, version="fake-asr-v9")
    measure_env.setattr(audio_runtime, "asr_model", lambda: fake)
    measured = audio_runtime.measure_audio(Path("unused"), None)
    assert measured["model_versions"]["asr"] == "fake-asr-v9"


def test_existing_style_mock_without_version_is_recorded_as_unknown(measure_env):
    # The mock used by the earlier tests has no usable `version`: never mislabel it.
    measure_env.setattr(
        audio_runtime, "asr_model", lambda: Mock(transcribe=lambda _: {"transcript": "hola"})
    )
    measured = audio_runtime.measure_audio(Path("unused"), None)
    assert measured["model_versions"]["asr"] == "asr-unknown"
    assert measured["similarity"] is None and measured["synthetic_voice_score"] is None


def test_measure_audio_end_to_end_with_simulated_deepgram(measure_env, tmp_path):
    # No ASR_PROVIDER: the default path itself must reach Deepgram.
    measure_env.setenv("DEEPGRAM_API_KEY", FAKE_KEY)
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "metadata": {"request_id": "abc-123", "duration": 1.5},
                "results": {
                    "channels": [{"alternatives": [{"transcript": "hola desde deepgram"}]}]
                },
            },
        )

    real_client = httpx.Client

    class MockedClient(real_client):  # type: ignore[valid-type, misc]
        def __init__(self, **kwargs):
            super().__init__(transport=httpx.MockTransport(handler), **kwargs)

    measure_env.setattr(deepgram_transcriber.httpx, "Client", MockedClient)
    audio = tmp_path / "segment.audio"
    audio.write_bytes(b"synthetic-test-bytes-not-speech")
    measured = audio_runtime.measure_audio(audio, None)
    # Worker contract unchanged: exactly these keys (tasks.py adds processing_ms).
    assert set(measured) == {"transcript", "similarity", "synthetic_voice_score", "model_versions"}
    assert measured["transcript"] == "hola desde deepgram"
    assert measured["model_versions"]["asr"] == "deepgram-nova-3-es"
    assert measured["similarity"] is None and measured["synthetic_voice_score"] is None
    assert "alerted" not in measured  # the worker measures; the API decides
    assert len(seen) == 1 and seen[0].headers["Authorization"] == f"Token {FAKE_KEY}"
    assert FAKE_KEY not in repr(measured)


def test_missing_similarity_model_still_transcribes(measure_env):
    """Decision cambiada el 31/10, y no a la ligera.

    Esta prueba exigia lo contrario: sin modelo de similitud no se gastaba una
    transcripcion de pago, porque la transcripcion solo servia para alimentar
    la comparacion con el enunciado.

    Dejo de ser cierto el 19/10, cuando el Product Owner decidio que **hablar
    durante el examen se reporta por si solo**: la transcripcion viaja con la
    alerta para que el docente decida, exista o no la similitud. Con la regla
    vieja, un modelo ausente borraba el fragmento, la transcripcion y la senal
    entera, y el expediente quedaba igual que si nadie hubiera hablado.

    El coste es real y se asume: cada fragmento de voz paga su transcripcion
    aunque la similitud no se pueda medir. Son centimos por examen; perder la
    evidencia no tiene vuelta atras.
    """
    asr = Mock(transcribe=lambda _: {"transcript": "me puedes decir la respuesta"})
    measure_env.setattr(audio_runtime, "asr_model", lambda: asr)
    measure_env.setattr(
        audio_runtime, "similarity_model", Mock(side_effect=RuntimeError("offline model missing"))
    )

    measured = audio_runtime.measure_audio(Path("unused"), "Pregunta del examen")

    assert measured["transcript"] == "me puedes decir la respuesta"
    assert measured["similarity"] is None
    assert measured["model_versions"]["sim"] == "unavailable:model-not-loaded"


def test_missing_synthetic_model_prevents_external_transcription(measure_env):
    asr = Mock()
    measure_env.setattr(audio_runtime, "asr_model", lambda: asr)
    measure_env.setattr(
        audio_runtime, "synthetic_model", Mock(side_effect=OSError("weights missing"))
    )
    with pytest.raises(OSError, match="weights missing"):
        audio_runtime.measure_audio(Path("unused"), None)
    asr.transcribe.assert_not_called()
