#!/usr/bin/env python3
"""Exercise pinned-model config failures, empty output, and real local fallback."""

from __future__ import annotations

import json
import os
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np

import audio_runtime
from parakeet_transcriber import (
    ParakeetConfigurationError,
    ParakeetRuntimeError,
    validate_parakeet_installation,
)


def check_config(label: str, model_dir: Path) -> dict[str, Any]:
    os.environ["PARAKEET_MODEL_DIR"] = str(model_dir)
    try:
        validate_parakeet_installation(model_dir, "fp32", 4)
        raise AssertionError(f"{label}: expected configuration error")
    except ParakeetConfigurationError as exc:
        return {"probe": label, "result": "expected_configuration_error", "error": str(exc)}


def main() -> int:
    os.environ.pop("DEEPGRAM_API_KEY", None)
    os.environ["ASR_PROVIDER"] = "parakeet"
    os.environ["ASR_FALLBACK_PROVIDER"] = "faster-whisper"
    results: list[dict[str, Any]] = []
    model_dir = Path(os.environ["PARAKEET_MODEL_DIR"])
    results.append(check_config("missing-directory", model_dir / "absent"))
    results.append(check_config("incorrect-directory", Path("/models/not-parakeet")))
    with tempfile.TemporaryDirectory(prefix="bad-parakeet-hash-") as temp:
        bad_dir = Path(temp)
        for filename in (
            "encoder.onnx",
            "encoder.weights",
            "decoder.onnx",
            "joiner.onnx",
            "tokens.txt",
        ):
            source = model_dir / filename
            (bad_dir / filename).symlink_to(source)
        (bad_dir / "tokens.txt").unlink()
        (bad_dir / "tokens.txt").write_text("corrupt test file\n")
        results.append(check_config("incorrect-hash", bad_dir))

    os.environ["PARAKEET_MODEL_DIR"] = str(model_dir)
    with tempfile.TemporaryDirectory(prefix="empty-audio-") as temp:
        silent = Path(temp) / "silence.wav"
        with wave.open(str(silent), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(16_000)
            out.writeframes(np.zeros(16_000 * 2, dtype="<i2").tobytes())
        empty = audio_runtime.measure_audio(silent, None)
        results.append(
            {
                "probe": "empty-output",
                "result": "low_confidence" if not empty["transcript"] else "nonempty",
                "quality_status": empty["model_versions"].get("asr_quality_status"),
                "quality_reasons": empty["model_versions"].get("asr_quality_reasons"),
            }
        )
        from parakeet_transcriber import ParakeetTranscriber

        original_transcribe = ParakeetTranscriber.transcribe

        def force_runtime_failure(self: Any, *_args: Any, **_kwargs: Any) -> Any:
            raise ParakeetRuntimeError("simulated native decode failure")

        ParakeetTranscriber.transcribe = force_runtime_failure  # type: ignore[method-assign]
        try:
            fallback = audio_runtime.measure_audio(silent, None)
        finally:
            ParakeetTranscriber.transcribe = original_transcribe  # type: ignore[method-assign]
    results.append(
        {
            "probe": "parakeet-runtime-failure",
            "result": "local-fallback"
            if "fallback_from=parakeet" in fallback["model_versions"]["asr"]
            else "failed",
            "asr_version": fallback["model_versions"]["asr"],
            "deepgram_api_key_present": bool(os.getenv("DEEPGRAM_API_KEY")),
            "cgroup_memory_peak_bytes": int(Path("/sys/fs/cgroup/memory.peak").read_text().strip()),
            "rss_hwm_bytes": int(
                next(
                    line.split()[1]
                    for line in Path("/proc/self/status").read_text().splitlines()
                    if line.startswith("VmHWM:")
                )
            )
            * 1024,
        }
    )
    print(
        json.dumps(
            {"probes": results, "deepgram_api_key_present": bool(os.getenv("DEEPGRAM_API_KEY"))},
            sort_keys=True,
        )
    )
    return (
        0
        if all(
            row["result"] in {"expected_configuration_error", "low_confidence", "local-fallback"}
            for row in results
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
