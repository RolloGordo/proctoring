"""RQ jobs used only to probe worker timeouts and crash recovery in E2E compose."""

from __future__ import annotations

import os
import resource
import time
from pathlib import Path

from redis import Redis


def hang(seconds: int = 30) -> str:
    time.sleep(seconds)
    return "unexpectedly-finished"


def crash_once(key: str) -> str:
    redis = Redis.from_url(os.environ["REDIS_URL"])
    if redis.set(key, "crashed", nx=True):
        os._exit(42)
    return "recovered-after-restart"


def noop() -> str:
    return "recovered"


def analyze_with_forced_fallback(event_id: str) -> object:
    """Run the real worker task while making only the model's decode fail once."""
    import parakeet_transcriber
    import tasks

    original = parakeet_transcriber.ParakeetTranscriber.transcribe

    def fail_decode(self: object, *_args: object, **_kwargs: object) -> object:
        raise parakeet_transcriber.ParakeetRuntimeError("forced fallback measurement")

    setattr(parakeet_transcriber.ParakeetTranscriber, "transcribe", fail_decode)
    try:
        result = tasks.analyze_audio(event_id)
    finally:
        setattr(parakeet_transcriber.ParakeetTranscriber, "transcribe", original)
    cgroup_peak = int(Path("/sys/fs/cgroup/memory.peak").read_text().strip())
    rss_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    Path("/tmp/forced-fallback-memory.json").write_text(
        __import__("json").dumps(
            {"cgroup_memory_peak_bytes": cgroup_peak, "worker_process_rss_hwm_bytes": rss_peak}
        )
    )
    return result


def analyze_with_process_rss(event_id: str) -> dict[str, int]:
    """Run the real API/storage task and return only process RSS high-water data."""
    import tasks

    tasks.analyze_audio(event_id)
    return {
        "worker_pid": os.getpid(),
        "worker_process_rss_hwm_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }
