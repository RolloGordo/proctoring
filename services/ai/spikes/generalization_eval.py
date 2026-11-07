"""Estimación de generalización de la puerta de calidad y cascada.

Divide los 28 audios en:
- Calibración (train, dentro de muestra): MediaSpeech (8) + Audio1 (5) + Audio2 (5) = 18 audios.
- Evaluación (held-out test, fuera de muestra): Audio3 (5) + Audio4 (5) = 10 audios.

Calibra los umbrales de la puerta en train y evalúa generalización en test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

AI_DIR = Path(__file__).resolve().parent.parent
CALIB_DATA_PATH = AI_DIR / "results" / "quality-gate-calibration.json"


def run_split_evaluation() -> dict[str, Any]:
    with open(CALIB_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # Obtenemos las muestras de la configuración recomendada (vad_true_threshold_0_3)
    vad_cfg = data["vad_configurations"]["vad_true_threshold_0_3"]
    all_samples = vad_cfg["samples"]

    train_samples = []
    test_samples = []

    for s in all_samples:
        sid = s["sample_id"]
        # MediaSpeech, Audio1 y Audio2 a train
        if sid.startswith("P01_A3") or sid.startswith("P01_A4"):
            test_samples.append(s)
        else:
            train_samples.append(s)

    # Umbrales recomendados: min_wps=0.5, max_nsp=0.6, min_logprob=-0.6, max_comp=1.85
    def evaluate_gate(
        s: dict[str, Any],
        min_wps: float = 0.5,
        max_nsp: float = 0.6,
        min_logprob: float = -0.6,
        max_comp: float = 1.85,
    ) -> tuple[bool, str]:
        words = s.get("word_count", 0)
        dur = s.get("audio_seconds", 0.0)
        wps = s.get("words_per_second", (words / dur if dur > 0 else 0.0))
        seg_stats = s.get("segment_stats", {})
        nsp = seg_stats.get("max_no_speech_prob")
        logp = seg_stats.get("min_avg_logprob")
        comp = seg_stats.get("max_compression_ratio")
        text = str(s.get("transcript", "")).lower()

        hallucinations = [
            "suscríbete",
            "suscribete",
            "más información en www",
            "mas informacion en www",
            "amara.org",
        ]
        for h in hallucinations:
            if h in text:
                return True, f"hallucination:{h}"

        if words == 0:
            return True, "empty_transcript"
        if wps < min_wps:
            return True, f"low_wps:{wps:.2f}<{min_wps}"
        if nsp is not None and nsp > max_nsp:
            return True, f"high_no_speech:{nsp:.2f}>{max_nsp}"
        if logp is not None and logp < min_logprob:
            return True, f"low_logprob:{logp:.2f}<{min_logprob}"
        if comp is not None and comp > max_comp:
            return True, f"high_compression:{comp:.2f}>{max_comp}"
        return False, "ok"

    def compute_metrics(samples: list[dict[str, Any]]) -> dict[str, Any]:
        tp = fp = fn = tn = 0
        details = []
        for s in samples:
            bad = bool(s.get("is_bad", False))
            flagged, reason = evaluate_gate(s)
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
                    "sample_id": s["sample_id"],
                    "condition": s.get("condition"),
                    "is_bad": bad,
                    "gate_flagged": flagged,
                    "gate_reason": reason,
                    "wer": s.get("metrics", {}).get("wer"),
                    "similarity": s.get("similarity_exact"),
                    "words": s.get("word_count"),
                    "wps": round(s.get("words_per_second", 0), 2),
                }
            )

        total = len(samples)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / total if total > 0 else 0.0

        return {
            "total_samples": total,
            "bad_transcripts_count": tp + fn,
            "good_transcripts_count": tn + fp,
            "tp (bad detectado -> fallback correcto)": tp,
            "fp (bueno rechazado -> fallback innecesario)": fp,
            "fn (malo no detectado -> fuga de baja calidad)": fn,
            "tn (bueno aceptado -> transcripcion local conservada)": tn,
            "precision": round(precision, 4),
            "recall (tasa de deteccion de fallos)": round(recall, 4),
            "f1_score": round(f1, 4),
            "accuracy": round(accuracy, 4),
            "samples": details,
        }

    train_metrics = compute_metrics(train_samples)
    test_metrics = compute_metrics(test_samples)

    return {
        "train_set": {
            "description": "MediaSpeech (8) + Audio1 (5) + Audio2 (5) = 18 audios (In-sample)",
            "metrics": train_metrics,
        },
        "test_set": {
            "description": "Audio3 (5) + Audio4 (5) = 10 audios (Held-out generalization)",
            "metrics": test_metrics,
        },
    }


if __name__ == "__main__":
    out = run_split_evaluation()
    print(json.dumps(out, indent=2))
