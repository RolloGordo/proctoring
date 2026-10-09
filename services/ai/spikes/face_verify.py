"""J4 / SPEC-005: medir FAR, FRR y P90 de pares de rostros en CPU.

CSV: reference,capture,same_person (1/0). Imágenes privadas sólo en disco local.
Uso: python spikes/face_verify.py pairs.csv --output results/face_verify.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
import sys
import time
from pathlib import Path

# Permite ejecutar directamente `python spikes/face_verify.py` desde services/ai.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from face_pipeline import FaceInconclusive, cosine_similarity, embedding_from_bytes


def report(pairs: list[tuple[float, bool]], latencies_ms: list[float]) -> dict:
    if not pairs:
        raise ValueError("Se requieren pares de evaluación consentidos")
    if not any(real for _, real in pairs) or not any(not real for _, real in pairs):
        raise ValueError("Incluir pares genuinos y de impostores")
    # Busca el umbral que minimiza FAR+FRR. Estos números NO calibran un modelo
    # de producción con muestras pequeñas; separar entrenamiento y prueba final.
    thresholds = sorted(set([0.0, 1.0, *(x for x, _ in pairs)]))
    curves = []
    for t in thresholds:
        genuine = [score for score, real in pairs if real]
        impostor = [score for score, real in pairs if not real]
        far = sum(score >= t for score in impostor) / len(impostor)
        frr = sum(score < t for score in genuine) / len(genuine)
        curves.append({"threshold": t, "FAR": far, "FRR": frr})
    recommended = min(curves, key=lambda row: (row["FAR"] + row["FRR"], row["FAR"]))
    ordered = sorted(latencies_ms)
    p90 = ordered[math.ceil(0.9 * len(ordered)) - 1] if ordered else None
    return {
        "pairs_genuine": sum(real for _, real in pairs),
        "pairs_impostor": sum(not real for _, real in pairs),
        "curves": curves,
        "recommended_threshold_exploratory": recommended,
        "latency_p90_cpu_ms": p90,
        "latency_p90_under_500ms": p90 < 500 if p90 is not None else None,
        "latency_mean_cpu_ms": statistics.mean(ordered) if ordered else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("results/face_verify.json"))
    args = parser.parse_args()
    base = args.manifest.resolve().parent
    with args.manifest.open(newline="", encoding="utf8") as f:
        rows = list(csv.DictReader(f))
    all_pairs: list[tuple[float, bool]] = []
    durations: list[float] = []
    failures: list[dict[str, object]] = []
    for row in rows:
        try:
            images = []
            for name in ("reference", "capture"):
                path = (base / row[name]).resolve()
                if not path.is_relative_to(base) or not path.is_file():
                    raise ValueError("Ruta inexistente o fuera de manifiesto")
                images.append(path)
            start = time.perf_counter()
            ref_vector = embedding_from_bytes(images[0].read_bytes())
            cap_vector = embedding_from_bytes(images[1].read_bytes())
            score = cosine_similarity(ref_vector, cap_vector)
            durations.append((time.perf_counter() - start) * 1000)
            all_pairs.append((score, row["same_person"].strip() in ("1", "true", "True")))
        except FaceInconclusive as exc:
            failures.append({"row": len(all_pairs) + len(failures) + 1, "reason": str(exc)})
    result = {
        "status": "exploratory_not_final_test",
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "model": "InsightFace CPU (FACE_MODEL_NAME)",
        "environment": platform.platform(),
        "measurements": report(all_pairs, durations),
        "inconclusive_pairs": failures,
        "limitations": (
            "Tiempo incluye decodificación e inferencia de dos caras; "
            "cold-start/model-load no incluido. Por medir integración end-to-end."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print(json.dumps(result["measurements"], indent=2))


if __name__ == "__main__":
    main()
