"""EXPERIMENTO ETAPA 1 — Calibración de la puerta de calidad ASR y simulación de cascada.

No forma parte del runtime de producción.
Evalúa faster-whisper small (int8, CPU) en los 28 audios (8 MediaSpeech + 20 stage_a_own)
con 3 configuraciones de VAD, calibra los umbrales de la puerta de calidad contra la
definición de transcripción mala (WER > 40 % o similitud < 0.60) y simula la cascada
Whisper -> Deepgram usando las transcripciones de Deepgram ya guardadas en
services/ai/results/asr-comparison.json.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

AI_ROOT = Path(__file__).resolve().parent.parent
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))
os.chdir(AI_ROOT)

from spikes.evaluate import load_manifest, summarize  # noqa: E402
from spikes.similarity import SimilarityModel  # noqa: E402
from spikes.transcribe import Transcriber  # noqa: E402

SIM_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
UNRELATED_TEXT = "El sistema solar tiene ocho planetas que giran alrededor del sol."

DEFAULT_HALLUCINATION_PHRASES: tuple[str, ...] = (
    "suscríbete",
    "suscribete",
    "más información en www",
    "mas informacion en www",
    "subtítulos realizados por",
    "subtitulos realizados por",
    "amara.org",
    "gracias por ver",
)

CONDITIONS_ORDER: tuple[str, ...] = (
    "mediaspeech_es",
    "base",
    "lejos",
    "ruido",
    "bajaylejos",
    "voz baja",
)


def condition_from_sample_id(sample_id: str) -> str:
    if not sample_id.upper().startswith("P01_"):
        return "mediaspeech_es"
    parts = sample_id.split("_")
    return " ".join(parts[2:])


def is_bad_transcript(wer: float | None, similarity: float) -> bool:
    """Criterio del prompt: WER > 40 % o similitud < 0,60."""
    if wer is None or wer > 0.40:
        return True
    if similarity < 0.60:
        return True
    return False


def aggregate_segment_stats(segments: list[dict[str, Any]]) -> dict[str, float | None]:
    nsps = [float(s["no_speech_prob"]) for s in segments if s.get("no_speech_prob") is not None]
    logprobs = [float(s["avg_logprob"]) for s in segments if s.get("avg_logprob") is not None]
    crs = [
        float(s["compression_ratio"]) for s in segments if s.get("compression_ratio") is not None
    ]
    return {
        "max_no_speech_prob": round(max(nsps), 6) if nsps else None,
        "mean_no_speech_prob": round(sum(nsps) / len(nsps), 6) if nsps else None,
        "min_avg_logprob": round(min(logprobs), 6) if logprobs else None,
        "mean_avg_logprob": round(sum(logprobs) / len(logprobs), 6) if logprobs else None,
        "max_compression_ratio": round(max(crs), 6) if crs else None,
        "mean_compression_ratio": round(sum(crs) / len(crs), 6) if crs else None,
    }


def evaluate_quality_gate(
    sample: dict[str, Any],
    *,
    min_words_per_second: float = 0.50,
    max_no_speech_prob: float = 0.60,
    min_avg_logprob: float = -0.60,
    max_compression_ratio: float = 1.85,
    hallucination_phrases: tuple[str, ...] = DEFAULT_HALLUCINATION_PHRASES,
) -> dict[str, Any]:
    """Evalúa si una transcripción de Whisper pasa la puerta de calidad o requiere respaldo."""
    reasons: list[str] = []

    if sample.get("error"):
        reasons.append("exception_or_timeout")

    transcript = (sample.get("transcript") or "").strip()
    lower_transcript = transcript.lower()

    if not transcript:
        reasons.append("empty_transcript")
    else:
        matched_phrases = [p for p in hallucination_phrases if p.lower() in lower_transcript]
        if matched_phrases:
            reasons.append(f"hallucination_phrase:{matched_phrases[0]}")

        wps = float(sample.get("words_per_second") or 0.0)
        if wps < min_words_per_second:
            reasons.append("low_words_per_second")

        seg_stats = sample.get("segment_stats", {})
        max_nsp = seg_stats.get("max_no_speech_prob")
        if max_nsp is not None and float(max_nsp) > max_no_speech_prob:
            reasons.append("high_no_speech_prob")

        min_lp = seg_stats.get("min_avg_logprob")
        if min_lp is not None and float(min_lp) < min_avg_logprob:
            reasons.append("low_avg_logprob")

        max_cr = seg_stats.get("max_compression_ratio")
        if max_cr is not None and float(max_cr) > max_compression_ratio:
            reasons.append("high_compression_ratio")

    return {
        "passed": len(reasons) == 0,
        "fallback_triggered": len(reasons) > 0,
        "reasons": reasons,
        "primary_reason": reasons[0] if reasons else None,
    }


def summarize_condition_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    wer_summary = summarize(samples)
    sims = [float(s["similarity_exact"]) for s in samples]
    bad_count = sum(1 for s in samples if s["is_bad"])
    return {
        "sample_count": len(samples),
        "audio_seconds": round(sum(float(s["audio_seconds"]) for s in samples), 3),
        "reference_words": wer_summary["reference_words"],
        "word_edits": wer_summary["word_edits"],
        "micro_wer": round(float(wer_summary["micro_wer"]), 6)
        if wer_summary["micro_wer"] is not None
        else None,
        "mean_similarity": round(sum(sims) / len(sims), 4) if sims else 0.0,
        "min_similarity": round(min(sims), 4) if sims else 0.0,
        "max_similarity": round(max(sims), 4) if sims else 0.0,
        "alerts_ge_0_60": sum(1 for x in sims if x >= 0.60),
        "bad_transcripts_count": bad_count,
        "good_transcripts_count": len(samples) - bad_count,
    }


def confusion_counts(samples: list[dict[str, Any]], flags: list[bool]) -> dict[str, Any]:
    """Calcula métricas de detección de transcripciones malas (positivo = requiere respaldo)."""
    total_bad = sum(1 for s in samples if s["is_bad"])
    total_good = len(samples) - total_bad
    tp_bad_caught = sum(
        1 for s, flagged in zip(samples, flags, strict=True) if s["is_bad"] and flagged
    )
    fn_bad_missed = sum(
        1 for s, flagged in zip(samples, flags, strict=True) if s["is_bad"] and not flagged
    )
    fp_false_trigger = sum(
        1 for s, flagged in zip(samples, flags, strict=True) if not s["is_bad"] and flagged
    )
    tn_good_passed = sum(
        1 for s, flagged in zip(samples, flags, strict=True) if not s["is_bad"] and not flagged
    )
    return {
        "total_samples": len(samples),
        "total_bad": total_bad,
        "total_good": total_good,
        "bad_caught_tp": tp_bad_caught,
        "bad_missed_fn": fn_bad_missed,
        "good_passed_tn": tn_good_passed,
        "false_triggers_fp": fp_false_trigger,
        "recall_bad_caught": round(tp_bad_caught / total_bad, 4) if total_bad > 0 else None,
        "false_trigger_rate": round(fp_false_trigger / total_good, 4) if total_good > 0 else None,
    }


def calibrate_thresholds_for_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Evalúa cada señal individualmente y la puerta combinada sobre los 28 audios."""
    non_empty = [s for s in samples if (s.get("transcript") or "").strip()]

    # 1. Empty transcript alone
    empty_flags = [not (s.get("transcript") or "").strip() for s in samples]
    empty_eval = confusion_counts(samples, empty_flags)

    # 2. Hallucination phrases alone
    halluc_flags = [
        any(p in (s.get("transcript") or "").lower() for p in DEFAULT_HALLUCINATION_PHRASES)
        for s in samples
    ]
    halluc_eval = confusion_counts(samples, halluc_flags)

    # 3. Words per second sweep (evaluated on non-empty and on all samples)
    wps_thresholds = [0.15, 0.30, 0.50, 0.80, 1.00, 1.20, 1.40, 1.60]
    wps_sweep_non_empty = []
    wps_sweep_all = []
    for th in wps_thresholds:
        flags_ne = [float(s["words_per_second"]) < th for s in non_empty]
        wps_sweep_non_empty.append(
            {"threshold_min_wps": th, **confusion_counts(non_empty, flags_ne)}
        )
        flags_all = [float(s["words_per_second"]) < th for s in samples]
        wps_sweep_all.append({"threshold_min_wps": th, **confusion_counts(samples, flags_all)})

    # 4. max_no_speech_prob sweep (on non-empty segments)
    nsp_thresholds = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80]
    nsp_sweep = []
    for th in nsp_thresholds:
        flags_ne = [
            s["segment_stats"]["max_no_speech_prob"] is not None
            and float(s["segment_stats"]["max_no_speech_prob"]) > th
            for s in non_empty
        ]
        nsp_sweep.append(
            {"threshold_max_no_speech_prob": th, **confusion_counts(non_empty, flags_ne)}
        )

    # 5. min_avg_logprob sweep (on non-empty segments)
    lp_thresholds = [-0.45, -0.50, -0.55, -0.60, -0.65, -0.70, -0.75, -0.80, -0.90, -1.00]
    lp_sweep = []
    for th in lp_thresholds:
        flags_ne = [
            s["segment_stats"]["min_avg_logprob"] is not None
            and float(s["segment_stats"]["min_avg_logprob"]) < th
            for s in non_empty
        ]
        lp_sweep.append({"threshold_min_avg_logprob": th, **confusion_counts(non_empty, flags_ne)})

    # 6. max_compression_ratio sweep (on non-empty segments)
    cr_thresholds = [1.50, 1.60, 1.75, 1.85, 2.00, 2.20, 2.40]
    cr_sweep = []
    for th in cr_thresholds:
        flags_ne = [
            s["segment_stats"]["max_compression_ratio"] is not None
            and float(s["segment_stats"]["max_compression_ratio"]) > th
            for s in non_empty
        ]
        cr_sweep.append(
            {"threshold_max_compression_ratio": th, **confusion_counts(non_empty, flags_ne)}
        )

    # 7. Combined gate with calibrated thresholds
    calibrated_params = {
        "min_words_per_second": 0.50,
        "max_no_speech_prob": 0.60,
        "min_avg_logprob": -0.60,
        "max_compression_ratio": 1.85,
        "hallucination_phrases": list(DEFAULT_HALLUCINATION_PHRASES),
    }
    decisions = [
        evaluate_quality_gate(
            s,
            min_words_per_second=0.50,
            max_no_speech_prob=0.60,
            min_avg_logprob=-0.60,
            max_compression_ratio=1.85,
        )
        for s in samples
    ]
    combined_flags = [d["fallback_triggered"] for d in decisions]
    combined_eval = confusion_counts(samples, combined_flags)

    # Feature ranges observed across good vs bad non-empty transcripts
    good_ne = [s for s in non_empty if not s["is_bad"]]
    bad_ne = [s for s in non_empty if s["is_bad"]]

    def _range(items: list[dict[str, Any]], getter: Any) -> dict[str, float | None]:
        vals = [float(v) for s in items if (v := getter(s)) is not None]
        if not vals:
            return {"min": None, "max": None, "count": 0}
        return {"min": round(min(vals), 4), "max": round(max(vals), 4), "count": len(vals)}

    observed_ranges = {
        "good_non_empty": {
            "count": len(good_ne),
            "words_per_second": _range(good_ne, lambda s: s["words_per_second"]),
            "max_no_speech_prob": _range(
                good_ne, lambda s: s["segment_stats"]["max_no_speech_prob"]
            ),
            "min_avg_logprob": _range(good_ne, lambda s: s["segment_stats"]["min_avg_logprob"]),
            "max_compression_ratio": _range(
                good_ne, lambda s: s["segment_stats"]["max_compression_ratio"]
            ),
        },
        "bad_non_empty": {
            "count": len(bad_ne),
            "words_per_second": _range(bad_ne, lambda s: s["words_per_second"]),
            "max_no_speech_prob": _range(
                bad_ne, lambda s: s["segment_stats"]["max_no_speech_prob"]
            ),
            "min_avg_logprob": _range(bad_ne, lambda s: s["segment_stats"]["min_avg_logprob"]),
            "max_compression_ratio": _range(
                bad_ne, lambda s: s["segment_stats"]["max_compression_ratio"]
            ),
        },
    }

    return {
        "observed_feature_ranges": observed_ranges,
        "single_criterion_evaluations": {
            "empty_transcript": empty_eval,
            "hallucination_phrase": halluc_eval,
            "words_per_second_on_all": wps_sweep_all,
            "words_per_second_on_non_empty": wps_sweep_non_empty,
            "max_no_speech_prob_on_non_empty": nsp_sweep,
            "min_avg_logprob_on_non_empty": lp_sweep,
            "max_compression_ratio_on_non_empty": cr_sweep,
        },
        "proposed_gate_parameters": calibrated_params,
        "combined_gate_evaluation": combined_eval,
    }


def simulate_cascade(
    whisper_samples: list[dict[str, Any]],
    deepgram_by_id: dict[str, dict[str, Any]],
    *,
    min_words_per_second: float = 0.50,
    max_no_speech_prob: float = 0.60,
    min_avg_logprob: float = -0.60,
    max_compression_ratio: float = 1.85,
) -> dict[str, Any]:
    """Simula la cascada Whisper -> Puerta de calidad -> Deepgram sobre los 28 audios."""
    cascade_samples: list[dict[str, Any]] = []
    for ws in whisper_samples:
        sid = ws["sample_id"]
        dgs = deepgram_by_id[sid]
        gate = evaluate_quality_gate(
            ws,
            min_words_per_second=min_words_per_second,
            max_no_speech_prob=max_no_speech_prob,
            min_avg_logprob=min_avg_logprob,
            max_compression_ratio=max_compression_ratio,
        )
        chosen = dgs if gate["fallback_triggered"] else ws
        total_infer_s = (
            float(ws["inference_seconds"]) + float(dgs["inference_seconds"])
            if gate["fallback_triggered"]
            else float(ws["inference_seconds"])
        )
        cascade_samples.append(
            {
                "sample_id": sid,
                "condition": ws["condition"],
                "audio_file": ws["audio_file"],
                "audio_seconds": ws["audio_seconds"],
                "inference_seconds": round(total_infer_s, 4),
                "reference": ws["reference"],
                "whisper_transcript": ws["transcript"],
                "whisper_wer": ws["metrics"]["wer"],
                "whisper_similarity": ws["similarity_exact"],
                "whisper_is_bad": ws["is_bad"],
                "gate_passed": gate["passed"],
                "fallback_triggered": gate["fallback_triggered"],
                "fallback_reasons": gate["reasons"],
                "primary_fallback_reason": gate["primary_reason"],
                "selected_provider": "deepgram-nova-3"
                if gate["fallback_triggered"]
                else "faster-whisper-small",
                "transcript": chosen["transcript"],
                "metrics": chosen["metrics"],
                "similarity_exact": chosen["similarity_exact"],
                "similarity_unrelated": chosen["similarity_unrelated"],
                "is_bad": chosen["is_bad"],
            }
        )

    total_audio_s = sum(float(s["audio_seconds"]) for s in cascade_samples)
    dg_audio_s = sum(float(s["audio_seconds"]) for s in cascade_samples if s["fallback_triggered"])
    fallback_count = sum(1 for s in cascade_samples if s["fallback_triggered"])

    by_condition: dict[str, Any] = {}
    for cond in CONDITIONS_ORDER:
        cs = [s for s in cascade_samples if s["condition"] == cond]
        fb_cs = [s for s in cs if s["fallback_triggered"]]
        cond_audio_s = sum(float(s["audio_seconds"]) for s in cs)
        cond_dg_s = sum(float(s["audio_seconds"]) for s in fb_cs)
        by_condition[cond] = {
            **summarize_condition_samples(cs),
            "fallback_count": len(fb_cs),
            "fallback_rate": round(len(fb_cs) / len(cs), 4) if cs else 0.0,
            "deepgram_audio_seconds": round(cond_dg_s, 3),
            "deepgram_audio_minutes": round(cond_dg_s / 60.0, 4),
            "deepgram_audio_share": round(cond_dg_s / cond_audio_s, 4) if cond_audio_s > 0 else 0.0,
        }

    clean_cs = [s for s in cascade_samples if s["condition"] in ("mediaspeech_es", "base", "lejos")]
    adverse_cs = [
        s for s in cascade_samples if s["condition"] in ("ruido", "bajaylejos", "voz baja")
    ]
    clean_fb = [s for s in clean_cs if s["fallback_triggered"]]
    adverse_fb = [s for s in adverse_cs if s["fallback_triggered"]]

    return {
        "overall": {
            **summarize_condition_samples(cascade_samples),
            "fallback_count": fallback_count,
            "fallback_rate": round(fallback_count / len(cascade_samples), 4),
            "total_audio_seconds": round(total_audio_s, 3),
            "total_audio_minutes": round(total_audio_s / 60.0, 4),
            "deepgram_audio_seconds": round(dg_audio_s, 3),
            "deepgram_audio_minutes": round(dg_audio_s / 60.0, 4),
            "deepgram_audio_share": round(dg_audio_s / total_audio_s, 4)
            if total_audio_s > 0
            else 0.0,
        },
        "clean_aggregate": {
            **summarize_condition_samples(clean_cs),
            "fallback_count": len(clean_fb),
            "fallback_rate": round(len(clean_fb) / len(clean_cs), 4),
            "deepgram_audio_seconds": round(sum(float(s["audio_seconds"]) for s in clean_fb), 3),
            "deepgram_audio_minutes": round(
                sum(float(s["audio_seconds"]) for s in clean_fb) / 60.0, 4
            ),
        },
        "adverse_aggregate": {
            **summarize_condition_samples(adverse_cs),
            "fallback_count": len(adverse_fb),
            "fallback_rate": round(len(adverse_fb) / len(adverse_cs), 4),
            "deepgram_audio_seconds": round(sum(float(s["audio_seconds"]) for s in adverse_fb), 3),
            "deepgram_audio_minutes": round(
                sum(float(s["audio_seconds"]) for s in adverse_fb) / 60.0, 4
            ),
        },
        "by_condition": by_condition,
        "samples": cascade_samples,
    }


def main() -> int:
    raw_path = AI_ROOT / "results/quality-gate-raw-vad.json"
    if raw_path.is_file():
        raw_data = json.loads(raw_path.read_text(encoding="utf-8"))
        vad_evaluations = raw_data["vad_evaluations"]
        deepgram_samples = raw_data["deepgram"]["samples"]
    else:
        ms_rows = load_manifest(AI_ROOT / "datasets/mediaspeech_es/manifest.csv")
        own_rows = load_manifest(AI_ROOT / "datasets/stage_a_own/manifest.csv")
        all_rows = ms_rows + own_rows
        prev_comparison = json.loads(
            (AI_ROOT / "results/asr-comparison.json").read_text(encoding="utf-8")
        )
        dg_cand = prev_comparison["candidates"]["deepgram-nova-3"]
        dg_samples_raw = (
            dg_cand["datasets"]["mediaspeech_es"]["samples"]
            + dg_cand["datasets"]["stage_a_own"]["samples"]
        )
        dg_by_id_raw: dict[str, dict[str, Any]] = {s["sample_id"]: s for s in dg_samples_raw}
        sim_model = SimilarityModel(SIM_REVISION, offline=True)
        transcriber = Transcriber(model="small", threads=4, offline=True)
        deepgram_samples = []
        for row in all_rows:
            sid = row["sample_id"]
            cond = condition_from_sample_id(sid)
            dgs = dg_by_id_raw[sid]
            transcript = (dgs.get("transcript") or "").strip()
            ref = row["reference"]
            sim_exact = float(sim_model.score(ref, transcript)) if transcript else 0.0
            sim_unrel = float(sim_model.score(UNRELATED_TEXT, transcript)) if transcript else 0.0
            wer_val = dgs["metrics"]["wer"]
            deepgram_samples.append(
                {
                    "sample_id": sid,
                    "condition": cond,
                    "audio_file": Path(row["resolved_path"]).name,
                    "audio_seconds": float(dgs["audio_seconds"]),
                    "inference_seconds": float(dgs["inference_seconds"]),
                    "reference": ref,
                    "transcript": transcript,
                    "word_count": len(transcript.split()),
                    "words_per_second": round(
                        len(transcript.split()) / float(dgs["audio_seconds"]), 4
                    )
                    if float(dgs["audio_seconds"]) > 0
                    else 0.0,
                    "metrics": dgs["metrics"],
                    "similarity_exact": round(sim_exact, 4),
                    "similarity_unrelated": round(sim_unrel, 4),
                    "is_bad": is_bad_transcript(wer_val, sim_exact),
                }
            )
        vad_configs: list[dict[str, Any]] = [
            {"name": "vad_true_default", "vad_filter": True, "vad_parameters": None},
            {"name": "vad_false", "vad_filter": False, "vad_parameters": None},
            {
                "name": "vad_true_threshold_0_3",
                "vad_filter": True,
                "vad_parameters": {"threshold": 0.3},
            },
        ]
        vad_evaluations = {}
        for cfg in vad_configs:
            transcriber.vad_filter = cfg["vad_filter"]
            transcriber.vad_parameters = cfg["vad_parameters"]
            samples: list[dict[str, Any]] = []
            for row in all_rows:
                sid = row["sample_id"]
                cond = condition_from_sample_id(sid)
                res = transcriber.transcribe(
                    Path(row["resolved_path"]),
                    row["reference"],
                )
                transcript = res["transcript"]
                sim_exact = (
                    float(sim_model.score(row["reference"], transcript)) if transcript else 0.0
                )
                sim_unrel = (
                    float(sim_model.score(UNRELATED_TEXT, transcript)) if transcript else 0.0
                )
                seg_stats = aggregate_segment_stats(res["segments"])
                wer_val = res["metrics"]["wer"]
                samples.append(
                    {
                        "sample_id": sid,
                        "condition": cond,
                        "audio_file": res["audio_file"],
                        "audio_seconds": round(float(res["audio_seconds"]), 3),
                        "inference_seconds": round(float(res["inference_seconds"]), 4),
                        "reference": row["reference"],
                        "transcript": transcript,
                        "word_count": res["word_count"],
                        "words_per_second": round(float(res["words_per_second"]), 4),
                        "segment_count": len(res["segments"]),
                        "segments": res["segments"],
                        "segment_stats": seg_stats,
                        "metrics": res["metrics"],
                        "similarity_exact": round(sim_exact, 4),
                        "similarity_unrelated": round(sim_unrel, 4),
                        "is_bad": is_bad_transcript(wer_val, sim_exact),
                    }
                )
            vad_evaluations[cfg["name"]] = {
                "vad_filter": cfg["vad_filter"],
                "vad_parameters": cfg["vad_parameters"],
                "samples": samples,
            }

    # Normalize condition names and recompute summaries, calibration, and cascade
    for s in deepgram_samples:
        s["condition"] = condition_from_sample_id(s["sample_id"])
    deepgram_by_id = {s["sample_id"]: s for s in deepgram_samples}

    dg_by_cond = {
        cond: summarize_condition_samples([s for s in deepgram_samples if s["condition"] == cond])
        for cond in CONDITIONS_ORDER
    }
    deepgram_report = {
        "overall": summarize_condition_samples(deepgram_samples),
        "clean_aggregate": summarize_condition_samples(
            [s for s in deepgram_samples if s["condition"] in ("mediaspeech_es", "base", "lejos")]
        ),
        "adverse_aggregate": summarize_condition_samples(
            [s for s in deepgram_samples if s["condition"] in ("ruido", "bajaylejos", "voz baja")]
        ),
        "by_condition": dg_by_cond,
        "samples": deepgram_samples,
    }

    full_vad_reports: dict[str, Any] = {}
    for cfg_name, cfg in vad_evaluations.items():
        samples = cfg["samples"]
        for s in samples:
            s["condition"] = condition_from_sample_id(s["sample_id"])
        by_cond = {
            cond: summarize_condition_samples([s for s in samples if s["condition"] == cond])
            for cond in CONDITIONS_ORDER
        }
        clean_samples = [
            s for s in samples if s["condition"] in ("mediaspeech_es", "base", "lejos")
        ]
        adverse_samples = [
            s for s in samples if s["condition"] in ("ruido", "bajaylejos", "voz baja")
        ]
        calibration = calibrate_thresholds_for_samples(samples)
        cascade = simulate_cascade(samples, deepgram_by_id)
        full_vad_reports[cfg_name] = {
            "vad_filter": cfg["vad_filter"],
            "vad_parameters": cfg["vad_parameters"],
            "overall": summarize_condition_samples(samples),
            "clean_aggregate": summarize_condition_samples(clean_samples),
            "adverse_aggregate": summarize_condition_samples(adverse_samples),
            "by_condition": by_cond,
            "calibration": calibration,
            "cascade_simulation": cascade,
            "samples": samples,
        }

    out_path = AI_ROOT / "results/quality-gate-calibration.json"
    report = {
        "schema_version": 1,
        "experiment": "stage_1_quality_gate_calibration_and_cascade_simulation",
        "scope": "experiment_only_not_production_code",
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_warning": (
            "Calibrado sobre 28 audios en total: 8 de MediaSpeech (1 hablante cada uno) y "
            "20 grabaciones propias de una sola voz (hablante P01, 4 guiones x 5 condiciones). "
            "Existe riesgo de sobreajuste a esta voz, micrófono y sala; cualquier audio nuevo "
            "debe emplearse únicamente como conjunto de validación independiente."
        ),
        "bad_transcript_definition": "WER > 0.40 or similarity_exact < 0.60",
        "recommended_vad_config": "vad_true_threshold_0_3",
        "recommended_quality_gate_thresholds": {
            "min_words_per_second": 0.50,
            "max_no_speech_prob": 0.60,
            "min_avg_logprob": -0.60,
            "max_compression_ratio": 1.85,
            "hallucination_phrases": list(DEFAULT_HALLUCINATION_PHRASES),
        },
        "vad_configurations": full_vad_reports,
        "deepgram_standalone": deepgram_report,
    }
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if raw_path.is_file():
        raw_path.unlink()
    print(f"Saved full calibration report to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
