import csv
import hashlib
import io
import json
import tarfile
import wave
from pathlib import Path

import pytest

from spikes import demo, download_sample
from spikes.evaluate import summarize
from spikes.metrics import word_errors

AI_ROOT = Path(__file__).resolve().parents[1]


def make_manifest(folder, content=b"test audio"):
    manifest = folder / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(["sample_id", "audio_path", "reference", "sha256"])
        writer.writerow(
            ["sample", "sample.flac", "El niño llegó.", hashlib.sha256(content).hexdigest()]
        )
    return manifest


def make_archive(name, content):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        member = tarfile.TarInfo(name)
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content))
    buffer.seek(0)
    return buffer


def test_demo_uses_manifest_reference_and_preserves_original_result(tmp_path, monkeypatch):
    manifest = make_manifest(tmp_path)
    audio = tmp_path / "sample.flac"
    audio.write_bytes(b"test audio")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "results").mkdir()
    original = tmp_path / "results/demo.json"
    original.write_bytes(b"original evidence")

    class FakeTranscriber:
        def __init__(self, model, offline):
            assert model == "base"
            assert offline is True

        def transcribe(self, path, reference):
            assert path == audio
            assert reference == "El niño llegó."
            return {
                "transcript": reference,
                "inference_seconds": 1,
                "model_load_seconds": 2,
                "metrics": word_errors(reference, reference),
            }

    monkeypatch.setattr(demo, "Transcriber", FakeTranscriber)
    assert demo.main(["--manifest", str(manifest), "--model", "base", "--offline"]) == 0
    result = json.loads((tmp_path / "results/demo-local.json").read_text(encoding="utf-8"))
    assert result["metrics"]["wer"] == 0
    assert original.read_bytes() == b"original evidence"


def test_demo_rejects_modified_audio_before_loading_model(tmp_path, monkeypatch, capsys):
    manifest = make_manifest(tmp_path)
    (tmp_path / "sample.flac").write_bytes(b"changed")

    def fail_if_loaded(*args, **kwargs):
        pytest.fail("No model should be loaded for invalid input")

    monkeypatch.setattr(demo, "Transcriber", fail_if_loaded)
    assert demo.main(["--manifest", str(manifest)]) == 1
    assert "cambió" in capsys.readouterr().err
    assert not (tmp_path / "results").exists()


def test_restore_recovers_original_audio_without_rewriting_metadata(tmp_path, monkeypatch):
    manifest = make_manifest(tmp_path)
    original = manifest.read_bytes()
    provenance = tmp_path / "provenance.json"
    provenance.write_bytes(b'{"source": "test"}\n')
    monkeypatch.setattr(
        download_sample.urllib.request,
        "urlopen",
        lambda *args, **kwargs: make_archive("ES/sample.flac", b"test audio"),
    )
    download_sample.restore_sample(tmp_path)
    assert (tmp_path / "sample.flac").read_bytes() == b"test audio"
    assert manifest.read_bytes() == original
    assert provenance.read_bytes() == b'{"source": "test"}\n'


@pytest.mark.parametrize("content", [b"test audio", b"modified"])
def test_restore_checks_existing_audio_without_network(tmp_path, monkeypatch, content):
    make_manifest(tmp_path)
    audio = tmp_path / "sample.flac"
    audio.write_bytes(content)

    def fail_if_downloaded(*args, **kwargs):
        pytest.fail("Existing audio must be checked before any download")

    monkeypatch.setattr(download_sample.urllib.request, "urlopen", fail_if_downloaded)
    if content == b"test audio":
        download_sample.restore_sample(tmp_path)
    else:
        with pytest.raises(ValueError, match="modificado"):
            download_sample.restore_sample(tmp_path)
    assert audio.read_bytes() == content


@pytest.mark.parametrize(
    ("name", "content", "error"),
    [
        ("ES/sample.flac", b"modified", "SHA-256"),
        ("ES/other.flac", b"test audio", "no contiene"),
        ("../sample.flac", b"test audio", "no contiene"),
    ],
)
def test_restore_rejects_changed_or_missing_archive_audio(
    tmp_path, monkeypatch, name, content, error
):
    manifest = make_manifest(tmp_path)
    original = manifest.read_bytes()
    monkeypatch.setattr(
        download_sample.urllib.request,
        "urlopen",
        lambda *args, **kwargs: make_archive(name, content),
    )
    with pytest.raises(ValueError, match=error):
        download_sample.restore_sample(tmp_path)
    assert not (tmp_path / "sample.flac").exists()
    assert manifest.read_bytes() == original


@pytest.mark.parametrize("model", ["base", "small"])
def test_recorded_evaluation_matches_manifest_and_recomputed_wer(model):
    manifest = AI_ROOT / "datasets/mediaspeech_es/manifest.csv"
    report = json.loads((AI_ROOT / "results/evaluation.json").read_text(encoding="utf-8"))
    assert report["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    with manifest.open(encoding="utf-8", newline="") as source:
        rows = {row["sample_id"]: row for row in csv.DictReader(source)}
    results = report["models"][model]["samples"]
    assert len(results) == len(rows) == 8
    assert {sample["sample_id"] for sample in results} == set(rows)
    for sample in results:
        row = rows[sample["sample_id"]]
        assert sample["audio_sha256"] == row["sha256"]
        assert sample["reference"] == row["reference"]
        assert sample["metrics"] == word_errors(row["reference"], sample["transcript"])
    assert report["models"][model]["summary"] == summarize(results)


def test_silence_control_can_be_recreated_from_documented_parameters():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 16000 * 3)
    result = json.loads((AI_ROOT / "results/silence.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(buffer.getvalue()).hexdigest() == result["audio_sha256"]
    assert result["reference"] == result["transcript"] == ""
    assert result["metrics"]["wer"] is None
