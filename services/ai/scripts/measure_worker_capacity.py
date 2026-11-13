#!/usr/bin/env python3
"""Measure scaled worker-bench RQ processes while sampling Docker memory."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "-f", "docker-compose.vps.yml", "--profile", "e2e"]


def memory_bytes(raw: str | None) -> int | None:
    if not raw:
        return None
    match = re.match(r"\s*([0-9.]+)\s*([KMGT]?i?B)", raw)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    power = {"B": 0, "KB": 1, "MB": 2, "GB": 3, "TB": 4, "KiB": 1, "MiB": 2, "GiB": 3, "TiB": 4}[
        unit
    ]
    base = 1024 if "i" in unit else 1000
    return int(value * base**power)


def run(
    cmd: list[str], env: dict[str, str], timeout: int = 1800
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processes", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--jobs", type=int, default=30)
    parser.add_argument("--cpu-quota", type=float, required=True)
    parser.add_argument("--simple", action="store_true")
    parser.add_argument("--mixed-fallback", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    env = os.environ.copy()
    env["WORKER_CPU_QUOTA"] = str(args.cpu_quota)
    env["WORKER_USE_SIMPLE_WORKER"] = str(args.simple).lower()
    prep = run(COMPOSE + ["up", "-d", "redis", "api-sim", "storage-sim"], env)
    if prep.returncode:
        raise SystemExit(prep.stderr)
    scale = run(
        COMPOSE
        + [
            "up",
            "-d",
            "--force-recreate",
            "--scale",
            f"worker-bench={args.processes}",
            "worker-bench",
        ],
        env,
    )
    if scale.returncode:
        raise SystemExit(scale.stderr)
    time.sleep(8)
    started = time.monotonic()
    if args.mixed_fallback:
        runner_cmd = COMPOSE + [
            "run",
            "--rm",
            "--entrypoint",
            "python",
            "e2e-runner",
            "/opt/enqueue_mixed_e2e.py",
            "--normal",
            str(args.jobs - 1),
        ]
    else:
        runner_cmd = COMPOSE + [
            "run",
            "--rm",
            "e2e-runner",
            "--jobs",
            str(args.jobs),
            "--timeout",
            "1500",
        ]
    proc = subprocess.Popen(
        runner_cmd, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    samples: list[dict[str, Any]] = []
    all_memory_samples: list[dict[str, int]] = []
    while proc.poll() is None:
        stats = run(["docker", "stats", "--no-stream", "--format", "{{json .}}"], env, timeout=30)
        if stats.returncode == 0:
            for line in stats.stdout.splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                name = row.get("Name", "")
                current = memory_bytes(row.get("MemUsage"))
                if current is not None:
                    all_memory_samples.append(
                        {
                            "elapsed_millis": int((time.monotonic() - started) * 1000),
                            "memory_current_bytes": current,
                        }
                    )
                if "worker-bench" in name:
                    samples.append(
                        {
                            "elapsed_seconds": time.monotonic() - started,
                            "name": name,
                            "memory_usage": row.get("MemUsage"),
                            "memory_current_bytes": current,
                            "cpu_percent": row.get("CPUPerc"),
                        }
                    )
        time.sleep(0.5)
    stdout, stderr = proc.communicate()
    elapsed = time.monotonic() - started
    if proc.returncode:
        raise SystemExit(f"runner failed: {stderr}\n{stdout}")
    summary = json.loads(stdout.strip().splitlines()[-1])
    payload_path = Path(tempfile.gettempdir()) / "phase32-worker-api-results.json"
    copy = run(["docker", "cp", "ai-api-sim-1:/state/results.json", str(payload_path)], env)
    job_ms: list[int] = []
    if copy.returncode == 0 and payload_path.exists():
        api_results = json.loads(payload_path.read_text()).get("results", [])
        by_id = {row["event_id"]: row["payload"].get("processing_ms") for row in api_results}
        job_ms = [
            int(by_id[event_id])
            for event_id in summary.get("event_ids", [])
            if by_id.get(event_id) is not None
        ]
    ordered_ms = sorted(job_ms[1:])

    def percentile(q: float) -> float | None:
        if not ordered_ms:
            return None
        pos = (len(ordered_ms) - 1) * q
        low = int(pos)
        high = min(low + 1, len(ordered_ms) - 1)
        return ordered_ms[low] * (1 - (pos - low)) + ordered_ms[high] * (pos - low)

    names = [row["name"] for row in samples]
    unique_names = sorted(set(names))
    worker_current_by_sample: dict[int, int] = {}
    for row in samples:
        key = round(float(row["elapsed_seconds"]) * 2)  # Docker stats cadence: 0.5 s.
        worker_current_by_sample[key] = worker_current_by_sample.get(key, 0) + int(
            row["memory_current_bytes"] or 0
        )
    cgroup_peaks: dict[str, int] = {}
    for name in unique_names:
        value = run(["docker", "exec", name, "cat", "/sys/fs/cgroup/memory.peak"], env, timeout=10)
        if value.returncode == 0:
            cgroup_peaks[name] = int(value.stdout.strip())
    out = {
        "processes": args.processes,
        "jobs": args.jobs,
        "cpu_quota_per_worker": args.cpu_quota,
        "mode": "SimpleWorker" if args.simple else "RQ Worker with fork",
        "mixed_forced_fallback": args.mixed_fallback,
        "batch_seconds": elapsed,
        "jobs_per_minute": args.jobs / elapsed * 60,
        "job_runner": summary,
        "api_processing_ms": {
            "sample_count": len(job_ms),
            "first_enqueued_job_ms": job_ms[0] if job_ms else None,
            "subsequent_sample_count": len(ordered_ms),
            "subsequent_p50_ms": percentile(0.5) if ordered_ms else None,
            "subsequent_p90_ms": percentile(0.9) if ordered_ms else None,
            "all_samples_ms": job_ms,
        },
        "cgroup_peak_bytes_by_worker": cgroup_peaks,
        "docker_stats_samples": samples,
        "docker_stats_sample_count": len(samples),
        "worker_aggregate_peak_current_bytes": max(worker_current_by_sample.values(), default=None),
        "all_docker_memory_sample_count": len(all_memory_samples),
        "worker_container_names_seen": unique_names,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: out[key]
                for key in (
                    "processes",
                    "jobs",
                    "mode",
                    "batch_seconds",
                    "jobs_per_minute",
                    "api_processing_ms",
                    "cgroup_peak_bytes_by_worker",
                )
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
