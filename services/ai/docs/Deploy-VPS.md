# AI worker on a 12 GB / 6 vCPU VPS

This deploys only the AI worker. It does not change API contracts, database schema,
or repository defaults. The profile selects Parakeet FP32, local faster-whisper
small as an execution-error fallback, and ONNX int8 similarity. Deepgram remains
available in code but is disabled in this profile; no Deepgram key is needed.

The Compose allocation is capped at 10 GiB and 4 CPU cores, leaving capacity for
the host and other services. Phase 3.2 measured RQ workers with fork under a local
12 GiB / 6 CPU Docker quota: one process reached 13.64 jobs/minute with a 4.70 GB
cgroup peak; two reached 14.59 jobs/minute with 5.51 GB aggregate simultaneous
worker memory; three reached 6.89 jobs/minute with 7.65 GB aggregate peak. The
current Compose publishes one loopback health port, so the recommended supported
configuration here is **one process**. Do not use `--scale ai-worker=2` until
health ports are unique per replica. These are mock API/storage measurements,
not production SLOs. See `results/phase3.2-worker-capacity.json`.

## Prepare the VPS safely

1. Create a non-root deploy account with sudo access. Use SSH keys, disable password
   authentication and root SSH login, and restrict SSH ingress to a trusted IP.
2. Enable a host firewall. Allow SSH from the trusted IP and only the inbound ports
   actually required by the API/reverse proxy. Keep Redis private; do not expose its
   port publicly. Allow outbound HTTPS for image/model downloads.
3. Install Docker Engine and the Compose plugin from Docker's official repository.
   Add the deploy account to the `docker` group only if that access is acceptable;
   membership grants root-equivalent control. Otherwise use sudo for Docker.
4. Create `/srv/proctoring/models` owned by the runtime UID/GID 1001 and mode 0750.

## Install and configure

```sh
sudo mkdir -p /srv/proctoring/ai /srv/proctoring/models
sudo chown -R 1001:1001 /srv/proctoring/models
# Copy services/ai to /srv/proctoring/ai through the approved deployment channel.
cd /srv/proctoring/ai
cp .env.vps.example .env
chmod 600 .env
```

Edit `.env` locally on the VPS. Supply `REDIS_URL` for the existing private Redis,
`PROCTORING_API_URL` reachable from the worker, and the required Supabase/API
credentials. Use a secret manager or protected operator session; never commit `.env`
or paste credentials into deployment logs. The compose file binds health port 8080
only to localhost for a local reverse proxy or SSH tunnel.

Prepare all three local model assets under the mounted `/srv/proctoring/models`
directory. Parakeet is pinned and SHA-verified by the downloader. faster-whisper
small is the configured local execution fallback. ONNX similarity artifacts are
exported from the pinned MiniLM revision:

```sh
uv sync --extra asr-parakeet
uv run --extra asr-parakeet python scripts/download_parakeet.py \
  --precision fp32 --output /srv/proctoring/models/parakeet-fp32
uv sync --extra asr-local
uv run --extra asr-local python -c 'from faster_whisper import WhisperModel; WhisperModel("small", device="cpu", compute_type="int8", download_root="/srv/proctoring/models", local_files_only=False)'
uv sync --extra similarity --extra voice
uv run --extra similarity --extra voice python spikes/export_onnx.py \
  --source hf --out-dir /srv/proctoring/models/onnx_minilm_experiment --int8-only
chown -R 1001:1001 /srv/proctoring/models
chmod -R a-w /srv/proctoring/models
```

Build and start the worker:

```sh
docker compose -f docker-compose.vps.yml --env-file .env build
docker compose -f docker-compose.vps.yml --env-file .env up -d
```

## Connect and verify

The same host model directory is mounted read-only at `/models` and `/app/models`:
Parakeet reads `/models/parakeet-fp32`, while the ASR and similarity caches use
`/models` as their root. The worker connects to `REDIS_URL`, downloads audio using its configured storage
credentials, and posts results to `PROCTORING_API_URL` using `INTERNAL_API_TOKEN`.
Check `docker compose ... logs --tail=100 ai-worker`, then query
`http://127.0.0.1:8080/health` over SSH tunnel. Verify it reports Redis reachable,
`asr_provider=parakeet`, FP32 revision and SHA-verified model directory, memory
sufficiency, and no missing required configuration. Confirm no Deepgram key is set.

Run one RQ process with `WORKER_USE_SIMPLE_WORKER=false` and
`PARAKEET_NUM_THREADS=4`. The local cascade loads faster-whisper small only after
a Parakeet execution failure; observed combined cgroup peak while both models
were live was 3.94 GB (`results/phase3.2-failure-probes.json`). A forced fallback
inside a three worker load mix finished alongside two normal tasks; aggregate
worker memory peaked at 6.94 GB (`results/phase3.2-capacity-rq-3-fallback.json`).
The 2-process throughput trial was slightly higher, but it is not directly
deployable through the current Compose health port mapping.

RQ's crash handling put the interrupted forked job into its scheduled retry
registry, but this worker currently calls `work(with_scheduler=False)`, so
automatic retry execution after a fatal crash is not enabled. Until scheduler
or explicit requeue recovery is implemented and verified, monitor scheduled
jobs and requeue them using the operational recovery procedure. A timeout is
different: the worker parent survives and takes the next job.

Run the normal end-to-end flow using a designated test session/audio and confirm
that the transcript and `model_versions` arrive through the existing API. Do not
use real candidate audio for a deployment smoke test without the required consent.

## Transfer from Render

Keep the Render worker intact. Pause/scale it to zero only after the VPS worker is
healthy and the queue is drained or operationally coordinated. Do not delete the
Render service during the cutover. Watch queue depth, job failures, RSS/cgroup
memory, CPU, health status, and fallback/low-confidence logs. Avoid running both
workers against the same queue unintentionally because this can increase concurrent
model memory and make rollback ambiguous.

## Roll back

1. Pause the VPS worker with `docker compose ... stop ai-worker`.
2. Confirm Redis queue state and re-enable the existing Render worker.
3. Restore the prior deployment configuration/image and investigate failed jobs
   through the normal retry path.
4. Keep `/srv/proctoring/models` until rollback is complete; deleting it is not
   required. Revert only the VPS deploy change or image tag; repository defaults
   remain Deepgram / no fallback / PyTorch similarity.
