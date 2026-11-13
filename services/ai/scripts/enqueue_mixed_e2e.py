#!/usr/bin/env python3
"""Queue ordinary and forced-local-fallback jobs concurrently for an E2E probe."""

from __future__ import annotations

import argparse
import json
import time
from uuid import uuid4

from redis import Redis
from rq import Queue, Retry
from rq.job import Job


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normal", type=int, default=2)
    args = parser.parse_args()
    connection = Redis.from_url("redis://redis:6379/0")
    queue = Queue("audio", connection=connection)
    rows: list[tuple[str, str]] = []
    for force_fallback in (True, *([False] * args.normal)):
        event_id = str(uuid4())
        function = (
            "scripts.worker_fault_probe.analyze_with_forced_fallback"
            if force_fallback
            else "tasks.analyze_audio"
        )
        queue.enqueue(
            function, event_id, job_id=event_id, job_timeout=180, retry=Retry(max=1, interval=[1])
        )
        rows.append((event_id, "forced_fallback" if force_fallback else "normal"))
    deadline = time.monotonic() + 900
    statuses: dict[str, str] = {}
    while time.monotonic() < deadline:
        statuses = {
            event_id: Job.fetch(event_id, connection=connection).get_status(refresh=True).value
            for event_id, _ in rows
        }
        if all(
            status in {"finished", "failed", "stopped", "canceled"} for status in statuses.values()
        ):
            break
        time.sleep(0.5)
    result = {
        "jobs": [
            {"event_id": event_id, "kind": kind, "status": statuses.get(event_id)}
            for event_id, kind in rows
        ],
        "all_finished": all(statuses.get(event_id) == "finished" for event_id, _ in rows),
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["all_finished"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
