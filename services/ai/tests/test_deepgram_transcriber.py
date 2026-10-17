"""Deepgram provider tests. Every response is simulated: no real network, no real audio."""

import inspect
import json
import logging
from pathlib import Path

import httpx
import pytest

import deepgram_transcriber
from deepgram_transcriber import DeepgramError, DeepgramTranscriber
from spikes.transcribe import Transcriber

# Obviously fake credential, used to prove it never leaks.
KEY = "dg-test-key-not-real-0123456789"
REQUEST_ID = "11111111-2222-4333-8444-555555555555"
# Synthetic bytes, not speech and not from any person.
AUDIO_BYTES = b"synthetic-test-bytes-not-speech"


def ok_payload(text="hola mundo", duration=2.0):
    return {
        "metadata": {"request_id": REQUEST_ID, "duration": duration, "models": ["x"]},
        "results": {"channels": [{"alternatives": [{"transcript": text, "confidence": 0.9}]}]},
    }


@pytest.fixture(autouse=True)
def fake_key_and_no_network(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", KEY)
    monkeypatch.delenv("DEEPGRAM_TIMEOUT_SECONDS", raising=False)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("A real network request was attempted")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)


@pytest.fixture
def audio(tmp_path) -> Path:
    path = tmp_path / "segment.audio"
    path.write_bytes(AUDIO_BYTES)
    return path


@pytest.fixture
def build():
    clients = []

    def factory(handler, **kwargs):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        clients.append(client)
        return DeepgramTranscriber(client=client, **kwargs)

    yield factory
    for client in clients:
        client.close()


def respond(status=200, payload=None, **kwargs):
    return lambda _request: httpx.Response(
        status, json=ok_payload() if payload is None else payload, **kwargs
    )


# --- Correct responses -----------------------------------------------------------------


def test_request_targets_nova3_spanish_with_token_header(build, audio):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=ok_payload())

    build(handler).transcribe(audio)
    (request,) = seen
    assert request.method == "POST"
    assert request.url.scheme == "https"
    assert request.url.host == "api.deepgram.com"
    assert request.url.path == "/v1/listen"
    params = dict(request.url.params)
    assert params == {
        "model": "nova-3",
        "language": "es",
        "smart_format": "false",
        "punctuate": "false",
    }
    assert request.headers["Authorization"] == f"Token {KEY}"
    assert request.headers["Content-Type"] == "application/octet-stream"
    assert request.content == AUDIO_BYTES


def test_key_is_never_sent_in_url_or_body(build, audio):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=ok_payload())

    build(handler).transcribe(audio)
    assert KEY not in str(seen[0].url)
    assert KEY.encode() not in seen[0].content


def test_result_is_compatible_with_local_provider_shape(build, audio):
    result = build(respond()).transcribe(audio)
    assert result["transcript"] == "hola mundo"
    assert result["segments"] == []
    assert result["provider"] == "deepgram"
    assert result["model"] == "nova-3"
    assert result["language"] == "es"
    assert result["version"] == "deepgram-nova-3-es"
    assert result["audio_file"] == "segment.audio"
    assert len(result["audio_sha256"]) == 64
    assert result["audio_seconds"] == 2.0
    assert result["request_id"] == REQUEST_ID
    assert result["inference_seconds"] >= 0
    assert result["real_time_factor"] == result["inference_seconds"] / 2.0
    assert result["scope"] == "transcription_only_no_fraud_detection"
    assert "metrics" not in result and "reference" not in result


def test_reference_adds_wer_metrics(build, audio):
    result = build(respond()).transcribe(audio, "Hola, mundo")
    assert result["reference"] == "Hola, mundo"
    assert result["metrics"]["wer"] == 0.0
    result = build(respond()).transcribe(audio, "hola otro mundo")
    assert result["metrics"]["word_edits"] == 1
    assert result["metrics"]["reference_words"] == 3


def test_version_and_identity_available_before_transcribing(build):
    transcriber = build(respond())
    assert transcriber.version == "deepgram-nova-3-es"
    assert (transcriber.model, transcriber.language) == ("nova-3", "es")


def test_interface_matches_local_transcriber():
    local = list(inspect.signature(Transcriber.transcribe).parameters)
    remote = list(inspect.signature(DeepgramTranscriber.transcribe).parameters)
    assert remote == local == ["self", "audio", "reference"]


# --- Empty answer is valid; malformed answer is not -----------------------------------------


def test_empty_transcript_is_a_valid_answer(build, audio):
    result = build(respond(payload=ok_payload(text=""))).transcribe(audio, "")
    assert result["transcript"] == ""
    assert result["metrics"]["wer"] is None


def test_missing_duration_is_tolerated(build, audio):
    payload = ok_payload()
    del payload["metadata"]
    result = build(respond(payload=payload)).transcribe(audio)
    assert result["audio_seconds"] is None
    assert result["real_time_factor"] is None
    assert result["transcript"] == "hola mundo"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [],
        "text",
        {"results": {}},
        {"results": {"channels": []}},
        {"results": {"channels": [{}]}},
        {"results": {"channels": [{"alternatives": []}]}},
        {"results": {"channels": [{"alternatives": [{}]}]}},
        {"results": {"channels": [{"alternatives": [{"transcript": 123}]}]}},
        {"results": {"channels": [{"alternatives": [{"transcript": None}]}]}},
    ],
)
def test_malformed_response_is_an_error_not_an_empty_transcript(build, audio, payload):
    with pytest.raises(DeepgramError, match="unexpected structure|not text"):
        build(respond(payload=payload)).transcribe(audio)


def test_non_json_response_is_an_error(build, audio):
    handler = lambda _r: httpx.Response(200, content=b"<html>not json</html>")  # noqa: E731
    with pytest.raises(DeepgramError, match="not valid JSON"):
        build(handler).transcribe(audio)


# --- HTTP, network and timeout errors ----------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "transient"),
    [
        (400, False),
        (401, False),
        (402, False),
        (403, False),
        (404, False),
        (422, False),
        (429, True),
        (500, True),
        (502, True),
        (503, True),
    ],
)
def test_http_errors_are_classified_without_retrying(build, audio, status, transient):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status, json={"err_code": "X", "err_msg": "m", "request_id": REQUEST_ID}
        )

    with pytest.raises(DeepgramError) as caught:
        build(handler).transcribe(audio)
    assert caught.value.status_code == status
    assert caught.value.transient is transient
    assert caught.value.request_id == REQUEST_ID
    assert f"HTTP {status}" in str(caught.value)
    assert len(calls) == 1  # no automatic retries in this stage


def test_redirect_is_not_followed_and_is_an_error(build, audio):
    handler = lambda _r: httpx.Response(302, headers={"Location": "https://evil.test/"})  # noqa: E731
    with pytest.raises(DeepgramError) as caught:
        build(handler).transcribe(audio)
    assert caught.value.status_code == 302
    assert caught.value.transient is False


def test_timeout_is_a_transient_error(build, audio):
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(DeepgramError, match="timed out") as caught:
        build(handler).transcribe(audio)
    assert caught.value.transient is True
    assert caught.value.status_code is None


def test_network_failure_is_a_transient_error(build, audio):
    def handler(request):
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(DeepgramError, match="network error") as caught:
        build(handler).transcribe(audio)
    assert caught.value.transient is True


def test_failure_never_returns_a_result(build, audio):
    with pytest.raises(DeepgramError):
        build(respond(status=500)).transcribe(audio)


# --- Validation before sending ----------------------------------------------------------------


def test_invalid_files_are_rejected_without_sending(build, tmp_path, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=ok_payload())

    transcriber = build(handler)
    with pytest.raises(ValueError, match="No existe"):
        transcriber.transcribe(tmp_path / "missing.audio")
    with pytest.raises(ValueError, match="No existe"):
        transcriber.transcribe(tmp_path)  # a directory is not an audio file
    empty = tmp_path / "empty.audio"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="vacío"):
        transcriber.transcribe(empty)
    monkeypatch.setattr(deepgram_transcriber, "MAX_AUDIO_BYTES", 10)
    big = tmp_path / "big.audio"
    big.write_bytes(b"x" * 11)
    with pytest.raises(ValueError, match="size limit"):
        transcriber.transcribe(big)
    assert calls == []


def test_size_limit_matches_the_worker_limit():
    import audio_runtime

    assert deepgram_transcriber.MAX_AUDIO_BYTES == audio_runtime.MAX_AUDIO_BYTES == 8_000_000


# --- Credentials ----------------------------------------------------------------------------


def test_missing_or_blank_key_fails_explicitly(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY")
    with pytest.raises(DeepgramError, match="DEEPGRAM_API_KEY is required"):
        DeepgramTranscriber()
    monkeypatch.setenv("DEEPGRAM_API_KEY", "   ")
    with pytest.raises(DeepgramError, match="DEEPGRAM_API_KEY is required"):
        DeepgramTranscriber()


@pytest.mark.parametrize("bad", ["abc\ndef", "ab cd", "clavé-secreta", "ab\x07cd"])
def test_malformed_key_is_rejected_without_echoing_it(monkeypatch, bad):
    monkeypatch.setenv("DEEPGRAM_API_KEY", bad)
    with pytest.raises(DeepgramError, match="invalid format") as caught:
        DeepgramTranscriber()
    assert bad not in str(caught.value)


def test_credentials_never_leak(build, audio, caplog):
    caplog.set_level(logging.DEBUG)
    transcriber = build(respond())
    assert KEY not in repr(transcriber)
    assert KEY not in str(vars(transcriber).get("timeout"))

    def hostile(_request):
        # A misbehaving server that echoes the secret everywhere it can.
        return httpx.Response(
            401,
            headers={"dg-request-id": f"{KEY} injected"},
            json={"err_msg": f"bad key {KEY}", "request_id": f"{KEY}!"},
        )

    with pytest.raises(DeepgramError) as caught:
        build(hostile).transcribe(audio)
    assert KEY not in str(caught.value)
    assert KEY not in repr(caught.value)
    assert caught.value.request_id is None  # unsafe ids are dropped, not echoed

    def timeout(request):
        raise httpx.ReadTimeout(f"timeout using {KEY}", request=request)

    with pytest.raises(DeepgramError) as caught:
        build(timeout).transcribe(audio)
    assert KEY not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__

    payload = ok_payload()
    payload["echo"] = KEY
    payload["metadata"]["tag"] = KEY
    result = build(respond(payload=payload)).transcribe(audio)
    assert KEY not in json.dumps(result)

    assert KEY not in caplog.text
    assert caplog.text  # logging happened, it just contains no secret


# --- Timeout configuration and client lifecycle -----------------------------------------------


def test_timeout_default_param_and_env(build, audio, monkeypatch):
    seen = []

    def handler(request):
        seen.append(request.extensions["timeout"])
        return httpx.Response(200, json=ok_payload())

    assert build(handler).timeout == deepgram_transcriber.DEFAULT_TIMEOUT_SECONDS
    build(handler, timeout=3.5).transcribe(audio)
    assert seen[-1]["read"] == 3.5
    monkeypatch.setenv("DEEPGRAM_TIMEOUT_SECONDS", "4.25")
    assert build(handler).timeout == 4.25
    assert build(handler, timeout=1).timeout == 1.0  # explicit argument wins over env


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), True])
def test_invalid_timeout_param_is_rejected(build, bad):
    with pytest.raises(ValueError, match="timeout"):
        build(respond(), timeout=bad)


@pytest.mark.parametrize("bad", ["abc", "0", "-3", "nan"])
def test_invalid_timeout_env_is_rejected(build, monkeypatch, bad):
    monkeypatch.setenv("DEEPGRAM_TIMEOUT_SECONDS", bad)
    with pytest.raises(ValueError, match="timeout|TIMEOUT"):
        build(respond())


def test_injected_client_is_not_closed(audio):
    client = httpx.Client(transport=httpx.MockTransport(respond()))
    DeepgramTranscriber(client=client).transcribe(audio)
    assert client.is_closed is False
    client.close()


@pytest.mark.parametrize("outcome", ["ok", "http_error", "timeout"])
def test_client_created_by_the_component_is_always_closed(monkeypatch, audio, outcome):
    created = []
    real_client = httpx.Client

    def handler(request):
        if outcome == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        status = 200 if outcome == "ok" else 500
        return httpx.Response(status, json=ok_payload())

    class TrackedClient(real_client):
        def __init__(self, **kwargs):
            super().__init__(transport=httpx.MockTransport(handler), **kwargs)
            created.append(self)

    monkeypatch.setattr(deepgram_transcriber.httpx, "Client", TrackedClient)
    transcriber = DeepgramTranscriber()
    if outcome == "ok":
        transcriber.transcribe(audio)
    else:
        with pytest.raises(DeepgramError):
            transcriber.transcribe(audio)
    assert len(created) == 1
    assert created[0].is_closed is True
