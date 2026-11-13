#!/usr/bin/env python3
"""Measure cold/warm local end-to-end path under Docker CPU quotas."""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from audio_runtime import measure_audio


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * quantile
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    weight = pos - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def rss_hwm_bytes() -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) * 1024
    return 0


def cgroup_value(name: str) -> int | None:
    path = Path("/sys/fs/cgroup") / name
    try:
        raw = path.read_text().strip()
        return int(raw) if raw != "max" else None
    except (OSError, ValueError):
        return None


def run_once(source: Path, question: str) -> dict[str, Any]:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="mock-download-") as temp:
        local = Path(temp) / source.name
        shutil.copyfile(source, local)  # Simulated object-storage download.
        downloaded = time.perf_counter()
        measured = measure_audio(local, question)
        serialized = json.dumps(measured, separators=(",", ":")).encode()
        _simulated_post_bytes = len(serialized)  # Simulated HTTP POST serialization.
        posted = time.perf_counter()
    return {
        "download_seconds": downloaded - started,
        "asr_similarity_seconds": posted - downloaded,
        "end_to_end_seconds": posted - started,
        "transcript_nonempty": bool(measured["transcript"].strip()),
        "similarity_present": measured["similarity"] is not None,
        "asr_status": measured["model_versions"].get("asr_quality_status"),
        "rss_hwm_bytes": rss_hwm_bytes(),
        "cgroup_memory_current_bytes": cgroup_value("memory.current"),
        "cgroup_memory_peak_bytes": cgroup_value("memory.peak"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--warm-runs", type=int, default=20)
    args = parser.parse_args()
    runs = [run_once(args.audio, args.question) for _ in range(args.warm_runs + 1)]
    warm = [float(row["end_to_end_seconds"]) for row in runs[1:]]
    output = {
        "cpu_quota": Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
        "memory_limit_bytes": cgroup_value("memory.max"),
        "cold_first_job": runs[0],
        "warm_runs": len(warm),
        "warm_p50_seconds": percentile(warm, 0.50),
        "warm_p90_seconds": percentile(warm, 0.90),
        "warm_min_seconds": min(warm),
        "warm_max_seconds": max(warm),
        "warm_mean_seconds": statistics.fmean(warm),
        "warm_samples": warm,
        "rss_hwm_bytes": max(int(row["rss_hwm_bytes"]) for row in runs),
        "cgroup_memory_peak_bytes": max(int(row["cgroup_memory_peak_bytes"] or 0) for row in runs),
        "simulated_steps": [
            "local file copy as download",
            "measure_audio ASR+similarity",
            "JSON serialization as POST",
        ],
    }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
