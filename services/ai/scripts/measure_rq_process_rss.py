#!/usr/bin/env python3
"""Run one real RQ task and report only its process RSS high-water mark."""

from __future__ import annotations

import json
import time
from uuid import uuid4

from redis import Redis
from rq import Queue
from rq.job import Job


def main() -> int:
    connection = Redis.from_url("redis://redis:6379/0")
    event_id = str(uuid4())
    job = Queue("audio", connection=connection).enqueue(
        "scripts.worker_fault_probe.analyze_with_process_rss",
        event_id,
        job_id=event_id,
        job_timeout=180,
    )
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        job = Job.fetch(event_id, connection=connection)
        status = job.get_status(refresh=True)
        if status and status.value in {"finished", "failed", "stopped", "canceled"}:
            result = job.result if status.value == "finished" else None
            print(
                json.dumps(
                    {"job_id": event_id, "status": status.value, "process_rss": result},
                    sort_keys=True,
                )
            )
            return 0 if result else 1
        time.sleep(0.25)
    print(json.dumps({"job_id": event_id, "status": "timeout"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
