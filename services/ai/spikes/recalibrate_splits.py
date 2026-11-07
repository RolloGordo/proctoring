"""Recalibración rigurosa de umbrales con validación cruzada entre guiones.

Split 1:
- Calibración: Audio1-2 + MediaSpeech (18 audios)
- Evaluación held-out: Audio3-4 (10 audios)

Split 2 (intercambio inverso):
- Calibración: Audio3-4 + MediaSpeech (18 audios)
- Evaluación held-out: Audio1-2 (10 audios)

Calcula umbrales óptimos por optimización sobre train, evalúa en test y
reporta intervalos de confianza de Wilson al 95 %.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

AI_DIR = Path(__file__).resolve().parent.parent
CALIB_DATA_PATH = AI_DIR / "results" / "quality-gate-calibration.json"


def wilson_interval(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Calcula el intervalo de Wilson para k aciertos sobre n ensayos."""
    if n == 0:
        return (0.0, 0.0)
    # z = 1.95996 para 95%
    z = 1.95996 if confidence == 0.95 else 1.64485
    p = k / n
    denom = 1.0 + (z**2) / n
    center = (p + (z**2) / (2 * n)) / denom
    spread = (z / denom) * math.sqrt((p * (1 - p) / n) + ((z**2) / (4 * (n**2))))
    lower = max(0.0, center - spread)
    upper = min(1.0, center + spread)
    return (round(lower, 4), round(upper, 4))


def is_bad_sample(s: dict[str, Any]) -> bool:
    wer = s.get("metrics", {}).get("wer")
    sim = s.get("similarity_exact", 0.0)
    return (wer is not None and wer > 0.40) or (sim < 0.60)


def extract_features(s: dict[str, Any]) -> dict[str, Any]:
    words = s.get("word_count", 0)
    dur = s.get("audio_seconds", 0.0)
    wps = s.get("words_per_second", (words / dur if dur > 0 else 0.0))
    seg_stats = s.get("segment_stats", {})
    return {
        "sample_id": s["sample_id"],
        "condition": s.get("condition"),
        "is_bad": is_bad_sample(s),
        "words": words,
        "wps": wps,
        "max_nsp": seg_stats.get("max_no_speech_prob", 0.0),
        "min_logprob": seg_stats.get("min_avg_logprob", 0.0),
        "max_comp": seg_stats.get("max_compression_ratio", 1.0),
        "text": str(s.get("transcript", "")).lower(),
    }


def evaluate_gate_params(
    feat: dict[str, Any],
    min_wps: float,
    max_nsp: float,
    min_logprob: float,
    max_comp: float,
) -> tuple[bool, str]:
    text = feat["text"]
    hallucinations = [
        "suscríbete",
        "suscribete",
        "más información en www",
        "mas informacion en www",
        "amara.org",
        "subtítulos realizados por",
        "subtitulos realizados por",
    ]
    for h in hallucinations:
        if h in text:
            return True, f"hallucination:{h}"

    if feat["words"] == 0:
        return True, "empty_transcript"
    if feat["wps"] < min_wps:
        return True, f"low_wps:{feat['wps']:.2f}<{min_wps:.2f}"
    if feat["max_nsp"] > max_nsp:
        return True, f"high_no_speech:{feat['max_nsp']:.2f}>{max_nsp:.2f}"
    if feat["min_logprob"] < min_logprob:
        return True, f"low_logprob:{feat['min_logprob']:.2f}<{min_logprob:.2f}"
    if feat["max_comp"] > max_comp:
        return True, f"high_comp:{feat['max_comp']:.2f}>{max_comp:.2f}"
    return False, "ok"


def calibrate_thresholds(train_features: list[dict[str, Any]]) -> dict[str, float]:
    """Encuentra los umbrales óptimos maximizando F1 en el conjunto de entrenamiento."""
    best_f1 = -1.0
    best_params = {
        "min_words_per_second": 0.5,
        "max_no_speech_prob": 0.6,
        "min_avg_logprob": -0.6,
        "max_compression_ratio": 1.85,
    }

    # Búsqueda en grilla sobre valores plausibles
    wps_candidates = [0.3, 0.4, 0.5, 0.6, 0.8]
    nsp_candidates = [0.4, 0.5, 0.6, 0.7]
    logprob_candidates = [-0.8, -0.7, -0.6, -0.5, -0.4]
    comp_candidates = [1.6, 1.7, 1.85, 2.0]

    for wps in wps_candidates:
        for nsp in nsp_candidates:
            for lp in logprob_candidates:
                for comp in comp_candidates:
                    tp = fp = fn = tn = 0
                    for feat in train_features:
                        flagged, _ = evaluate_gate_params(feat, wps, nsp, lp, comp)
                        bad = feat["is_bad"]
                        if bad and flagged:
                            tp += 1
                        elif not bad and flagged:
                            fp += 1
                        elif bad and not flagged:
                            fn += 1
                        else:
                            tn += 1

                    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

                    # Priorizamos 0 falsos positivos (no degradar audios buenos) y máximo recall
                    score = f1 - (fp * 0.2)
                    if score > best_f1:
                        best_f1 = score
                        best_params = {
                            "min_words_per_second": wps,
                            "max_no_speech_prob": nsp,
                            "min_avg_logprob": lp,
                            "max_compression_ratio": comp,
                        }

    return best_params


def evaluate_split(
    train_features: list[dict[str, Any]],
    test_features: list[dict[str, Any]],
    split_name: str,
) -> dict[str, Any]:
    calibrated = calibrate_thresholds(train_features)

    # Evaluar en train
    def score_set(features: list[dict[str, Any]]) -> dict[str, Any]:
        tp = fp = fn = tn = 0
        details = []
        for feat in features:
            flagged, reason = evaluate_gate_params(
                feat,
                calibrated["min_words_per_second"],
                calibrated["max_no_speech_prob"],
                calibrated["min_avg_logprob"],
                calibrated["max_compression_ratio"],
            )
            bad = feat["is_bad"]
            if bad and flagged:
                tp += 1
            elif not bad and flagged:
                fp += 1
            elif bad and not flagged:
                fn += 1
            else:
                tn += 1
            details.append(
                {
                    "sample_id": feat["sample_id"],
                    "condition": feat["condition"],
                    "is_bad": bad,
                    "flagged": flagged,
                    "reason": reason,
                }
            )

        n = len(features)
        bad_count = tp + fn
        good_count = tn + fp
        rec = tp / bad_count if bad_count > 0 else 1.0
        prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        acc = (tp + tn) / n if n > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        rec_wilson = wilson_interval(tp, bad_count)
        acc_wilson = wilson_interval(tp + tn, n)

        return {
            "total_samples": n,
            "bad_count": bad_count,
            "good_count": good_count,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "recall_wilson_95": rec_wilson,
            "accuracy": round(acc, 4),
            "accuracy_wilson_95": acc_wilson,
            "f1_score": round(f1, 4),
            "samples": details,
        }

    return {
        "split_name": split_name,
        "calibrated_thresholds": calibrated,
        "train_metrics": score_set(train_features),
        "test_metrics": score_set(test_features),
    }


def main() -> int:
    with open(CALIB_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    samples = data["vad_configurations"]["vad_true_threshold_0_3"]["samples"]
    features = [extract_features(s) for s in samples]

    # Split 1: Train = MediaSpeech + Audio1 + Audio2; Test = Audio3 + Audio4
    train1 = [
        f
        for f in features
        if not (f["sample_id"].startswith("P01_A3") or f["sample_id"].startswith("P01_A4"))
    ]
    test1 = [
        f
        for f in features
        if f["sample_id"].startswith("P01_A3") or f["sample_id"].startswith("P01_A4")
    ]

    # Split 2 (inverso): Train = MediaSpeech + Audio3 + Audio4; Test = Audio1 + Audio2
    train2 = [
        f
        for f in features
        if not (f["sample_id"].startswith("P01_A1") or f["sample_id"].startswith("P01_A2"))
    ]
    test2 = [
        f
        for f in features
        if f["sample_id"].startswith("P01_A1") or f["sample_id"].startswith("P01_A2")
    ]

    res1 = evaluate_split(train1, test1, "Split 1: Train=MediaSpeech+A1+A2 (18) -> Test=A3+A4 (10)")
    res2 = evaluate_split(
        train2, test2, "Split 2 (Inverso): Train=MediaSpeech+A3+A4 (18) -> Test=A1+A2 (10)"
    )

    output = {
        "speaker_warning": (
            "NOTA CRÍTICA: Las muestras grabadas provienen de una única voz y hablante (P01), "
            "con el mismo micrófono y entorno acústico. La generalización evaluada es "
            "exclusivamente entre guiones y preguntas distintas (out-of-script), pero NO "
            "entre diferentes hablantes ni micrófonos."
        ),
        "split_1": res1,
        "split_2_inverse": res2,
    }

    out_path = AI_DIR / "results" / "gate-generalization-cross-validation.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Resultados guardados en {out_path}")
    print("\n--- RESUMEN SPLIT 1 (Train: A1-2+MediaSpeech -> Test: A3-4) ---")
    print("Umbrales calibrados en Train:", res1["calibrated_thresholds"])
    m1 = res1["test_metrics"]
    print(
        f"Test Recall: {m1['recall']} (Wilson 95%: {m1['recall_wilson_95']}) | "
        f"Accuracy: {m1['accuracy']} (Wilson 95%: {m1['accuracy_wilson_95']}) | "
        f"FP: {m1['fp']} | FN: {m1['fn']}"
    )

    print("\n--- RESUMEN SPLIT 2 INVERSO (Train: A3-4+MediaSpeech -> Test: A1-2) ---")
    print("Umbrales calibrados en Train:", res2["calibrated_thresholds"])
    m2 = res2["test_metrics"]
    print(
        f"Test Recall: {m2['recall']} (Wilson 95%: {m2['recall_wilson_95']}) | "
        f"Accuracy: {m2['accuracy']} (Wilson 95%: {m2['accuracy_wilson_95']}) | "
        f"FP: {m2['fp']} | FN: {m2['fn']}"
    )
    return 0


if __name__ == "__main__":
    main()
