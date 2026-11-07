"""EXPERIMENTO (Etapa A): comparación reproducible de proveedores y modelos ASR.

NOTA: Este script es un experimento de medición (spike), NO es código de producción.
Evalúa sobre el MISMO conjunto de audios en español con transcripción de referencia:
- faster-whisper: tiny, base y small (CPU, int8, 4 hilos, beam_size=5, vad_filter=True)
- Deepgram Nova-3 (solo si DEEPGRAM_API_KEY está definida en el entorno; si no, lo omite
  y deja constancia explícita sin exponer ningún secreto).

Registra en JSON:
- WER (micro y macro), ediciones, palabras de referencia e hipótesis por muestra.
- Tiempo de carga del modelo, tiempo de inferencia y factor de tiempo real (RTF).
- Pico de memoria RSS del proceso (y delta respecto del proceso base) medido en
  subprocesos aislados por candidato.
- Tamaño del modelo en disco (bytes y MiB).
- Latencia en frío y en caliente (mínimo 20 corridas por candidato cuando aplica,
  con p50, p90, min, max y media).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from typing import Any

AI_ROOT = Path(__file__).resolve().parents[1]
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from deepgram_transcriber import API_KEY_ENV, DeepgramTranscriber  # noqa: E402
from spikes.evaluate import load_manifest, summarize  # noqa: E402
from spikes.transcribe import Transcriber, save_json  # noqa: E402

LOCAL_MODELS = ("tiny", "base", "small")
MODEL_DIRS = {
    "tiny": Path("models/models--Systran--faster-whisper-tiny"),
    "base": Path("models/models--Systran--faster-whisper-base"),
    "small": Path("models/models--Systran--faster-whisper-small"),
}


def percentile(values: list[float], q: float) -> float | None:
    """Linear-interpolated percentile in [0, 100] (same method as numpy 'linear')."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * (q / 100.0)
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[low]
    weight = pos - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def latency_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"runs": 0, "p50_seconds": None, "p90_seconds": None}
    return {
        "runs": len(values),
        "p50_seconds": percentile(values, 50),
        "p90_seconds": percentile(values, 90),
        "mean_seconds": sum(values) / len(values),
        "min_seconds": min(values),
        "max_seconds": max(values),
        "all_seconds": values,
    }


def directory_size_bytes(path: Path) -> int | None:
    if not path.exists():
        return None
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file() and not f.is_symlink())


def current_peak_rss_bytes() -> int:
    """Linux ru_maxrss is in KiB; macOS is in bytes."""
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(rss)
    return int(rss) * 1024


def current_rss_bytes() -> int | None:
    status = Path("/proc/self/status")
    if status.is_file():
        for line in status.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    return None


def measure_combined_with_similarity_30s_subprocess(
    candidate: str,
    audio_a: Path,
    audio_b: Path,
    audio_c: Path,
    question: str,
    offline: bool,
) -> dict[str, Any]:
    """Measure peak RSS in a single process on a maximum-duration 30.0s audio (480,000 samples)."""
    code = (
        "import json, sys, wave; from pathlib import Path; "
        "from tempfile import TemporaryDirectory; "
        "from time import perf_counter; import numpy as np; "
        f"sys.path.insert(0, {str(AI_ROOT)!r}); "
        "from audio_runtime import SIM_REVISION; "
        "from spikes.compare_asr import current_peak_rss_bytes, current_rss_bytes; "
        "from spikes.similarity import SimilarityModel; "
        "from spikes.synthetic_voice import decode_audio; "
        "cand, p1, p2, p3, question, offline = ("
        "sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), "
        "sys.argv[5], sys.argv[6] == '1'); "
        "w = np.concatenate([decode_audio(p1), decode_audio(p2), decode_audio(p3)])[:480000]; "
        "pcm16 = np.clip(w * 32767.0, -32768, 32767).astype('<i2').tobytes(); "
        "tmp = TemporaryDirectory(); wav_path = Path(tmp.name) / 'max30s.wav'; "
        "wf = wave.open(str(wav_path), 'wb'); wf.setnchannels(1); wf.setsampwidth(2); "
        "wf.setframerate(16000); wf.writeframes(pcm16); wf.close(); "
        "del w, pcm16; "
        "rss_start = current_rss_bytes(); "
        "t0 = perf_counter(); "
        "waveform = decode_audio(wav_path); "
    )
    if candidate == "deepgram":
        code += (
            "from deepgram_transcriber import DeepgramTranscriber; asr = DeepgramTranscriber(); "
        )
    else:
        code += (
            "from spikes.transcribe import Transcriber; asr = Transcriber(cand, offline=offline); "
        )
    code += (
        "rss_after_asr_load = current_rss_bytes(); "
        "t_sim0 = perf_counter(); "
        "sim_model = SimilarityModel(SIM_REVISION, offline=offline); "
        "sim_load_s = perf_counter() - t_sim0; "
        "rss_after_both_loaded = current_rss_bytes(); "
        "res = asr.transcribe(wav_path); "
        "t_score0 = perf_counter(); "
        "sim_score = sim_model.score(question, res['transcript']); "
        "sim_infer_s = perf_counter() - t_score0; "
        "total_s = perf_counter() - t0; "
        "rss_after_infer = current_rss_bytes(); "
        "peak = current_peak_rss_bytes(); "
        "tmp.cleanup(); "
        "print(json.dumps({"
        "'audio_seconds': len(waveform) / 16000.0, "
        "'decoded_samples': len(waveform), "
        "'rss_start_bytes': rss_start, "
        "'rss_after_asr_load_bytes': rss_after_asr_load, "
        "'rss_after_both_loaded_bytes': rss_after_both_loaded, "
        "'rss_after_infer_bytes': rss_after_infer, "
        "'peak_rss_bytes': peak, "
        "'peak_rss_mib': round(peak / (1024 * 1024), 2), "
        "'asr_inference_seconds': res['inference_seconds'], "
        "'similarity_load_seconds': sim_load_s, "
        "'similarity_inference_seconds': sim_infer_s, "
        "'similarity_score': sim_score, "
        "'combined_total_seconds': total_s"
        "}))"
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            candidate,
            str(audio_a),
            str(audio_b),
            str(audio_c),
            question,
            "1" if offline else "0",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return dict(json.loads(lines[-1]))


def classify_transcript_error(reference: str, hypothesis: str, metrics: dict[str, Any]) -> str:
    """Classify each transcription outcome based on observed tokens and edits."""
    if not hypothesis.strip():
        return "empty_output"
    wer = metrics.get("wer")
    ref_words = int(metrics.get("reference_words") or 0)
    hyp_words = int(metrics.get("hypothesis_words") or 0)
    edits = int(metrics.get("word_edits") or 0)
    if wer is not None and wer == 0.0:
        return "exact_match"
    # How many reference words were matched/preserved at least by edit distance bound:
    # In Levenshtein, matched_words >= max(ref_words, hyp_words) - edits.
    min_matched = max(0, max(ref_words, hyp_words) - edits)
    if min_matched == 0 or (wer is not None and wer >= 0.90):
        return "hallucination_or_noise_substitution"
    if hyp_words < ref_words * 0.65:
        return "partial_truncated_text"
    return "partial_with_substitutions"


def diagnose_adverse_vad(stage_a_manifest: Path, offline: bool) -> dict[str, Any]:
    """Re-run ruido, bajaylejos and voz baja with vad_filter=False and lower VAD thresholds."""
    from faster_whisper import WhisperModel  # type: ignore[import-untyped]

    from spikes.metrics import normalize, word_errors

    rows = load_manifest(stage_a_manifest)
    adverse_conditions = {"ruido", "bajaylejos", "voz baja"}
    adverse_rows = [r for r in rows if r.get("condition") in adverse_conditions]

    configs: list[tuple[str, bool, dict[str, Any] | None]] = [
        ("vad_true_default_0.5", True, None),
        ("vad_true_threshold_0.3", True, {"threshold": 0.3}),
        ("vad_true_threshold_0.15", True, {"threshold": 0.15}),
        ("vad_false", False, None),
    ]

    report: dict[str, Any] = {}
    for model_name in LOCAL_MODELS:
        engine = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            cpu_threads=4,
            download_root="models",
            local_files_only=offline,
        )
        model_report: dict[str, Any] = {}
        for cfg_name, vad_flag, vad_params in configs:
            samples_out = []
            by_condition: dict[str, list[dict[str, Any]]] = {}
            for row in adverse_rows:
                audio_path = Path(row["resolved_path"])
                ref = row["reference"]
                t0 = perf_counter()
                kwargs: dict[str, Any] = {
                    "language": "es",
                    "beam_size": 5,
                    "vad_filter": vad_flag,
                    "condition_on_previous_text": False,
                }
                if vad_params is not None:
                    kwargs["vad_parameters"] = vad_params
                segments, info = engine.transcribe(str(audio_path), **kwargs)
                seg_list = [
                    {"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments
                ]
                elapsed = perf_counter() - t0
                transcript = " ".join(s["text"] for s in seg_list).strip()
                m = word_errors(ref, transcript)
                ref_set = set(normalize(ref))
                hyp_tokens = normalize(transcript)
                overlap_words = sum(1 for w in hyp_tokens if w in ref_set)
                diag = classify_transcript_error(ref, transcript, m)
                item = {
                    "sample_id": row["sample_id"],
                    "condition": row["condition"],
                    "audio_file": audio_path.name,
                    "audio_seconds": info.duration,
                    "inference_seconds": elapsed,
                    "reference": ref,
                    "transcript": transcript,
                    "metrics": m,
                    "lexical_overlap_words": overlap_words,
                    "diagnosis": diag,
                }
                samples_out.append(item)
                by_condition.setdefault(row["condition"], []).append(item)

            cond_summaries: dict[str, Any] = {}
            for cond, items in sorted(by_condition.items()):
                s = summarize(items)
                counts: dict[str, int] = {}
                for it in items:
                    d = it["diagnosis"]
                    counts[d] = counts.get(d, 0) + 1
                cond_summaries[cond] = {
                    "micro_wer": s["micro_wer"],
                    "word_edits": s["word_edits"],
                    "reference_words": s["reference_words"],
                    "diagnosis_counts": counts,
                }
            model_report[cfg_name] = {
                "vad_filter": vad_flag,
                "vad_parameters": vad_params,
                "overall_adverse_summary": summarize(samples_out),
                "by_condition": cond_summaries,
                "samples": samples_out,
            }
        report[f"faster-whisper-{model_name}"] = model_report
        del engine
    return report


UNRELATED_STATEMENT = "El autobús tardó bastante esta mañana por el tráfico en la avenida."


def evaluate_similarity_separation(candidates: dict[str, Any], offline: bool) -> dict[str, Any]:
    """Compute MiniLM similarity of each transcript vs exact reference and vs unrelated phrase."""
    from audio_runtime import SIM_REVISION
    from spikes.similarity import SimilarityModel

    sim_model = SimilarityModel(SIM_REVISION, offline=offline)
    out: dict[str, Any] = {
        "unrelated_statement": UNRELATED_STATEMENT,
        "similarity_model_revision": SIM_REVISION,
        "candidates": {},
    }

    def group_stats(items: list[dict[str, Any]]) -> dict[str, Any]:
        pos = [float(x["sim_reference"]) for x in items]
        neg = [float(x["sim_unrelated"]) for x in items]
        min_pos = min(pos)
        max_neg = max(neg)
        mean_pos = sum(pos) / len(pos)
        mean_neg = sum(neg) / len(neg)
        # Overlap: how many positive scores fall <= max_neg or negative scores >= min_pos
        overlapping_samples = [
            x["sample_id"] for x in items if float(x["sim_reference"]) <= max_neg
        ]
        return {
            "sample_count": len(items),
            "sim_reference": {
                "min": min_pos,
                "p50": percentile(pos, 50),
                "mean": mean_pos,
                "max": max(pos),
            },
            "sim_unrelated": {
                "min": min(neg),
                "p50": percentile(neg, 50),
                "mean": mean_neg,
                "max": max_neg,
            },
            "mean_separation_gap": mean_pos - mean_neg,
            "min_pos_minus_max_neg_margin": min_pos - max_neg,
            "has_overlap": min_pos <= max_neg,
            "overlapping_positive_sample_ids": overlapping_samples,
            "above_0_60_reference_count": sum(1 for v in pos if v >= 0.60),
            "above_0_60_unrelated_count": sum(1 for v in neg if v >= 0.60),
        }

    for cand_name, cand_data in candidates.items():
        cand_samples: list[dict[str, Any]] = []
        by_group: dict[str, list[dict[str, Any]]] = {}
        for ds_name, ds_data in cand_data["datasets"].items():
            for samp in ds_data["samples"]:
                transcript = samp["transcript"]
                ref = samp["reference"]
                s_ref = sim_model.score(ref, transcript)
                s_unrel = sim_model.score(UNRELATED_STATEMENT, transcript)
                if ds_name == "stage_a_own":
                    cond = samp["audio_file"].split("-", 1)[1].replace(".m4a", "").strip()
                    group_key = f"stage_a_own:{cond}"
                else:
                    group_key = ds_name
                entry = {
                    "sample_id": samp["sample_id"],
                    "dataset": ds_name,
                    "group": group_key,
                    "wer": samp["metrics"]["wer"],
                    "transcript": transcript,
                    "sim_reference": s_ref,
                    "sim_unrelated": s_unrel,
                    "separation": s_ref - s_unrel,
                }
                cand_samples.append(entry)
                by_group.setdefault(group_key, []).append(entry)

        out["candidates"][cand_name] = {
            "overall": group_stats(cand_samples),
            "by_condition": {g: group_stats(items) for g, items in sorted(by_group.items())},
            "samples": cand_samples,
        }
    return out


def measure_cold_run_subprocess(candidate: str, audio_path: Path, offline: bool) -> dict[str, Any]:
    """Run a single cold start (model load + 1st inference) in a fresh Python process."""
    code = (
        "import json, sys; from pathlib import Path; from time import perf_counter; "
        f"sys.path.insert(0, {str(AI_ROOT)!r}); "
        "from spikes.compare_asr import current_peak_rss_bytes, current_rss_bytes; "
        "cand, audio, offline = sys.argv[1], Path(sys.argv[2]), sys.argv[3] == '1'; "
        "rss_before = current_rss_bytes(); "
        "t0 = perf_counter(); "
    )
    if candidate == "deepgram":
        code += (
            "from deepgram_transcriber import DeepgramTranscriber; "
            "t_load0 = perf_counter(); engine = DeepgramTranscriber(); "
            "load_s = perf_counter() - t_load0; "
            "res = engine.transcribe(audio); "
        )
    else:
        code += (
            "from spikes.transcribe import Transcriber; "
            "engine = Transcriber(cand, offline=offline); "
            "load_s = engine.load_seconds; "
            "res = engine.transcribe(audio); "
        )
    code += (
        "total_s = perf_counter() - t0; "
        "peak = current_peak_rss_bytes(); "
        "rss_after = current_rss_bytes(); "
        "print(json.dumps({'total_seconds': total_s, 'model_load_seconds': load_s, "
        "'inference_seconds': res['inference_seconds'], 'peak_rss_bytes': peak, "
        "'rss_before_bytes': rss_before, 'rss_after_bytes': rss_after}))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code, candidate, str(audio_path), "1" if offline else "0"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return dict(json.loads(lines[-1]))


def measure_combined_with_similarity_subprocess(
    candidate: str, audio_path: Path, question: str, offline: bool
) -> dict[str, Any]:
    """Measure peak RSS in a single process loading and running both ASR and SimilarityModel."""
    code = (
        "import json, sys; from pathlib import Path; from time import perf_counter; "
        f"sys.path.insert(0, {str(AI_ROOT)!r}); "
        "from audio_runtime import SIM_REVISION; "
        "from spikes.compare_asr import current_peak_rss_bytes, current_rss_bytes; "
        "from spikes.similarity import SimilarityModel; "
        "from spikes.synthetic_voice import decode_audio; "
        "cand, audio, question, offline = ("
        "sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4] == '1'); "
        "rss_start = current_rss_bytes(); "
        "t0 = perf_counter(); "
        "waveform = decode_audio(audio); "
    )
    if candidate == "deepgram":
        code += (
            "from deepgram_transcriber import DeepgramTranscriber; asr = DeepgramTranscriber(); "
        )
    else:
        code += (
            "from spikes.transcribe import Transcriber; asr = Transcriber(cand, offline=offline); "
        )
    code += (
        "rss_after_asr_load = current_rss_bytes(); "
        "t_sim0 = perf_counter(); "
        "sim_model = SimilarityModel(SIM_REVISION, offline=offline); "
        "sim_load_s = perf_counter() - t_sim0; "
        "rss_after_both_loaded = current_rss_bytes(); "
        "res = asr.transcribe(audio); "
        "t_score0 = perf_counter(); "
        "sim_score = sim_model.score(question, res['transcript']); "
        "sim_infer_s = perf_counter() - t_score0; "
        "total_s = perf_counter() - t0; "
        "rss_after_infer = current_rss_bytes(); "
        "peak = current_peak_rss_bytes(); "
        "print(json.dumps({"
        "'rss_start_bytes': rss_start, "
        "'rss_after_asr_load_bytes': rss_after_asr_load, "
        "'rss_after_both_loaded_bytes': rss_after_both_loaded, "
        "'rss_after_infer_bytes': rss_after_infer, "
        "'peak_rss_bytes': peak, "
        "'peak_rss_mib': round(peak / (1024 * 1024), 2), "
        "'similarity_load_seconds': sim_load_s, "
        "'similarity_inference_seconds': sim_infer_s, "
        "'similarity_score': sim_score, "
        "'combined_total_seconds': total_s, "
        "'decoded_samples': len(waveform)"
        "}))"
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            candidate,
            str(audio_path),
            question,
            "1" if offline else "0",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return dict(json.loads(lines[-1]))


def run_candidate_worker(
    candidate: str,
    manifests: list[Path],
    warm_runs: int,
    cold_runs: int,
    offline: bool,
) -> dict[str, Any]:
    """Execute inside an isolated process for accurate RSS peak tracking."""
    rss_baseline = current_rss_bytes()
    datasets_rows: dict[str, list[dict[str, str]]] = {}
    for manifest in manifests:
        datasets_rows[manifest.parent.name] = load_manifest(manifest)

    first_dataset_rows = next(iter(datasets_rows.values()))
    benchmark_audio = Path(first_dataset_rows[0]["resolved_path"])
    benchmark_sample_id = first_dataset_rows[0]["sample_id"]
    benchmark_reference = first_dataset_rows[0]["reference"]

    if candidate == "deepgram":
        t0 = perf_counter()
        engine: Any = DeepgramTranscriber()
        load_seconds = perf_counter() - t0
        disk_bytes = 0
        provider_info = {
            "provider": "deepgram",
            "model": engine.model,
            "version": engine.version,
            "device": "remote_api",
            "compute_type": "remote",
        }
    else:
        engine = Transcriber(candidate, offline=offline)
        load_seconds = engine.load_seconds
        disk_bytes = directory_size_bytes(MODEL_DIRS[candidate]) or 0
        provider_info = {
            "provider": "faster-whisper",
            "model": candidate,
            "version": engine.version,
            "device": "cpu",
            "compute_type": "int8",
            "cpu_threads": engine.threads,
            "beam_size": 5,
            "vad_filter": True,
        }

    rss_after_load = current_rss_bytes()

    datasets_report: dict[str, Any] = {}
    all_samples: list[dict[str, Any]] = []
    for ds_name, rows in datasets_rows.items():
        ds_results = []
        for row in rows:
            item = engine.transcribe(Path(row["resolved_path"]), row["reference"])
            item["sample_id"] = row["sample_id"]
            item["dataset"] = ds_name
            ds_results.append(item)
            all_samples.append(item)
        datasets_report[ds_name] = {
            "summary": summarize(ds_results),
            "samples": ds_results,
        }

    warm_latencies: list[float] = []
    for _ in range(warm_runs):
        res = engine.transcribe(benchmark_audio)
        warm_latencies.append(float(res["inference_seconds"]))

    peak_rss_in_process = current_peak_rss_bytes()
    rss_after_warm = current_rss_bytes()

    cold_totals: list[float] = []
    cold_loads: list[float] = []
    cold_inferences: list[float] = []
    cold_peaks: list[int] = []
    for _ in range(cold_runs):
        cold = measure_cold_run_subprocess(candidate, benchmark_audio, offline)
        cold_totals.append(float(cold["total_seconds"]))
        cold_loads.append(float(cold["model_load_seconds"]))
        cold_inferences.append(float(cold["inference_seconds"]))
        cold_peaks.append(int(cold["peak_rss_bytes"]))

    peak_rss_bytes = max([peak_rss_in_process, *cold_peaks])
    combined_with_similarity = measure_combined_with_similarity_subprocess(
        candidate, benchmark_audio, benchmark_reference, offline
    )
    return {
        **provider_info,
        "model_size_disk_bytes": disk_bytes,
        "model_size_disk_mib": round(disk_bytes / (1024 * 1024), 2),
        "model_load_seconds_initial": load_seconds,
        "memory": {
            "rss_baseline_bytes": rss_baseline,
            "rss_after_load_bytes": rss_after_load,
            "rss_after_warm_bytes": rss_after_warm,
            "peak_rss_bytes": peak_rss_bytes,
            "peak_rss_mib": round(peak_rss_bytes / (1024 * 1024), 2),
            "rss_delta_load_mib": (
                round((rss_after_load - rss_baseline) / (1024 * 1024), 2)
                if rss_baseline is not None and rss_after_load is not None
                else None
            ),
            "combined_with_similarity": combined_with_similarity,
        },
        "benchmark_sample": {
            "sample_id": benchmark_sample_id,
            "audio_file": benchmark_audio.name,
            "audio_seconds": all_samples[0]["audio_seconds"],
        },
        "latency_cold": {
            "total": latency_stats(cold_totals),
            "model_load": latency_stats(cold_loads),
            "inference": latency_stats(cold_inferences),
        },
        "latency_warm": latency_stats(warm_latencies),
        "combined_summary": summarize(all_samples),
        "datasets": datasets_report,
    }


def invoke_isolated_candidate(
    candidate: str,
    manifests: list[Path],
    warm_runs: int,
    cold_runs: int,
    offline: bool,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker-candidate",
        candidate,
        "--warm-runs",
        str(warm_runs),
        "--cold-runs",
        str(cold_runs),
        *(["--offline"] if offline else []),
        "--manifests",
        *[str(m) for m in manifests],
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return dict(json.loads(lines[-1]))


def main() -> int:
    os.chdir(AI_ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifests",
        nargs="+",
        type=Path,
        default=[Path("datasets/mediaspeech_es/manifest.csv")],
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=[*LOCAL_MODELS],
        default=list(LOCAL_MODELS),
    )
    parser.add_argument("--warm-runs", type=int, default=20)
    parser.add_argument("--cold-runs", type=int, default=20)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/asr-comparison.json"),
    )
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="Conservar candidatos ya medidos en --output y actualizar solo los ejecutados",
    )
    parser.add_argument("--only-deepgram", action="store_true")
    parser.add_argument("--worker-candidate", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker_candidate:
        result = run_candidate_worker(
            args.worker_candidate,
            args.manifests,
            args.warm_runs,
            args.cold_runs,
            args.offline,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0

    existing: dict[str, Any] = {}
    if args.merge_existing and args.output.is_file():
        existing = json.loads(args.output.read_text(encoding="utf-8"))

    manifests_meta = []
    for manifest in args.manifests:
        rows = load_manifest(manifest)
        manifests_meta.append(
            {
                "dataset": manifest.parent.name,
                "manifest_path": str(manifest),
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "sample_count": len(rows),
            }
        )

    candidates: dict[str, Any] = dict(existing.get("candidates", {}))

    if not args.only_deepgram:
        for model_name in args.models:
            print(
                f"[compare_asr] Midiendo faster-whisper '{model_name}' "
                f"(cold={args.cold_runs}, warm={args.warm_runs})...",
                file=sys.stderr,
                flush=True,
            )
            candidates[f"faster-whisper-{model_name}"] = invoke_isolated_candidate(
                model_name,
                args.manifests,
                args.warm_runs,
                args.cold_runs,
                args.offline,
            )

    has_deepgram_key = bool(os.environ.get(API_KEY_ENV, "").strip())
    if not has_deepgram_key:
        for env_candidate in (
            AI_ROOT.parent.parent / ".env",
            AI_ROOT.parent / ".env",
            AI_ROOT / ".env",
        ):
            if env_candidate.is_file():
                for raw_line in env_candidate.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if line.startswith(f"{API_KEY_ENV}="):
                        val = line.split("=", 1)[1].strip().strip("\"'")
                        if val:
                            os.environ[API_KEY_ENV] = val
                            has_deepgram_key = True
                            break
            if has_deepgram_key:
                break
    deepgram_status: dict[str, Any]
    if has_deepgram_key:
        print(
            f"[compare_asr] DEEPGRAM_API_KEY detectada; midiendo Deepgram Nova-3 "
            f"(cold={args.cold_runs}, warm={args.warm_runs})...",
            file=sys.stderr,
            flush=True,
        )
        candidates["deepgram-nova-3"] = invoke_isolated_candidate(
            "deepgram",
            args.manifests,
            args.warm_runs,
            args.cold_runs,
            args.offline,
        )
        deepgram_status = {
            "evaluated": True,
            "reason": "DEEPGRAM_API_KEY present in environment (value never logged or stored)",
        }
    else:
        print(
            "[compare_asr] DEEPGRAM_API_KEY no definida; se omite Deepgram en esta pasada.",
            file=sys.stderr,
            flush=True,
        )
        if "deepgram-nova-3" in candidates:
            deepgram_status = {
                "evaluated": True,
                "reason": "Preserved from previous run via --merge-existing",
            }
        else:
            deepgram_status = {
                "evaluated": False,
                "reason": "Skipped: DEEPGRAM_API_KEY not set in environment",
            }

    report = {
        "schema_version": 1,
        "experiment": "stage_a_asr_comparison",
        "scope": "experiment_only_not_production_code",
        "created_at": datetime.now(UTC).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "os": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "faster_whisper": version("faster-whisper"),
            "ctranslate2": version("ctranslate2"),
            "httpx": version("httpx"),
        },
        "parameters": {
            "warm_runs": args.warm_runs,
            "cold_runs": args.cold_runs,
            "offline": args.offline,
            "manifests": manifests_meta,
        },
        "deepgram_status": deepgram_status,
        "candidates": candidates,
    }
    save_json(args.output, report)
    print(f"[compare_asr] Guardado en {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
