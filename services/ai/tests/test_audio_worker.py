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
    for var in (
        "ASR_PROVIDER",
        "ASR_LOCAL_MODEL",
        "ASR_FALLBACK_PROVIDER",
        "ASR_FALLBACK_ON_EMPTY",
        "ASR_LOCAL_VAD_FILTER",
        "ASR_LOCAL_VAD_THRESHOLD",
        "ASR_MIN_WORDS_PER_SECOND",
        "ASR_MAX_NO_SPEECH_PROB",
        "ASR_MIN_AVG_LOGPROB",
        "ASR_MAX_COMPRESSION_RATIO",
        "ASR_HALLUCINATION_PHRASES",
        "ASR_LATENCY_BUDGET_SECONDS",
        "ASR_FALLBACK_MAX_TIMEOUT_SECONDS",
        "ASR_POST_ASR_RESERVE_SECONDS",
        "ASR_ENFORCE_MEMORY_BUDGET",
        "SIMILARITY_BACKEND",
        "SIMILARITY_ONNX_VOCAB",
        "DEEPGRAM_API_KEY",
        "DEEPGRAM_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(var, raising=False)

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
def test_default_provider_is_faster_whisper_100_percent_local(asr_env, local_asr, value):
    if value is not None:
        asr_env.setenv("ASR_PROVIDER", value)
    assert audio_runtime.DEFAULT_ASR_PROVIDER == "faster-whisper"
    assert audio_runtime.asr_provider() == "faster-whisper"
    assert audio_runtime.DEFAULT_ASR_LOCAL_MODEL == "small"
    assert audio_runtime.asr_local_model() == "small"
    assert audio_runtime.DEFAULT_ASR_FALLBACK_PROVIDER == "none"
    assert audio_runtime.asr_fallback_provider() == "none"
    # Sin clave de Deepgram: por defecto opera 100 % local y no exige ninguna clave
    model = audio_runtime.asr_model()
    assert model is local_asr


@pytest.mark.parametrize("value", ["faster-whisper", "Faster-Whisper", " faster-whisper "])
def test_faster_whisper_can_be_selected_explicitly(asr_env, local_asr, value):
    asr_env.setenv("ASR_PROVIDER", value)
    assert audio_runtime.asr_model() is local_asr


def test_missing_key_when_fallback_is_configured_as_deepgram(asr_env, local_asr):
    # Si se activa explicitamente el respaldo con Deepgram pero falta la clave, falla de inmediato
    asr_env.setenv("ASR_FALLBACK_PROVIDER", "deepgram")
    with pytest.raises(deepgram_transcriber.DeepgramError, match="DEEPGRAM_API_KEY is required"):
        audio_runtime.asr_model()
    local_asr.factory.assert_not_called()


def test_faster_whisper_without_fallback_requires_no_key(asr_env, local_asr):
    # Modo 100 % local: con ASR_FALLBACK_PROVIDER=none no se requiere DEEPGRAM_API_KEY.
    asr_env.setenv("ASR_PROVIDER", "faster-whisper")
    asr_env.setenv("ASR_FALLBACK_PROVIDER", "none")
    assert audio_runtime.asr_model() is local_asr


def test_faster_whisper_without_its_extra_fails_with_an_actionable_message(asr_env):
    real_find_spec = audio_runtime.importlib.util.find_spec

    def find_spec(name, *args, **kwargs):
        return None if name == "faster_whisper" else real_find_spec(name, *args, **kwargs)

    asr_env.setenv("ASR_PROVIDER", "faster-whisper")
    asr_env.setenv("DEEPGRAM_API_KEY", FAKE_KEY)
    asr_env.setattr(audio_runtime.importlib.util, "find_spec", find_spec)
    audio_runtime._local_asr_model.cache_clear()
    try:
        with pytest.raises(ValueError, match="uv sync --extra asr-local"):
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
    asr_env.setenv("DEEPGRAM_API_KEY", FAKE_KEY)
    asr_env.setenv("ASR_PROVIDER", "faster-whisper")
    assert audio_runtime.asr_model() is local_asr
    asr_env.setenv("ASR_PROVIDER", "deepgram")
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
    measure_env.setenv("DEEPGRAM_API_KEY", FAKE_KEY)
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
    measure_env.setenv("ASR_PROVIDER", "deepgram")
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


# --- Etapa 2A: Quality gate, cascade fallback, model selection & memory checks ---


@pytest.mark.parametrize("model_name", ["tiny", "base", "small", " SMALL "])
def test_local_model_selection_by_env_variable(asr_env, monkeypatch, model_name):
    asr_env.setenv("DEEPGRAM_API_KEY", FAKE_KEY)
    asr_env.setenv("ASR_PROVIDER", "faster-whisper")
    asr_env.setenv("ASR_LOCAL_MODEL", model_name)
    asr_env.setenv("ASR_LOCAL_VAD_FILTER", "true")
    asr_env.setenv("ASR_LOCAL_VAD_THRESHOLD", "0.3")
    created = []

    class FakeTranscriber:
        def __init__(self, model, offline=True, vad_filter=True, vad_parameters=None):
            self.model = model
            self.offline = offline
            self.vad_filter = vad_filter
            self.vad_parameters = vad_parameters
            self.version = f"faster-whisper-{model}-cpu-int8"
            created.append(self)

    import spikes.transcribe

    monkeypatch.setattr(spikes.transcribe, "Transcriber", FakeTranscriber)
    monkeypatch.setattr(audio_runtime.importlib.util, "find_spec", lambda _: object())
    audio_runtime._local_asr_model.cache_clear()
    try:
        inst = audio_runtime.asr_model()
        expected = model_name.strip().lower()
        assert inst.model == expected
        assert inst.vad_filter is True
        assert inst.vad_parameters == {"threshold": 0.3}
        assert inst.version == f"faster-whisper-{expected}-cpu-int8"
    finally:
        audio_runtime._local_asr_model.cache_clear()


def test_invalid_local_model_fails_without_echoing_value(asr_env):
    asr_env.setenv("ASR_PROVIDER", "faster-whisper")
    asr_env.setenv("ASR_LOCAL_MODEL", "large-v3-secret-token")
    with pytest.raises(ValueError, match="Unknown ASR_LOCAL_MODEL") as exc_info:
        audio_runtime.asr_local_model()
    assert "secret-token" not in str(exc_info.value)


def test_missing_key_with_fallback_configured_fails_immediately(asr_env, local_asr):
    asr_env.setenv("ASR_PROVIDER", "faster-whisper")
    asr_env.setenv("ASR_FALLBACK_PROVIDER", "deepgram")
    with pytest.raises(deepgram_transcriber.DeepgramError, match="DEEPGRAM_API_KEY is required"):
        audio_runtime.asr_model()
    local_asr.factory.assert_not_called()


def test_whisper_acceptable_passes_without_calling_fallback(measure_env):
    measure_env.setenv("ASR_PROVIDER", "faster-whisper")
    measure_env.setenv("ASR_FALLBACK_PROVIDER", "deepgram")
    measure_env.setenv("DEEPGRAM_API_KEY", FAKE_KEY)
    local = Transcriber.__new__(Transcriber)
    local.model = "small"
    local.transcribe = lambda _path: {  # type: ignore[method-assign]
        "transcript": "Una empresa quiere guardar los datos de sus clientes",
        "audio_seconds": 4.0,
        "words_per_second": 2.25,
        "segments": [
            {
                "start": 0.0,
                "end": 4.0,
                "text": "Una empresa quiere guardar los datos de sus clientes",
                "no_speech_prob": 0.05,
                "avg_logprob": -0.21,
                "compression_ratio": 1.30,
            }
        ],
    }
    measure_env.setattr(audio_runtime, "_local_asr_model", lambda: local)
    fb_mock = Mock()
    measure_env.setattr(audio_runtime, "_build_fallback_transcriber", fb_mock)
    measured = audio_runtime.measure_audio(Path("unused"), None)
    assert measured["transcript"] == "Una empresa quiere guardar los datos de sus clientes"
    assert measured["model_versions"]["asr"] == "faster-whisper-small-cpu-int8"
    fb_mock.assert_not_called()


def test_empty_output_marks_low_confidence_without_fallback(measure_env):
    measure_env.setenv("ASR_PROVIDER", "faster-whisper")
    measure_env.setenv("ASR_FALLBACK_PROVIDER", "deepgram")
    measure_env.setenv("DEEPGRAM_API_KEY", FAKE_KEY)
    local = Transcriber.__new__(Transcriber)
    local.model = "small"
    local.transcribe = lambda _path: {"transcript": "   ", "segments": []}  # type: ignore[method-assign]
    measure_env.setattr(audio_runtime, "_local_asr_model", lambda: local)

    fb_instance = SimpleNamespace(
        version="deepgram-nova-3-es",
        transcribe=lambda _p: {"transcript": "transcripcion de respaldo"},
    )
    timeouts = []

    def build_fb(timeout):
        timeouts.append(timeout)
        return fb_instance

    measure_env.setattr(audio_runtime, "_build_fallback_transcriber", build_fb)
    measured = audio_runtime.measure_audio(Path("unused"), None)
    assert measured["transcript"] == "   "
    assert measured["model_versions"]["asr_quality_status"] == "low_confidence"
    assert measured["model_versions"]["asr_quality_reasons"] == "empty_transcript"
    assert timeouts == []


def test_whisper_exception_triggers_deepgram_fallback(measure_env):
    measure_env.setenv("ASR_PROVIDER", "faster-whisper")
    measure_env.setenv("ASR_FALLBACK_PROVIDER", "deepgram")
    measure_env.setenv("DEEPGRAM_API_KEY", FAKE_KEY)
    local = Transcriber.__new__(Transcriber)
    local.model = "small"

    def fail_transcribe(_path):
        raise RuntimeError("CTranslate2 internal error")

    local.transcribe = fail_transcribe  # type: ignore[method-assign]
    measure_env.setattr(audio_runtime, "_local_asr_model", lambda: local)
    fb_instance = SimpleNamespace(
        version="deepgram-nova-3-es",
        transcribe=lambda _p: {"transcript": "recuperado por deepgram"},
    )
    measure_env.setattr(audio_runtime, "_build_fallback_transcriber", lambda timeout: fb_instance)
    measured = audio_runtime.measure_audio(Path("unused"), None)
    assert measured["transcript"] == "recuperado por deepgram"
    assert (
        measured["model_versions"]["asr"]
        == "deepgram-nova-3-es;fallback_from=faster-whisper-small-cpu-int8;"
        "reason=runtime_error:RuntimeError"
    )


@pytest.mark.parametrize(
    "hallucination",
    [
        "¡Suscríbete!",
        "Más información en www.marcoparet.com",
        "Subtítulos realizados por Amara.org",
    ],
)
def test_known_hallucination_marks_low_confidence_without_fallback(measure_env, hallucination):
    measure_env.setenv("ASR_PROVIDER", "faster-whisper")
    measure_env.setenv("ASR_FALLBACK_PROVIDER", "deepgram")
    measure_env.setenv("DEEPGRAM_API_KEY", FAKE_KEY)
    local = Transcriber.__new__(Transcriber)
    local.model = "small"
    local.transcribe = lambda _path: {  # type: ignore[method-assign]
        "transcript": hallucination,
        "words_per_second": 2.0,
        "segments": [
            {
                "text": hallucination,
                "no_speech_prob": 0.1,
                "avg_logprob": -0.2,
                "compression_ratio": 1.1,
            }
        ],
    }
    measure_env.setattr(audio_runtime, "_local_asr_model", lambda: local)
    fb_instance = SimpleNamespace(
        version="deepgram-nova-3-es",
        transcribe=lambda _p: {"transcript": "texto real limpio"},
    )
    measure_env.setattr(audio_runtime, "_build_fallback_transcriber", lambda timeout: fb_instance)
    measured = audio_runtime.measure_audio(Path("unused"), None)
    assert measured["transcript"] == hallucination
    assert measured["model_versions"]["asr_quality_status"] == "low_confidence"
    assert measured["model_versions"]["asr_quality_reasons"] == "hallucination_phrase"


@pytest.mark.parametrize(
    ("segment_override", "wps", "expected_reason"),
    [
        (
            {"no_speech_prob": 0.1, "avg_logprob": -0.2, "compression_ratio": 1.1},
            0.10,
            "low_words_per_second",
        ),
        (
            {"no_speech_prob": 0.75, "avg_logprob": -0.2, "compression_ratio": 1.1},
            2.0,
            "high_no_speech_prob",
        ),
        (
            {"no_speech_prob": 0.1, "avg_logprob": -0.82, "compression_ratio": 1.1},
            2.0,
            "low_avg_logprob",
        ),
        (
            {"no_speech_prob": 0.1, "avg_logprob": -0.2, "compression_ratio": 2.10},
            2.0,
            "high_compression_ratio",
        ),
    ],
)
def test_segment_quality_thresholds_only_mark_low_confidence(
    measure_env, segment_override, wps, expected_reason
):
    measure_env.setenv("ASR_PROVIDER", "faster-whisper")
    measure_env.setenv("ASR_FALLBACK_PROVIDER", "deepgram")
    measure_env.setenv("DEEPGRAM_API_KEY", FAKE_KEY)
    local = Transcriber.__new__(Transcriber)
    local.model = "small"
    local.transcribe = lambda _path: {  # type: ignore[method-assign]
        "transcript": "texto ruidoso dudoso",
        "words_per_second": wps,
        "segments": [{"text": "texto ruidoso dudoso", **segment_override}],
    }
    measure_env.setattr(audio_runtime, "_local_asr_model", lambda: local)
    fb_instance = SimpleNamespace(
        version="deepgram-nova-3-es",
        transcribe=lambda _p: {"transcript": "texto desde deepgram"},
    )
    measure_env.setattr(audio_runtime, "_build_fallback_transcriber", lambda timeout: fb_instance)
    measured = audio_runtime.measure_audio(Path("unused"), None)
    assert measured["transcript"] == "texto ruidoso dudoso"
    assert measured["model_versions"]["asr_quality_status"] == "low_confidence"
    assert measured["model_versions"]["asr_quality_reasons"] == expected_reason


def test_fallback_none_never_calls_deepgram_and_reports_empty_without_analysis(measure_env):
    measure_env.setenv("ASR_PROVIDER", "faster-whisper")
    measure_env.setenv("ASR_FALLBACK_PROVIDER", "none")
    local = Transcriber.__new__(Transcriber)
    local.model = "small"
    local.transcribe = lambda _path: {"transcript": "", "segments": []}  # type: ignore[method-assign]
    measure_env.setattr(audio_runtime, "_local_asr_model", lambda: local)
    sim_mock = Mock()
    measure_env.setattr(audio_runtime, "similarity_model", lambda: sim_mock)
    fb_mock = Mock()
    measure_env.setattr(audio_runtime, "_build_fallback_transcriber", fb_mock)

    measured = audio_runtime.measure_audio(Path("unused"), "Pregunta del examen")
    assert measured["transcript"] == ""
    assert measured["similarity"] is None
    assert measured["model_versions"]["asr"] == "faster-whisper-small-cpu-int8"
    assert measured["model_versions"]["asr_quality_status"] == "low_confidence"
    assert measured["model_versions"]["asr_quality_reasons"] == "empty_transcript"
    sim_mock.score.assert_not_called()
    fb_mock.assert_not_called()


def test_empty_output_does_not_start_deepgram_when_budget_would_be_exhausted(measure_env):
    measure_env.setenv("ASR_PROVIDER", "faster-whisper")
    measure_env.setenv("ASR_FALLBACK_PROVIDER", "deepgram")
    measure_env.setenv("DEEPGRAM_API_KEY", FAKE_KEY)
    # 10s budget - 9.0s elapsed - 1.5s reserve = -0.5s <= 0 -> skip Deepgram
    clock = iter([100.0, 109.0])
    measure_env.setattr(audio_runtime, "perf_counter", lambda: next(clock))

    local = Transcriber.__new__(Transcriber)
    local.model = "small"
    local.transcribe = lambda _path: {"transcript": "", "segments": []}  # type: ignore[method-assign]
    measure_env.setattr(audio_runtime, "_local_asr_model", lambda: local)
    sim_mock = Mock()
    measure_env.setattr(audio_runtime, "similarity_model", lambda: sim_mock)
    fb_mock = Mock()
    measure_env.setattr(audio_runtime, "_build_fallback_transcriber", fb_mock)

    measured = audio_runtime.measure_audio(Path("unused"), "Pregunta del examen")
    assert measured["transcript"] == ""
    assert measured["similarity"] is None
    assert measured["model_versions"]["asr"] == "faster-whisper-small-cpu-int8"
    assert measured["model_versions"]["asr_quality_status"] == "low_confidence"
    assert measured["model_versions"]["asr_quality_reasons"] == "empty_transcript"
    fb_mock.assert_not_called()
    sim_mock.score.assert_not_called()


def test_fallback_timeout_respects_remaining_budget_formula(asr_env):
    # min(4.5, 10.0 - elapsed - 1.5)
    assert audio_runtime.compute_fallback_timeout(2.0) == pytest.approx(4.5)
    assert audio_runtime.compute_fallback_timeout(5.5) == pytest.approx(3.0)
    assert audio_runtime.compute_fallback_timeout(8.5) == pytest.approx(0.0)
    assert audio_runtime.compute_fallback_timeout(9.0) == pytest.approx(-0.5)


def test_memory_budget_warns_by_default_and_fails_only_when_enforced(asr_env, tmp_path, caplog):
    cg_file = tmp_path / "memory.max"
    cg_file.write_text(str(512 * 1024 * 1024), encoding="utf-8")
    detected = audio_runtime.detect_memory_limit_bytes(cgroup_v2_path=cg_file)
    assert detected == 512 * 1024 * 1024

    asr_env.setenv("ASR_PROVIDER", "faster-whisper")
    asr_env.setenv("ASR_LOCAL_MODEL", "small")
    # Default: ASR_ENFORCE_MEMORY_BUDGET is false -> warns without raising RuntimeError
    warn_status = audio_runtime.enforce_memory_budget(limit_bytes=detected)
    assert warn_status["memory_sufficient"] is False
    assert warn_status["memory_enforce"] is False
    assert warn_status["warning"] is not None
    assert "Insufficient container memory" in warn_status["warning"]
    assert any("Insufficient container memory" in r.message for r in caplog.records)

    # When ASR_ENFORCE_MEMORY_BUDGET=true -> fails fast with RuntimeError
    asr_env.setenv("ASR_ENFORCE_MEMORY_BUDGET", "true")
    with pytest.raises(RuntimeError, match="Insufficient container memory"):
        audio_runtime.enforce_memory_budget(limit_bytes=detected)

    # 2 GiB passes for faster-whisper small + SimilarityModel(torch)
    ok = audio_runtime.enforce_memory_budget(limit_bytes=2048 * 1024 * 1024)
    assert ok["memory_sufficient"] is True
    assert ok["asr_mode"] == "local-only"


@pytest.mark.parametrize(
    ("sim_backend", "provider", "local_model", "limit_mib", "expected_sufficient", "expected_req"),
    [
        ("torch", "deepgram", "small", 512, False, 1280.0),
        ("torch", "deepgram", "small", 1500, True, 1280.0),
        ("torch", "faster-whisper", "tiny", 1024, False, 1500.0),
        ("torch", "faster-whisper", "small", 1536, False, 1800.0),
        ("onnx-int8", "deepgram", "small", 512, True, 384.0),
        ("onnx-int8", "faster-whisper", "tiny", 512, True, 500.0),
        ("onnx-int8", "faster-whisper", "base", 512, False, 640.0),
        ("onnx-int8", "faster-whisper", "base", 1024, True, 640.0),
        ("onnx-int8", "faster-whisper", "small", 1024, False, 1150.0),
        ("onnx-int8", "faster-whisper", "small", 2048, True, 1150.0),
        ("onnx-fp32", "deepgram", "small", 512, False, 640.0),
        ("onnx-fp32", "deepgram", "small", 1024, True, 640.0),
        ("onnx-fp32", "faster-whisper", "tiny", 1024, True, 900.0),
        ("onnx-fp32", "faster-whisper", "small", 1024, False, 1400.0),
        ("onnx-fp32", "faster-whisper", "small", 2048, True, 1400.0),
    ],
)
def test_memory_budget_depends_on_similarity_backend_and_asr_engine(
    asr_env,
    sim_backend,
    provider,
    local_model,
    limit_mib,
    expected_sufficient,
    expected_req,
):
    asr_env.setenv("SIMILARITY_BACKEND", sim_backend)
    asr_env.setenv("ASR_PROVIDER", provider)
    asr_env.setenv("ASR_LOCAL_MODEL", local_model)
    status = audio_runtime.check_memory_budget(limit_bytes=limit_mib * 1024 * 1024)
    assert status["similarity_backend"] == sim_backend
    assert status["required_memory_mib"] == pytest.approx(expected_req)
    assert status["memory_sufficient"] is expected_sufficient


@pytest.mark.parametrize("backend", ["torch", "onnx-int8", "onnx-fp32", " ONNX-INT8 "])
def test_similarity_backend_selection_and_cache(asr_env, monkeypatch, backend):
    asr_env.setenv("SIMILARITY_BACKEND", backend)
    norm = backend.strip().lower()
    assert audio_runtime.similarity_backend() == norm

    class FakeTorchSim:
        def __init__(self, revision, offline=True, cache_dir="models"):
            self.revision = revision
            self.offline = offline
            self.cache_dir = cache_dir

        def score(self, q, t):
            return 0.75

    class FakeOnnxSim:
        def __init__(self, revision, *, variant="int8", vocab_mode="es_en", offline=True, **_kw):
            self.revision = revision
            self.variant = variant
            self.vocab_mode = vocab_mode
            self.offline = offline
            self.version = f"multilingual-MiniLM-L12-v2@{revision};backend=onnx-{variant}"

        def score(self, q, t):
            return 0.74

    import spikes.similarity

    monkeypatch.setattr(spikes.similarity, "SimilarityModel", FakeTorchSim)
    monkeypatch.setattr(spikes.similarity, "OnnxSimilarityModel", FakeOnnxSim)
    monkeypatch.setattr(audio_runtime.importlib.util, "find_spec", lambda _: object())
    audio_runtime.similarity_model.cache_clear()
    try:
        inst = audio_runtime.similarity_model()
        if norm == "torch":
            assert isinstance(inst, FakeTorchSim)
        else:
            assert isinstance(inst, FakeOnnxSim)
            assert inst.variant == ("int8" if norm == "onnx-int8" else "fp32")
    finally:
        audio_runtime.similarity_model.cache_clear()


def test_invalid_similarity_backend_fails_without_echoing_secret(asr_env):
    asr_env.setenv("SIMILARITY_BACKEND", "custom-secret-key-999")
    with pytest.raises(ValueError, match="Unknown SIMILARITY_BACKEND") as exc_info:
        audio_runtime.similarity_backend()
    assert "secret-key-999" not in str(exc_info.value)
