#!/usr/bin/env python3
"""Measure combined Parakeet FP32 + ONNX int8 RSS for fixed audio durations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from audio_runtime import asr_model, similarity_model
from spikes.synthetic_voice import decode_audio


def rss_hwm_bytes() -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) * 1024
    return 0


def cgroup_value(name: str) -> int | None:
    try:
        value = (Path("/sys/fs/cgroup") / name).read_text().strip()
        return int(value) if value != "max" else None
    except (OSError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--seconds", choices=(15, 30), type=int, required=True)
    args = parser.parse_args()
    model = asr_model()
    sim = similarity_model()
    waveform = decode_audio(args.audio)
    samples = int(args.seconds * 16_000)
    repeated = np.resize(waveform, samples).astype(np.float32, copy=False)
    result: dict[str, Any] = model.transcribe(args.audio, waveform=repeated)
    score = sim.score(
        "¿Cuál es la diferencia entre una variable local y una global?",
        str(result["transcript"] or "respuesta vacía"),
    )
    output = {
        "duration_seconds": args.seconds,
        "source_audio": args.audio.name,
        "signal_method": "repeat and truncate decoded P02 source to target duration",
        "model_versions": {"asr": model.version, "similarity": sim.version},
        "transcript_nonempty": bool(result["transcript"]),
        "similarity_score": score,
        "rss_hwm_bytes": rss_hwm_bytes(),
        "cgroup_memory_current_bytes": cgroup_value("memory.current"),
        "cgroup_memory_peak_bytes": cgroup_value("memory.peak"),
        "cgroup_memory_limit_bytes": cgroup_value("memory.max"),
    }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
