"""Etapa 2A: Medición de precarga en worker_stub.py frente al fork por trabajo de RQ.

Mide y compara en un contenedor Docker real (--memory=2g --memory-swap=2g, con
--cpus=1 y sin límite de CPU):
1. fork_no_preload (comportamiento original de rq.Worker en Linux): cada trabajo
   se ejecuta en un proceso hijo creado con os.fork() y las cachés @lru_cache de
   SimilarityModel y _local_asr_model empiezan vacías (currsize=0) en cada hijo.
2. fork_preload_similarity (rq.Worker con os.fork() + precargar_modelos(fork_worker=True)):
   SimilarityModel (~1.1 GiB) se precarga en el proceso padre con OMP_NUM_THREADS=1
   y los hijos lo heredan en Copy-on-Write (sim_cache_hits_at_start=1), mientras que
   CTranslate2 (faster-whisper) se inicializa en el hijo porque su pool C++
   (ctranslate2::ReplicaPool, que crea un std::thread en __init__) no sobrevive a
   os.fork().
3. simple_worker_preload_both (rq.SimpleWorker con WORKER_USE_SIMPLE_WORKER=true +
   precargar_modelos(fork_worker=False)): tanto SimilarityModel como faster-whisper
   se precargan en el proceso del worker y los trabajos se ejecutan sin os.fork(),
   eliminando toda recarga por trabajo (asr_cache_hits_at_start=1 y
   sim_cache_hits_at_start=1).

Guarda resultados en services/ai/results/worker-preload-benchmark.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
import wave
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

AI_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_DIR.parents[1]
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from spikes.synthetic_voice import decode_audio  # noqa: E402
from spikes.transcribe import save_json  # noqa: E402

OUTPUT_PATH = AI_DIR / "results" / "worker-preload-benchmark.json"
SOURCE_AUDIO = AI_DIR / "datasets" / "stage_a_own" / "audio" / "Audio1-base.m4a"
QUESTION = (
    "¿Cuál es la diferencia entre una variable local y una variable global en un programa? "
    "Explica en qué parte del código puede usarse cada una y da un ejemplo sencillo."
)

INNER_SCRIPT = """
import json
import os
import resource
import sys
from pathlib import Path
from time import perf_counter

import audio_runtime
import worker_stub

audio_path = Path(sys.argv[1])
mode = sys.argv[2]  # fork_no_preload | fork_preload_similarity | simple_worker_preload_both
num_jobs = int(sys.argv[3])
question = sys.argv[4]

parent_t0 = perf_counter()
preload_info = None
if mode == "fork_preload_similarity":
    preload_info = worker_stub.precargar_modelos(fork_worker=True)
elif mode == "simple_worker_preload_both":
    preload_info = worker_stub.precargar_modelos(fork_worker=False)
parent_setup_seconds = perf_counter() - parent_t0

def read_cgroup_peak() -> int | None:
    p = Path("/sys/fs/cgroup/memory.peak")
    if p.is_file():
        try:
            return int(p.read_text().strip())
        except Exception:
            return None
    return None

jobs_results = []
for job_idx in range(1, num_jobs + 1):
    if mode == "simple_worker_preload_both":
        t_job0 = perf_counter()
        asr_cached_before = audio_runtime._local_asr_model.cache_info().currsize
        sim_cached_before = audio_runtime.similarity_model.cache_info().currsize
        out = audio_runtime.measure_audio(audio_path, question)
        job_el = perf_counter() - t_job0
        ru_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
        sim_val = (
            round(float(out["similarity"]), 4)
            if out["similarity"] is not None
            else None
        )
        jobs_results.append({
            "job": job_idx,
            "worker_pid": os.getpid(),
            "asr_cache_hits_at_start": asr_cached_before,
            "sim_cache_hits_at_start": sim_cached_before,
            "job_seconds": round(job_el, 4),
            "fork_plus_job_seconds": round(job_el, 4),
            "process_ru_maxrss_mib": round(ru_rss / (1024 * 1024), 2),
            "similarity": sim_val,
            "model_versions": out["model_versions"],
            "exit_status": 0,
        })
    else:
        r_fd, w_fd = os.pipe()
        t_fork0 = perf_counter()
        pid = os.fork()
        if pid == 0:
            os.close(r_fd)
            try:
                t_job0 = perf_counter()
                asr_cached_before = audio_runtime._local_asr_model.cache_info().currsize
                sim_cached_before = audio_runtime.similarity_model.cache_info().currsize
                out = audio_runtime.measure_audio(audio_path, question)
                job_el = perf_counter() - t_job0
                ru_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
                sim_val = (
                    round(float(out["similarity"]), 4)
                    if out["similarity"] is not None
                    else None
                )
                payload = {
                    "job": job_idx,
                    "child_pid": os.getpid(),
                    "asr_cache_hits_at_start": asr_cached_before,
                    "sim_cache_hits_at_start": sim_cached_before,
                    "job_seconds": round(job_el, 4),
                    "child_ru_maxrss_mib": round(ru_rss / (1024 * 1024), 2),
                    "similarity": sim_val,
                    "model_versions": out["model_versions"],
                }
                os.write(w_fd, json.dumps(payload).encode("utf-8"))
            finally:
                os.close(w_fd)
                os._exit(0)
        else:
            os.close(w_fd)
            raw = b""
            while True:
                chunk = os.read(r_fd, 4096)
                if not chunk:
                    break
                raw += chunk
            os.close(r_fd)
            _, status = os.waitpid(pid, 0)
            wall_el = perf_counter() - t_fork0
            data = json.loads(raw.decode("utf-8"))
            data["fork_plus_job_seconds"] = round(wall_el, 4)
            data["exit_status"] = os.waitstatus_to_exitcode(status)
            jobs_results.append(data)

parent_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
cg_peak = read_cgroup_peak()
print("BENCHMARK_RESULT:" + json.dumps({
    "mode": mode,
    "parent_setup_seconds": round(parent_setup_seconds, 4),
    "preload_details": preload_info,
    "parent_ru_maxrss_mib": round(parent_rss / (1024 * 1024), 2),
    "cgroup_peak_mib": round(cg_peak / (1024 * 1024), 2) if cg_peak else None,
    "jobs": jobs_results,
    "mean_job_seconds": round(sum(j["job_seconds"] for j in jobs_results) / len(jobs_results), 4),
}), flush=True)
"""


def _build_15s_wav(target_path: Path) -> Path:
    if target_path.is_file():
        return target_path
    import numpy as np

    target_path.parent.mkdir(parents=True, exist_ok=True)
    samples_f32 = decode_audio(SOURCE_AUDIO)
    sr = 16000
    target_samples = 15 * sr
    repeats = (target_samples // len(samples_f32)) + 2
    tiled = np.tile(samples_f32, repeats)[:target_samples]
    pcm16 = np.clip(tiled * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(target_path), "wb") as w_out:
        w_out.setnchannels(1)
        w_out.setsampwidth(2)
        w_out.setframerate(sr)
        w_out.writeframes(pcm16.tobytes())
    return target_path


def _load_env_key(name: str) -> str:
    val = os.getenv(name, "").strip()
    if val:
        return val
    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{name}="):
                return stripped.split("=", 1)[1].strip().strip("\"'")
    return ""


def run_docker_benchmark(
    *,
    provider: str,
    mode: str,
    cpus: str | None,
    num_jobs: int = 3,
    audio_host_dir: Path,
    deepgram_key: str,
) -> dict[str, Any]:
    container_name = f"preload-bench-{uuid.uuid4().hex[:8]}"
    cmd = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--memory=2g",
        "--memory-swap=2g",
    ]
    if cpus is not None:
        cmd.append(f"--cpus={cpus}")
    cmd.extend(
        [
            "-e",
            f"ASR_PROVIDER={provider}",
            "-e",
            "ASR_LOCAL_MODEL=small",
            "-e",
            f"DEEPGRAM_API_KEY={deepgram_key}",
            "-v",
            f"{AI_DIR / 'models'}:/app/models:ro",
            "-v",
            f"{AI_DIR / 'audio_runtime.py'}:/app/audio_runtime.py:ro",
            "-v",
            f"{AI_DIR / 'worker_stub.py'}:/app/worker_stub.py:ro",
            "-v",
            f"{AI_DIR / 'salud.py'}:/app/salud.py:ro",
            "-v",
            f"{AI_DIR / 'spikes' / 'transcribe.py'}:/app/spikes/transcribe.py:ro",
            "-v",
            f"{audio_host_dir}:/tmp/preload:ro",
            "proctoring-ai:prod-asr-local",
            "python",
            "-c",
            INNER_SCRIPT,
            "/tmp/preload/sample15s.wav",
            mode,
            str(num_jobs),
            QUESTION,
        ]
    )
    t0 = perf_counter()
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    wall = perf_counter() - t0
    for line in completed.stdout.splitlines():
        if line.startswith("BENCHMARK_RESULT:"):
            parsed: dict[str, Any] = json.loads(line.split("BENCHMARK_RESULT:", 1)[1])
            parsed["provider"] = provider
            parsed["cpus"] = cpus if cpus is not None else "unlimited_host"
            parsed["container_wall_seconds"] = round(wall, 4)
            return parsed
    raise RuntimeError(
        f"No BENCHMARK_RESULT found in stdout: {completed.stdout}\n{completed.stderr}"
    )


def run_startup_memory_fast_fail_check() -> list[dict[str, Any]]:
    checks = []
    for mem_limit, provider, model, expect_pass in [
        ("512m", "faster-whisper", "small", False),
        ("1g", "faster-whisper", "small", False),
        ("2g", "faster-whisper", "small", True),
        ("1g", "deepgram", "small", False),
        ("2g", "deepgram", "small", True),
    ]:
        cmd = [
            "docker",
            "run",
            "--rm",
            f"--memory={mem_limit}",
            f"--memory-swap={mem_limit}",
            "-e",
            f"ASR_PROVIDER={provider}",
            "-e",
            f"ASR_LOCAL_MODEL={model}",
            "-v",
            f"{AI_DIR / 'audio_runtime.py'}:/app/audio_runtime.py:ro",
            "-v",
            f"{AI_DIR / 'worker_stub.py'}:/app/worker_stub.py:ro",
            "-v",
            f"{AI_DIR / 'salud.py'}:/app/salud.py:ro",
            "proctoring-ai:prod-asr-local",
            "python",
            "worker_stub.py",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        combined = (res.stdout + "\n" + res.stderr).strip()
        checks.append(
            {
                "memory_limit": mem_limit,
                "asr_provider": provider,
                "asr_local_model": model,
                "expected_memory_pass": expect_pass,
                "exit_code": res.returncode,
                "failed_fast_on_memory": "Insufficient container memory" in combined,
                "log_excerpt": combined.splitlines()[-1] if combined else "",
            }
        )
    return checks


def main() -> int:
    tmp_dir = AI_DIR / "results" / "preload_tmp"
    _build_15s_wav(tmp_dir / "sample15s.wav")
    dg_key = _load_env_key("DEEPGRAM_API_KEY")

    runs = []
    for provider in ("faster-whisper", "deepgram"):
        for cpus in ("1", None):
            modes = (
                ("fork_no_preload", "fork_preload_similarity", "simple_worker_preload_both")
                if provider == "faster-whisper"
                else ("fork_no_preload", "fork_preload_similarity")
            )
            for mode in modes:
                print(
                    f"[preload] provider={provider} | cpus={cpus or 'host'} | mode={mode}...",
                    flush=True,
                )
                runs.append(
                    run_docker_benchmark(
                        provider=provider,
                        mode=mode,
                        cpus=cpus,
                        num_jobs=3,
                        audio_host_dir=tmp_dir,
                        deepgram_key=dg_key,
                    )
                )

    print("[preload] verificando fallo rápido de memoria al arrancar...", flush=True)
    fast_fail_checks = run_startup_memory_fast_fail_check()

    summaries = []
    for provider in ("faster-whisper", "deepgram"):
        for cpus in ("1", "unlimited_host"):
            no_pre = next(
                r
                for r in runs
                if r["provider"] == provider
                and r["cpus"] == cpus
                and r["mode"] == "fork_no_preload"
            )
            fork_pre = next(
                r
                for r in runs
                if r["provider"] == provider
                and r["cpus"] == cpus
                and r["mode"] == "fork_preload_similarity"
            )
            item: dict[str, Any] = {
                "provider": provider,
                "cpus": cpus,
                "fork_no_preload_mean_job_seconds": no_pre["mean_job_seconds"],
                "fork_preload_similarity_mean_job_seconds": fork_pre["mean_job_seconds"],
                "fork_preload_savings_per_job_seconds": round(
                    no_pre["mean_job_seconds"] - fork_pre["mean_job_seconds"], 4
                ),
                "fork_no_preload_cgroup_peak_mib": no_pre["cgroup_peak_mib"],
                "fork_preload_similarity_cgroup_peak_mib": fork_pre["cgroup_peak_mib"],
            }
            simple_pre = next(
                (
                    r
                    for r in runs
                    if r["provider"] == provider
                    and r["cpus"] == cpus
                    and r["mode"] == "simple_worker_preload_both"
                ),
                None,
            )
            if simple_pre is not None:
                item["simple_worker_preload_both_mean_job_seconds"] = simple_pre["mean_job_seconds"]
                item["simple_worker_savings_per_job_seconds"] = round(
                    no_pre["mean_job_seconds"] - simple_pre["mean_job_seconds"], 4
                )
                item["simple_worker_cgroup_peak_mib"] = simple_pre["cgroup_peak_mib"]
            summaries.append(item)

    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "audio_sample": "sample15s.wav (15.0s, 16kHz mono PCM, pregunta Q01)",
        "container_memory_limit": "2g (--memory=2g --memory-swap=2g)",
        "fork_reload_diagnosis": {
            "does_rq_fork_reload_models_without_preload": True,
            "ctranslate2_fork_finding": (
                "WhisperModel (CTranslate2) crea un hilo C++ en su constructor "
                "(ctranslate2::ReplicaPool, aumentando Threads de 8 a 9). POSIX os.fork() "
                "no clona hilos secundarios al proceso hijo, por lo que invocar en el hijo "
                "una instancia de WhisperModel creada en el padre bloquea indefinidamente "
                "esperando al hilo de ReplicaPool inexistente. SimilarityModel (PyTorch) "
                "con OMP_NUM_THREADS=1 sí es seguro tras os.fork()."
            ),
            "solution_implemented": (
                "En modo rq.Worker (os.fork()), precargar_modelos() precarga SimilarityModel "
                "en el proceso padre (heredado vía Copy-on-Write con sim_cache_hits_at_start=1) "
                "y deja que el hijo inicialice WhisperModel limpiamente (con salvaguarda "
                "os.register_at_fork en audio_runtime.py). En modo SimpleWorker "
                "(WORKER_USE_SIMPLE_WORKER=true, sin os.fork()), se precargan ambos modelos "
                "(asr_cache_hits_at_start=1 y sim_cache_hits_at_start=1)."
            ),
        },
        "comparison_summary": summaries,
        "runs": runs,
        "startup_memory_fast_fail_checks": fast_fail_checks,
    }
    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()
    save_json(OUTPUT_PATH, report)
    print(f"Saved {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
