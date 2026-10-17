"""Evaluate a manifest without choosing a model from fabricated metrics."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from spikes.transcribe import Transcriber, save_json


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        raise ValueError("El manifiesto no contiene muestras.")
    ids: set[str] = set()
    for row in rows:
        if not {"sample_id", "audio_path", "reference"}.issubset(row):
            raise ValueError("Faltan sample_id, audio_path o reference.")
        if not row["sample_id"] or row["sample_id"] in ids:
            raise ValueError("Identificador vacío o duplicado.")
        ids.add(row["sample_id"])
        audio = (path.parent / row["audio_path"]).resolve()
        if not audio.is_relative_to(path.parent.resolve()) or not audio.is_file():
            raise ValueError("Audio inexistente o fuera de la carpeta del manifiesto.")
        if row.get("sha256") and hashlib.sha256(audio.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError(f"El audio cambió: {row['sample_id']}")
        row["resolved_path"] = str(audio)
    return rows


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    # Silence has no WER denominator. Report its hallucinations separately.
    speech = [r for r in results if r["metrics"]["reference_words"] > 0]
    words = sum(r["metrics"]["reference_words"] for r in speech)
    edits = sum(r["metrics"]["word_edits"] for r in speech)
    duration = sum(r["audio_seconds"] for r in results)
    inference = sum(r["inference_seconds"] for r in results)
    return {
        "sample_count": len(results),
        "reference_words": words,
        "word_edits": edits,
        "micro_wer": edits / words if words else None,
        "audio_seconds": duration,
        "inference_seconds": inference,
        "aggregate_real_time_factor": inference / duration if duration else None,
        "empty_reference_samples": len(results) - len(speech),
        "empty_reference_inserted_words": sum(
            r["metrics"]["hypothesis_words"]
            for r in results
            if r["metrics"]["reference_words"] == 0
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluar transcripción con referencias")
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--models", nargs="+", choices=["tiny", "base", "small"], default=["base", "small"]
    )
    parser.add_argument("--output", type=Path, default=Path("results/evaluation.json"))
    args = parser.parse_args()
    rows = load_manifest(args.manifest)
    report: dict[str, Any] = {
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "selection": "exploratory_not_final_test",
        "models": {},
    }
    for name in args.models:
        engine = Transcriber(name)
        results = []
        for row in rows:
            item = engine.transcribe(Path(row["resolved_path"]), row["reference"])
            item["sample_id"] = row["sample_id"]
            results.append(item)
            print(f"{name} {row['sample_id']}: {item['inference_seconds']:.2f}s", flush=True)
        report["models"][name] = {"summary": summarize(results), "samples": results}
        save_json(args.output, report)
        print(json.dumps(report["models"][name]["summary"], ensure_ascii=False), flush=True)
        del engine


if __name__ == "__main__":
    main()
