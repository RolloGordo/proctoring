#!/usr/bin/env python3
"""Enqueue bounded timeout/crash probes and report final RQ job states."""

from __future__ import annotations

import argparse
import json
import time
from uuid import uuid4

from redis import Redis
from rq import Queue, Retry
from rq.job import Job
from rq.registry import StartedJobRegistry


def wait(job: Job, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job.refresh()
        status = job.get_status(refresh=True)
        if status and status.value in {"finished", "failed", "stopped", "canceled"}:
            return status.value
        time.sleep(0.25)
    return "timeout-waiting"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("timeout", "crash", "status", "requeue"), required=True)
    parser.add_argument("--job-id")
    args = parser.parse_args()
    redis = Redis.from_url("redis://redis:6379/0")
    queue = Queue("audio", connection=redis)
    if args.mode == "timeout":
        doomed = queue.enqueue("scripts.worker_fault_probe.hang", 30, job_timeout=2)
        first_status = wait(doomed, 15)
        recovery = queue.enqueue("scripts.worker_fault_probe.noop", job_timeout=10)
        second_status = wait(recovery, 30)
        print(json.dumps({"timeout_job": first_status, "post_timeout_job": second_status}))
        return 0 if first_status == "failed" and second_status == "finished" else 1
    if args.mode == "crash":
        key = f"e2e:crash-once:{uuid4()}"
        doomed = queue.enqueue(
            "scripts.worker_fault_probe.crash_once",
            key,
            job_timeout=15,
            retry=Retry(max=1, interval=[1]),
        )
        print(json.dumps({"crash_job_id": doomed.id, "retries": 1, "queued": True}))
        return 0
    if not args.job_id:
        parser.error("--job-id is required with --mode status or requeue")
    job = Job.fetch(args.job_id, connection=redis)
    if args.mode == "requeue":
        StartedJobRegistry(queue=queue, connection=redis).requeue(job)
        print(json.dumps({"job_id": job.id, "status": job.get_status(refresh=True).value}))
        return 0
    status = wait(job, 60)
    job.refresh()
    print(json.dumps({"job_id": job.id, "status": status, "result": job.result}))
    return 0 if status == "finished" and job.result == "recovered-after-restart" else 1


if __name__ == "__main__":
    raise SystemExit(main())
