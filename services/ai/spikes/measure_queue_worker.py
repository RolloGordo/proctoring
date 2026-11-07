"""Benchmark del worker REAL con RQ, Redis, /health y precarga bajo límites de RAM y CPU.

Procesa 20 trabajos encolados por la cola 'audio' con audios de 15 s y 30 s
bajo límites de contenedor Docker:
- Memoria: --memory=512m --memory-swap=512m, y 1g
- CPU: --cpus=0.5, y --cpus=1
- Registra: RSS del worker, pico de cgroup, latencia p50 y p90, y estado OOM.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

AI_DIR = Path(__file__).resolve().parent.parent
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from redis import Redis  # noqa: E402
from rq import Queue  # noqa: E402

from deepgram_transcriber import API_KEY_ENV  # noqa: E402
from spikes.synthetic_voice import decode_audio  # noqa: E402

BENCH_AUDIOS_DIR = Path("/tmp/bench_audios")
BENCH_AUDIOS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_PATH = AI_DIR / "results" / "real-worker-queue-benchmark.json"

QUESTION_TEXT = (
    "¿Cuál es la diferencia entre una variable local y una variable global en un programa? "
    "Explica en qué parte del código puede usarse cada una y da un ejemplo sencillo."
)


def _load_env_key(name: str) -> str:
    val = os.environ.get(name, "")
    if val:
        return val
    env_file = AI_DIR.parent.parent / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def prepare_benchmark_audios() -> dict[str, Path]:
    audio1 = AI_DIR / "datasets" / "stage_a_own" / "audio" / "Audio1-base.m4a"
    audio2 = AI_DIR / "datasets" / "stage_a_own" / "audio" / "Audio2-base.m4a"
    audio3 = AI_DIR / "datasets" / "stage_a_own" / "audio" / "Audio3-base.m4a"

    arr = np.concatenate([decode_audio(audio1), decode_audio(audio2), decode_audio(audio3)])

    paths: dict[str, Path] = {}
    for secs in (15, 30):
        target = BENCH_AUDIOS_DIR / f"bench_{secs}s.wav"
        samples = secs * 16000
        clip = arr[:samples]
        pcm16 = np.clip(clip * 32767.0, -32768, 32767).astype("<i2").tobytes()
        with wave.open(str(target), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm16)
        paths[f"{secs}s"] = target
    return paths


def wait_for_redis(redis_url: str, timeout_s: float = 10.0) -> bool:
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout_s:
        try:
            r = Redis.from_url(redis_url)
            if r.ping():
                return True
        except Exception:
            time.sleep(0.2)
    return False


def wait_for_health(port: int, timeout_s: float = 25.0) -> dict[str, Any] | None:
    t0 = time.perf_counter()
    url = f"http://127.0.0.1:{port}/health"
    while time.perf_counter() - t0 < timeout_s:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                if resp.status == 200:
                    data = resp.read()
                    return json.loads(data.decode("utf-8"))
        except Exception:
            time.sleep(0.3)
    return None


def get_cgroup_peak(full_id: str) -> int | None:
    for path in (
        f"/sys/fs/cgroup/system.slice/docker-{full_id}.scope/memory.peak",
        f"/sys/fs/cgroup/docker/{full_id}/memory.peak",
    ):
        p = Path(path)
        if p.is_file():
            try:
                return int(p.read_text().strip())
            except Exception:
                pass
    return None


def run_benchmark_case(
    *,
    case_name: str,
    image_tag: str,
    memory_limit: str,
    cpus_limit: float | None,
    similarity_backend: str,
    asr_provider: str,
    asr_local_model: str | None = None,
    num_jobs: int = 20,
    redis_container_name: str = "bench-redis-queue",
    redis_port: int = 63799,
    worker_health_port: int = 7869,
) -> dict[str, Any]:
    print("\n========================================================")
    print(f"Iniciando caso: {case_name}")
    print(
        f"  Memoria: {memory_limit} | CPUs: {cpus_limit} | "
        f"Backend: {similarity_backend} | ASR: {asr_provider}"
    )
    print("========================================================")

    deepgram_key = _load_env_key(API_KEY_ENV)
    audio_paths = prepare_benchmark_audios()

    redis_url_for_worker = f"redis://{redis_container_name}:6379/0"
    redis_url_for_host = f"redis://127.0.0.1:{redis_port}/0"

    # Conectar cola desde host
    r_host = Redis.from_url(redis_url_for_host)
    r_host.flushall()
    q = Queue("audio", connection=r_host)

    # Preparar comando docker run para el worker
    cid_name = f"bench-worker-{case_name.lower().replace(' ', '-').replace('_', '-')}"
    subprocess.run(["docker", "rm", "-f", cid_name], capture_output=True, check=False)

    docker_cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        cid_name,
        "--network",
        "bench-net-queue",
        f"--memory={memory_limit}",
        f"--memory-swap={memory_limit}",
        "-p",
        f"{worker_health_port}:7860",
        "-v",
        f"{AI_DIR}/audio_runtime.py:/app/audio_runtime.py:ro",
        "-v",
        f"{AI_DIR}/salud.py:/app/salud.py:ro",
        "-v",
        f"{AI_DIR}/worker_stub.py:/app/worker_stub.py:ro",
        "-v",
        f"{AI_DIR}/spikes:/app/spikes:ro",
        "-v",
        f"{AI_DIR}/models:/app/models:ro",
        "-v",
        f"{BENCH_AUDIOS_DIR}:{BENCH_AUDIOS_DIR}:ro",
        "-e",
        f"REDIS_URL={redis_url_for_worker}",
        "-e",
        f"SIMILARITY_BACKEND={similarity_backend}",
        "-e",
        f"ASR_PROVIDER={asr_provider}",
        "-e",
        f"{API_KEY_ENV}={deepgram_key}",
        "-e",
        "WORKER_PRELOAD_MODELS=true",
        "-e",
        "ASR_ENFORCE_MEMORY_BUDGET=false",
    ]
    if cpus_limit is not None:
        docker_cmd.append(f"--cpus={cpus_limit}")
    if asr_local_model:
        docker_cmd.extend(["-e", f"ASR_LOCAL_MODEL={asr_local_model}"])

    docker_cmd.extend([image_tag, "python", "worker_stub.py"])

    t_start = time.perf_counter()
    run_proc = subprocess.run(docker_cmd, capture_output=True, text=True, check=False)
    if run_proc.returncode != 0:
        return {
            "case_name": case_name,
            "error": f"docker run failed: {run_proc.stderr}",
            "oom_killed": False,
        }

    cid = run_proc.stdout.strip()[:12]

    # Sondeo del endpoint /health
    health_data = wait_for_health(worker_health_port, timeout_s=15.0)

    # Verificar si murió al arrancar
    inspect_proc = subprocess.run(
        ["docker", "inspect", cid_name], capture_output=True, text=True, check=False
    )
    inspect_info = json.loads(inspect_proc.stdout)[0] if inspect_proc.stdout else {}
    full_id = inspect_info.get("Id", cid)
    state = inspect_info.get("State", {})
    if state.get("OOMKilled", False) or not state.get("Running", False):
        logs = subprocess.run(["docker", "logs", cid_name], capture_output=True, text=True).stdout
        cgroup_peak = get_cgroup_peak(full_id)
        subprocess.run(["docker", "rm", "-f", cid_name], capture_output=True, check=False)
        return {
            "case_name": case_name,
            "memory_limit": memory_limit,
            "cpus_limit": cpus_limit,
            "similarity_backend": similarity_backend,
            "asr_provider": asr_provider,
            "oom_killed": state.get("OOMKilled", False),
            "exit_code": state.get("ExitCode"),
            "cgroup_peak_bytes": cgroup_peak,
            "cgroup_peak_mib": round(cgroup_peak / (1024 * 1024), 2) if cgroup_peak else None,
            "health_reached": health_data is not None,
            "jobs_processed": 0,
            "error": "Worker terminated during startup/preload",
            "last_logs": logs.splitlines()[-5:] if logs else [],
        }

    print(f"Worker arrancado y /health respondió OK en {round(time.perf_counter() - t_start, 2)} s")

    # Encolar 20 trabajos alternando 15 s y 30 s
    import audio_runtime

    job_latencies: list[float] = []
    job_results: list[dict[str, Any]] = []

    durations = [15 if i % 2 == 0 else 30 for i in range(num_jobs)]
    print(f"Encolando {num_jobs} trabajos (10 de 15 s y 10 de 30 s)...")

    for i, secs in enumerate(durations, start=1):
        audio_file = audio_paths[f"{secs}s"]
        t_job0 = time.perf_counter()
        job = q.enqueue(audio_runtime.measure_audio, str(audio_file), QUESTION_TEXT)

        # Esperar a que termine el trabajo
        timeout_job = 60.0
        while not job.is_finished and not job.is_failed:
            time.sleep(0.05)
            if time.perf_counter() - t_job0 > timeout_job:
                break

        elapsed = time.perf_counter() - t_job0

        # Verificar si el contenedor sufrió OOM durante el trabajo
        insp = subprocess.run(["docker", "inspect", cid_name], capture_output=True, text=True)
        cur_state = json.loads(insp.stdout)[0].get("State", {})
        if cur_state.get("OOMKilled", False):
            print(f"  [!] Trabajo {i} ({secs} s): Contenedor OOMKilled tras {round(elapsed, 2)} s!")
            break

        if job.is_failed:
            print(f"  [X] Trabajo {i} ({secs} s) falló tras {round(elapsed, 2)} s: {job.exc_info}")
            break

        job_latencies.append(round(elapsed, 4))
        res = job.result or {}
        job_results.append(
            {
                "job_index": i,
                "duration_seconds": secs,
                "latency_seconds": round(elapsed, 4),
                "words": len(str(res.get("transcript", "")).split()),
                "transcript": res.get("transcript", ""),
                "similarity": res.get("similarity"),
            }
        )
        if i % 5 == 0 or i == num_jobs:
            print(
                f"  Completados {i}/{num_jobs} trabajos | Último: {secs} s en {round(elapsed, 2)} s"
            )

    # Inspección final
    final_insp = subprocess.run(["docker", "inspect", cid_name], capture_output=True, text=True)
    final_insp_info = json.loads(final_insp.stdout)[0] if final_insp.stdout else {}
    final_full_id = final_insp_info.get("Id", full_id)
    final_state = final_insp_info.get("State", {})
    oom_killed = final_state.get("OOMKilled", False)

    cgroup_peak = get_cgroup_peak(final_full_id)

    # Medir RSS del proceso worker en el contenedor si sigue vivo
    worker_rss_mib = None
    if final_state.get("Running", False):
        try:
            top_proc = subprocess.run(
                ["docker", "top", cid_name, "-o", "pid,vsz,rss,comm"],
                capture_output=True,
                text=True,
            )
            # sum rss
            rss_kb = 0
            for line in top_proc.stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 3 and parts[2].isdigit():
                    rss_kb += int(parts[2])
            if rss_kb > 0:
                worker_rss_mib = round(rss_kb / 1024.0, 2)
        except Exception:
            pass

    subprocess.run(["docker", "rm", "-f", cid_name], capture_output=True, check=False)

    p50 = float(np.percentile(job_latencies, 50)) if job_latencies else None
    p90 = float(np.percentile(job_latencies, 90)) if job_latencies else None

    return {
        "case_name": case_name,
        "memory_limit": memory_limit,
        "cpus_limit": cpus_limit,
        "similarity_backend": similarity_backend,
        "asr_provider": asr_provider,
        "asr_local_model": asr_local_model,
        "jobs_requested": num_jobs,
        "jobs_completed": len(job_latencies),
        "oom_killed": oom_killed,
        "worker_rss_mib": worker_rss_mib,
        "cgroup_peak_bytes": cgroup_peak,
        "cgroup_peak_mib": round(cgroup_peak / (1024 * 1024), 2) if cgroup_peak else None,
        "latency_p50_seconds": round(p50, 4) if p50 else None,
        "latency_p90_seconds": round(p90, 4) if p90 else None,
        "latency_min_seconds": min(job_latencies) if job_latencies else None,
        "latency_max_seconds": max(job_latencies) if job_latencies else None,
        "latency_mean_seconds": round(float(np.mean(job_latencies)), 4) if job_latencies else None,
        "health_endpoint_response": health_data,
        "jobs_summary": job_results,
    }


def main() -> int:
    # 1. Asegurar red y Redis
    subprocess.run(
        ["docker", "network", "create", "bench-net-queue"], capture_output=True, check=False
    )
    subprocess.run(["docker", "rm", "-f", "bench-redis-queue"], capture_output=True, check=False)

    redis_cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        "bench-redis-queue",
        "--network",
        "bench-net-queue",
        "-p",
        "63799:6379",
        "redis:7-alpine",
    ]
    subprocess.run(redis_cmd, check=True)
    if not wait_for_redis("redis://127.0.0.1:63799/0"):
        print("Error: Redis no respondió en 127.0.0.1:63799")
        return 1
    print("Redis de prueba listo en puerto 63799")

    matrix: list[dict[str, Any]] = [
        # 1. Deepgram + onnx-int8 en 512m (cpus=1.0)
        {
            "case_name": "deepgram_onnx_int8_512m_1cpu",
            "image_tag": "proctoring-ai:prod-asr-local",
            "memory_limit": "512m",
            "cpus_limit": 1.0,
            "similarity_backend": "onnx-int8",
            "asr_provider": "deepgram",
            "num_jobs": 20,
        },
        # 2. Deepgram + onnx-int8 en 512m (cpus=0.5)
        {
            "case_name": "deepgram_onnx_int8_512m_05cpu",
            "image_tag": "proctoring-ai:prod-asr-local",
            "memory_limit": "512m",
            "cpus_limit": 0.5,
            "similarity_backend": "onnx-int8",
            "asr_provider": "deepgram",
            "num_jobs": 20,
        },
        # 3. Deepgram + onnx-int8 en 1g (cpus=1.0)
        {
            "case_name": "deepgram_onnx_int8_1g_1cpu",
            "image_tag": "proctoring-ai:prod-asr-local",
            "memory_limit": "1g",
            "cpus_limit": 1.0,
            "similarity_backend": "onnx-int8",
            "asr_provider": "deepgram",
            "num_jobs": 20,
        },
        # 4. Deepgram + onnx-int8 en 1g (cpus=0.5)
        {
            "case_name": "deepgram_onnx_int8_1g_05cpu",
            "image_tag": "proctoring-ai:prod-asr-local",
            "memory_limit": "1g",
            "cpus_limit": 0.5,
            "similarity_backend": "onnx-int8",
            "asr_provider": "deepgram",
            "num_jobs": 20,
        },
        # 5. Whisper small + onnx-int8 en 512m (prueba de OOM esperada)
        {
            "case_name": "whisper_small_onnx_int8_512m_1cpu_oom_check",
            "image_tag": "proctoring-ai:prod-asr-local",
            "memory_limit": "512m",
            "cpus_limit": 1.0,
            "similarity_backend": "onnx-int8",
            "asr_provider": "faster-whisper",
            "asr_local_model": "small",
            "num_jobs": 2,
        },
        # 6. Whisper small + onnx-int8 en 1g (cpus=1.0)
        {
            "case_name": "whisper_small_onnx_int8_1g_1cpu",
            "image_tag": "proctoring-ai:prod-asr-local",
            "memory_limit": "1g",
            "cpus_limit": 1.0,
            "similarity_backend": "onnx-int8",
            "asr_provider": "faster-whisper",
            "asr_local_model": "small",
            "num_jobs": 6,
        },
        # 7. Torch + Deepgram en 512m (prueba de OOM esperada)
        {
            "case_name": "torch_deepgram_512m_1cpu_oom_check",
            "image_tag": "proctoring-ai:prod-asr-local",
            "memory_limit": "512m",
            "cpus_limit": 1.0,
            "similarity_backend": "torch",
            "asr_provider": "deepgram",
            "num_jobs": 2,
        },
        # 8. Torch + Deepgram en 1g (cpus=1.0)
        {
            "case_name": "torch_deepgram_1g_1cpu",
            "image_tag": "proctoring-ai:prod-asr-local",
            "memory_limit": "1g",
            "cpus_limit": 1.0,
            "similarity_backend": "torch",
            "asr_provider": "deepgram",
            "num_jobs": 6,
        },
        # 9. Deepgram + onnx-int8 en 512m (cpus=0.1)
        {
            "case_name": "deepgram_onnx_int8_512m_01cpu",
            "image_tag": "proctoring-ai:prod-asr-local",
            "memory_limit": "512m",
            "cpus_limit": 0.1,
            "similarity_backend": "onnx-int8",
            "asr_provider": "deepgram",
            "num_jobs": 6,
        },
        # 10. Deepgram + onnx-int8 en 512m (cpus=0.25)
        {
            "case_name": "deepgram_onnx_int8_512m_025cpu",
            "image_tag": "proctoring-ai:prod-asr-local",
            "memory_limit": "512m",
            "cpus_limit": 0.25,
            "similarity_backend": "onnx-int8",
            "asr_provider": "deepgram",
            "num_jobs": 6,
        },
        # 11. Whisper base + onnx-int8 en 1g (cpus=1.0)
        {
            "case_name": "whisper_base_onnx_int8_1g_1cpu",
            "image_tag": "proctoring-ai:prod-asr-local",
            "memory_limit": "1g",
            "cpus_limit": 1.0,
            "similarity_backend": "onnx-int8",
            "asr_provider": "faster-whisper",
            "asr_local_model": "base",
            "num_jobs": 6,
        },
        # 12. Whisper base + onnx-int8 en 1g (cpus=2.0)
        {
            "case_name": "whisper_base_onnx_int8_1g_2cpu",
            "image_tag": "proctoring-ai:prod-asr-local",
            "memory_limit": "1g",
            "cpus_limit": 2.0,
            "similarity_backend": "onnx-int8",
            "asr_provider": "faster-whisper",
            "asr_local_model": "base",
            "num_jobs": 6,
        },
    ]

    target_case = sys.argv[1] if len(sys.argv) > 1 else None
    if target_case:
        matrix = [c for c in matrix if target_case in c["case_name"]]
        print(f"Filtrando casos con '{target_case}': {[c['case_name'] for c in matrix]}")

    all_results = []
    for case in matrix:
        res = run_benchmark_case(**case)
        all_results.append(res)
        print(
            f"Resultado {case['case_name']}: "
            f"jobs={res.get('jobs_completed')}/{res.get('jobs_requested')} | "
            f"OOM={res.get('oom_killed')} | Peak={res.get('cgroup_peak_mib')} MiB | "
            f"p50={res.get('latency_p50_seconds')} s | p90={res.get('latency_p90_seconds')} s"
        )

    # Limpieza
    subprocess.run(["docker", "rm", "-f", "bench-redis-queue"], capture_output=True, check=False)
    subprocess.run(["docker", "network", "rm", "bench-net-queue"], capture_output=True, check=False)

    if target_case and RESULTS_PATH.is_file():
        try:
            existing = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
            existing_results = existing.get("results", [])
            existing_map = {r["case_name"]: r for r in existing_results}
            for res in all_results:
                existing_map[res["case_name"]] = res
            all_results = list(existing_map.values())
        except Exception:
            pass

    final_payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "experiment": "real_worker_queue_benchmark_20_jobs",
        "description": (
            "Benchmark por cola RQ con worker real, Redis, /health y precarga "
            "bajo límites de 512m y 1g, con 0.1, 0.25, 0.5, 1.0 y 2.0 CPUs."
        ),
        "results": all_results,
    }
    RESULTS_PATH.write_text(json.dumps(final_payload, indent=2), encoding="utf-8")
    print(f"\nBenchmark completado. Resultados guardados en {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
