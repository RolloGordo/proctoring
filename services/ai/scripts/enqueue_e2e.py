#!/usr/bin/env python3
"""Enqueue a measured batch into the local Compose worker and verify completions."""

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
    parser.add_argument("--jobs", type=int, choices=(1, 30, 50, 200), required=True)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--force-fallback", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    redis = Redis.from_url("redis://redis:6379/0")
    queue = Queue("audio", connection=redis)
    task_name = (
        "scripts.worker_fault_probe.analyze_with_forced_fallback"
        if args.force_fallback
        else "tasks.analyze_audio"
    )
    event_ids = [str(uuid4()) for _ in range(args.jobs)]
    jobs = [
        queue.enqueue(
            task_name,
            event_id,
            job_id=event_id,
            job_timeout=180,
            retry=Retry(max=1, interval=[1]),
        )
        for event_id in event_ids
    ]
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        states = [
            Job.fetch(job.id, connection=redis).get_status(refresh=True).value for job in jobs
        ]
        if all(state in {"finished", "failed", "stopped", "canceled"} for state in states):
            break
        time.sleep(0.5)
    else:
        states = [
            Job.fetch(job.id, connection=redis).get_status(refresh=True).value for job in jobs
        ]
    counts = {state: states.count(state) for state in sorted(set(states))}
    print(
        json.dumps(
            {
                "enqueued": len(jobs),
                "event_ids": event_ids,
                "job_statuses": counts,
                "batch_seconds": time.monotonic() - started,
            },
            sort_keys=True,
        )
    )
    return 0 if counts.get("finished", 0) == len(jobs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
