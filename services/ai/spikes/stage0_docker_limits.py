"""EXPERIMENTO ETAPA 0 — Medición en contenedor Docker con límites de RAM y CPU.

No modifica código de producción.
Ejecuta `audio_runtime.measure_audio` dentro de contenedores Docker reales con:
- Límites de memoria: `--memory=512m --memory-swap=512m`, `1g`, `2g`
- Límites de CPU: `--cpus=0.5`, `--cpus=1`, y sin límite de CPU
- Audios reales en español de 15,0 s y 30,0 s
- Motores: `ASR_PROVIDER=deepgram` y `ASR_PROVIDER=faster-whisper` (`small`)
Registra OOMKilled (vía `docker inspect`), código de salida, pico de RSS (`VmHWM`/`ru_maxrss`),
pico de memoria del cgroup (`memory.peak`) y latencias en frío y en caliente por etapa.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import uuid
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

AI_ROOT = Path(__file__).resolve().parent.parent
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))
os.chdir(AI_ROOT)

from deepgram_transcriber import API_KEY_ENV  # noqa: E402
from spikes.synthetic_voice import decode_audio  # noqa: E402

QUESTION_TEXT = (
    "¿Cuál es la diferencia entre una variable local y una variable global en un programa? "
    "Explica en qué parte del código puede usarse cada una y da un ejemplo sencillo."
)

INNER_CONTAINER_SCRIPT = r"""
import json
import os
import resource
import sys
from pathlib import Path
from time import perf_counter

def read_int_file(path: str) -> int | None:
    p = Path(path)
    if p.is_file():
        try:
            return int(p.read_text().strip())
        except Exception:
            return None
    return None

def proc_mem() -> dict[str, int | None]:
    vm_rss = None
    vm_hwm = None
    status = Path("/proc/self/status")
    if status.is_file():
        for line in status.read_text().splitlines():
            if line.startswith("VmRSS:"):
                vm_rss = int(line.split()[1]) * 1024
            elif line.startswith("VmHWM:"):
                vm_hwm = int(line.split()[1]) * 1024
    ru_maxrss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    cgroup_current = read_int_file("/sys/fs/cgroup/memory.current")
    cgroup_peak = read_int_file("/sys/fs/cgroup/memory.peak")
    return {
        "vm_rss_bytes": vm_rss,
        "vm_hwm_bytes": vm_hwm,
        "ru_maxrss_bytes": ru_maxrss,
        "cgroup_current_bytes": cgroup_current,
        "cgroup_peak_bytes": cgroup_peak,
    }

def emit(stage: str, **extra: object) -> None:
    payload = {"stage": stage, "memory": proc_mem(), **extra}
    print("STAGE_EVENT:" + json.dumps(payload), flush=True)

audio_path = Path(sys.argv[1])
with_similarity = sys.argv[2] == "1"
warm_runs = int(sys.argv[3])
model_override = sys.argv[4] if len(sys.argv) > 4 else ""
question = sys.argv[5] if with_similarity else None

emit("start")

import audio_runtime
from spikes.synthetic_voice import decode_audio

if model_override and model_override != "small":
    from functools import lru_cache
    from spikes.transcribe import Transcriber
    @lru_cache(maxsize=1)
    def _custom_local_asr():
        return Transcriber(model_override, offline=True)
    audio_runtime._local_asr_model = _custom_local_asr

t_total_0 = perf_counter()

t0 = perf_counter()
waveform = decode_audio(audio_path)
decode_s = perf_counter() - t0
emit("after_decode", decode_seconds=round(decode_s, 4), samples=len(waveform))

t0 = perf_counter()
asr = audio_runtime.asr_model()
asr_load_s = perf_counter() - t0
emit(
    "after_asr_load",
    asr_load_seconds=round(asr_load_s, 4),
    asr_version=getattr(asr, "version", "unknown"),
)

sim_model = None
sim_load_s = 0.0
if question:
    t0 = perf_counter()
    sim_model = audio_runtime.similarity_model()
    sim_load_s = perf_counter() - t0
    emit("after_similarity_load", similarity_load_seconds=round(sim_load_s, 4))

t0 = perf_counter()
asr_res = asr.transcribe(audio_path)
asr_infer_s = perf_counter() - t0
transcript = str(asr_res["transcript"])
emit(
    "after_asr_transcribe",
    asr_inference_seconds=round(asr_infer_s, 4),
    transcript_words=len(transcript.split()),
)

sim_score = None
sim_infer_s = 0.0
if sim_model is not None and question:
    t0 = perf_counter()
    sim_score = sim_model.score(question, transcript)
    sim_infer_s = perf_counter() - t0
    emit(
        "after_similarity_score",
        similarity_inference_seconds=round(sim_infer_s, 4),
        similarity_score=round(float(sim_score), 4),
    )

cold_total_s = perf_counter() - t_total_0
emit(
    "cold_complete",
    cold_total_seconds=round(cold_total_s, 4),
    decode_seconds=round(decode_s, 4),
    asr_load_seconds=round(asr_load_s, 4),
    similarity_load_seconds=round(sim_load_s, 4),
    asr_inference_seconds=round(asr_infer_s, 4),
    similarity_inference_seconds=round(sim_infer_s, 4),
)

warm_results = []
for i in range(warm_runs):
    tw0 = perf_counter()
    out = audio_runtime.measure_audio(audio_path, question)
    tw_el = perf_counter() - tw0
    warm_results.append({
        "run": i + 1,
        "warm_total_seconds": round(tw_el, 4),
        "similarity": round(float(out["similarity"]), 4) if out["similarity"] is not None else None,
        "model_versions": out["model_versions"],
    })
    emit("warm_run_complete", run=i + 1, warm_total_seconds=round(tw_el, 4))

emit("finished", warm_runs=warm_results)
"""


def load_deepgram_key() -> str:
    val = os.environ.get(API_KEY_ENV, "").strip()
    if val:
        return val
    for env_candidate in (
        AI_ROOT.parent.parent / ".env",
        AI_ROOT.parent / ".env",
        AI_ROOT / ".env",
    ):
        if env_candidate.is_file():
            for raw_line in env_candidate.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if line.startswith(f"{API_KEY_ENV}="):
                    parsed = line.split("=", 1)[1].strip().strip("\"'")
                    if parsed:
                        return parsed
    raise RuntimeError("DEEPGRAM_API_KEY not found in environment or .env")


def prepare_test_wavs(dir_path: Path) -> dict[str, dict[str, Any]]:
    dir_path.mkdir(parents=True, exist_ok=True)
    p1 = AI_ROOT / "datasets/stage_a_own/audio/Audio1-base.m4a"
    p2 = AI_ROOT / "datasets/stage_a_own/audio/Audio2-base.m4a"
    p3 = AI_ROOT / "datasets/stage_a_own/audio/Audio3-base.m4a"
    combined = np.concatenate([decode_audio(p1), decode_audio(p2), decode_audio(p3)])

    out: dict[str, dict[str, Any]] = {}
    for seconds in (15, 30):
        samples_count = seconds * 16000
        clip = combined[:samples_count]
        pcm16 = np.clip(clip * 32767.0, -32768, 32767).astype("<i2").tobytes()
        wav_path = dir_path / f"stage0_{seconds}s.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm16)
        out[f"{seconds}s"] = {
            "path": wav_path,
            "duration_seconds": float(seconds),
            "samples": samples_count,
            "size_bytes": wav_path.stat().st_size,
            "sha256": hashlib.sha256(wav_path.read_bytes()).hexdigest(),
        }
    return out


def build_images() -> dict[str, Any]:
    subprocess.run(
        ["docker", "build", "-t", "proctoring-ai:prod-base", "."],
        cwd=AI_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "docker",
            "build",
            "--build-arg",
            "EXTRAS=--extra similarity --extra face --extra asr-local",
            "-t",
            "proctoring-ai:prod-asr-local",
            ".",
        ],
        cwd=AI_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    sizes: dict[str, Any] = {}
    for tag in ("proctoring-ai:prod-base", "proctoring-ai:prod-asr-local"):
        res = subprocess.run(
            ["docker", "image", "inspect", tag, "--format", "{{.Size}}"],
            capture_output=True,
            text=True,
            check=True,
        )
        b = int(res.stdout.strip())
        sizes[tag] = {
            "size_bytes": b,
            "size_mb_decimal": round(b / 1_000_000, 2),
            "size_gib_binary": round(b / (1024**3), 3),
        }
    return sizes


def run_container_case(
    *,
    image: str,
    memory_limit: str,
    cpus: str | None,
    asr_provider: str,
    audio_filename: str,
    with_similarity: bool,
    warm_runs: int,
    deepgram_key: str,
    model_override: str = "small",
) -> dict[str, Any]:
    container_name = f"stage0-{uuid.uuid4().hex[:10]}"
    cmd = [
        "docker",
        "run",
        "--name",
        container_name,
        f"--memory={memory_limit}",
        f"--memory-swap={memory_limit}",
    ]
    if cpus is not None:
        cmd.append(f"--cpus={cpus}")
    cmd.extend(
        [
            "-e",
            f"ASR_PROVIDER={asr_provider}",
            "-e",
            f"{API_KEY_ENV}={deepgram_key}",
            "-v",
            f"{AI_ROOT / 'models'}:/app/models:ro",
            "-v",
            f"{AI_ROOT / 'results' / 'stage0_tmp'}:/tmp/stage0:ro",
            image,
            "python",
            "-c",
            INNER_CONTAINER_SCRIPT,
            f"/tmp/stage0/{audio_filename}",
            "1" if with_similarity else "0",
            str(warm_runs),
            model_override,
            QUESTION_TEXT,
        ]
    )

    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)

    inspect_res = subprocess.run(
        ["docker", "inspect", container_name, "--format", "{{json .State}}"],
        capture_output=True,
        text=True,
        check=True,
    )
    state = json.loads(inspect_res.stdout.strip())
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, check=False)

    events: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        if line.startswith("STAGE_EVENT:"):
            events.append(json.loads(line[len("STAGE_EVENT:") :]))

    peak_rss_bytes = 0
    peak_cgroup_bytes = 0
    for ev in events:
        mem = ev.get("memory", {})
        for k in ("vm_hwm_bytes", "ru_maxrss_bytes", "vm_rss_bytes"):
            v = mem.get(k)
            if isinstance(v, int) and v > peak_rss_bytes:
                peak_rss_bytes = v
        cg = mem.get("cgroup_peak_bytes") or mem.get("cgroup_current_bytes")
        if isinstance(cg, int) and cg > peak_cgroup_bytes:
            peak_cgroup_bytes = cg

    last_stage = events[-1]["stage"] if events else "before_python_start"
    cold_event = next((e for e in events if e["stage"] == "cold_complete"), None)
    finished_event = next((e for e in events if e["stage"] == "finished"), None)

    stderr_clean = completed.stderr.strip()
    if deepgram_key and deepgram_key in stderr_clean:
        stderr_clean = stderr_clean.replace(deepgram_key, "[REDACTED]")

    return {
        "image": image,
        "memory_limit": memory_limit,
        "cpus": cpus or "unlimited_host_8_vcpu",
        "asr_provider": asr_provider,
        "local_model": model_override if asr_provider == "faster-whisper" else None,
        "with_similarity": with_similarity,
        "audio_filename": audio_filename,
        "exit_code": state.get("ExitCode", completed.returncode),
        "oom_killed": bool(state.get("OOMKilled", False)),
        "succeeded": state.get("ExitCode", completed.returncode) == 0
        and not bool(state.get("OOMKilled", False)),
        "last_reached_stage": last_stage,
        "observed_peak_rss_bytes": peak_rss_bytes if peak_rss_bytes > 0 else None,
        "observed_peak_rss_mib": round(peak_rss_bytes / (1024 * 1024), 2)
        if peak_rss_bytes > 0
        else None,
        "observed_cgroup_peak_bytes": peak_cgroup_bytes if peak_cgroup_bytes > 0 else None,
        "observed_cgroup_peak_mib": round(peak_cgroup_bytes / (1024 * 1024), 2)
        if peak_cgroup_bytes > 0
        else None,
        "cold_timings": {
            k: v for k, v in (cold_event or {}).items() if k not in ("stage", "memory")
        }
        if cold_event
        else None,
        "warm_runs": finished_event.get("warm_runs") if finished_event else None,
        "stage_trace": events,
        "stderr_tail": stderr_clean[-400:] if stderr_clean else None,
    }


def main() -> int:
    deepgram_key = load_deepgram_key()
    tmp_dir = AI_ROOT / "results" / "stage0_tmp"
    wavs = prepare_test_wavs(tmp_dir)

    try:
        print("[stage0] Construyendo imágenes Docker...", file=sys.stderr, flush=True)
        image_sizes = build_images()

        # 1. Experimento en imagen por defecto actual (sin asr-local) para verificar comportamiento
        print("[stage0] Verificando imagen por defecto (prod-base)...", file=sys.stderr, flush=True)
        prod_base_checks = []
        for mem in ("512m", "1g", "2g"):
            prod_base_checks.append(
                run_container_case(
                    image="proctoring-ai:prod-base",
                    memory_limit=mem,
                    cpus=None,
                    asr_provider="deepgram",
                    audio_filename="stage0_15s.wav",
                    with_similarity=True,
                    warm_runs=0,
                    deepgram_key=deepgram_key,
                )
            )
        prod_base_whisper_check = run_container_case(
            image="proctoring-ai:prod-base",
            memory_limit="2g",
            cpus=None,
            asr_provider="faster-whisper",
            audio_filename="stage0_15s.wav",
            with_similarity=True,
            warm_runs=0,
            deepgram_key=deepgram_key,
        )

        # 2. Matriz principal de límites de memoria (512m, 1g, 2g)
        #    x (15s, 30s) x (deepgram, faster-whisper small)
        memory_matrix = []
        for provider in ("deepgram", "faster-whisper"):
            for duration_key in ("15s", "30s"):
                wav_name = wavs[duration_key]["path"].name
                for mem in ("512m", "1g", "2g"):
                    print(
                        f"[stage0] Memoria {mem} | provider={provider} | audio={duration_key}...",
                        file=sys.stderr,
                        flush=True,
                    )
                    res = run_container_case(
                        image="proctoring-ai:prod-asr-local",
                        memory_limit=mem,
                        cpus=None,
                        asr_provider=provider,
                        audio_filename=wav_name,
                        with_similarity=True,
                        warm_runs=1 if mem == "2g" else 0,
                        deepgram_key=deepgram_key,
                    )
                    res["audio_seconds"] = wavs[duration_key]["duration_seconds"]
                    memory_matrix.append(res)

        # 3. Pruebas adicionales de desglose para responder qué cabe en 512m y 1g
        #    (solo transcripción sin SimilarityModel, y modelos tiny/base con SimilarityModel en 1g)
        breakdown_matrix = []
        for provider, model_ov, with_sim, mem in (
            ("deepgram", "small", False, "512m"),
            ("faster-whisper", "small", False, "512m"),
            ("faster-whisper", "small", False, "1g"),
            ("faster-whisper", "tiny", False, "512m"),
            ("faster-whisper", "base", False, "512m"),
            ("faster-whisper", "tiny", True, "1g"),
            ("faster-whisper", "base", True, "1g"),
            ("faster-whisper", "tiny", True, "2g"),
            ("faster-whisper", "base", True, "2g"),
        ):
            print(
                f"[stage0] Desglose mem={mem} | {provider} ({model_ov}) | sim={with_sim}...",
                file=sys.stderr,
                flush=True,
            )
            res = run_container_case(
                image="proctoring-ai:prod-asr-local",
                memory_limit=mem,
                cpus=None,
                asr_provider=provider,
                audio_filename="stage0_30s.wav",
                with_similarity=with_sim,
                warm_runs=0,
                deepgram_key=deepgram_key,
                model_override=model_ov,
            )
            res["audio_seconds"] = 30.0
            breakdown_matrix.append(res)

        # 4. Matriz de CPU limitada (--cpus=0.5, --cpus=1, sin límite) en 2g de RAM
        cpu_matrix = []
        for provider in ("deepgram", "faster-whisper"):
            for duration_key in ("15s", "30s"):
                wav_name = wavs[duration_key]["path"].name
                for cpu_limit in ("0.5", "1", None):
                    cpu_tag = cpu_limit or "unlimited"
                    print(
                        f"[stage0] CPU={cpu_tag} | provider={provider} | audio={duration_key}...",
                        file=sys.stderr,
                        flush=True,
                    )
                    res = run_container_case(
                        image="proctoring-ai:prod-asr-local",
                        memory_limit="2g",
                        cpus=cpu_limit,
                        asr_provider=provider,
                        audio_filename=wav_name,
                        with_similarity=True,
                        warm_runs=3,
                        deepgram_key=deepgram_key,
                    )
                    res["audio_seconds"] = wavs[duration_key]["duration_seconds"]
                    cpu_matrix.append(res)

        report = {
            "schema_version": 1,
            "experiment": "stage_0_docker_memory_and_cpu_limits",
            "scope": "experiment_only_not_production_code",
            "created_at": datetime.now(UTC).isoformat(),
            "test_audios": {
                k: {key: val for key, val in v.items() if key != "path"} for k, v in wavs.items()
            },
            "images": image_sizes,
            "prod_base_default_extras_verification": {
                "deepgram_by_memory": prod_base_checks,
                "faster_whisper_without_asr_local_extra": prod_base_whisper_check,
            },
            "memory_limit_matrix": memory_matrix,
            "capacity_breakdown_matrix_30s": breakdown_matrix,
            "cpu_limit_matrix": cpu_matrix,
        }

        out_path = AI_ROOT / "results" / "stage0-docker-limits.json"
        out_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"[stage0] Guardado en {out_path}", file=sys.stderr, flush=True)
        return 0
    finally:
        for info in wavs.values():
            p = info["path"]
            if isinstance(p, Path) and p.exists():
                p.unlink()
        if tmp_dir.exists():
            try:
                tmp_dir.rmdir()
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
