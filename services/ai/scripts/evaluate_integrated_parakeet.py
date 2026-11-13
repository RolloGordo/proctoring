#!/usr/bin/env python3
"""Re-evaluate the prior 28-sample comparison and 30 P02 audios via audio_runtime."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from audio_runtime import measure_audio
from spikes.metrics import word_errors
from spikes.synthetic_voice import decode_audio


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    edits = sum(int(row["word_edits"]) for row in rows)
    words = sum(int(row["reference_words"]) for row in rows)
    return {
        "sample_count": len(rows),
        "reference_words": words,
        "word_edits": edits,
        "micro_wer": edits / words if words else None,
        "empty_transcripts": sum(not row["transcript_nonempty"] for row in rows),
        "mean_runtime_seconds": statistics.fmean(float(row["runtime_seconds"]) for row in rows),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_one(
    sample_id: str, condition: str, audio: Path, reference: str, expected_sha: str
) -> dict[str, Any]:
    actual_sha = sha256(audio)
    if expected_sha and actual_sha != expected_sha:
        raise ValueError(f"SHA-256 mismatch: {sample_id}")
    started = time.perf_counter()
    measured = measure_audio(audio, reference)
    runtime = time.perf_counter() - started
    metrics = word_errors(reference, measured["transcript"])
    audio_seconds = len(decode_audio(audio)) / 16_000
    versions = measured["model_versions"]
    return {
        "sample_id": sample_id,
        "condition": condition,
        "audio_sha256": actual_sha,
        "audio_seconds": audio_seconds,
        "reference_words": metrics["reference_words"],
        "word_edits": metrics["word_edits"],
        "wer": metrics["wer"],
        "transcript_nonempty": bool(measured["transcript"].strip()),
        "similarity": measured["similarity"],
        "quality_status": versions.get("asr_quality_status"),
        "quality_reasons": versions.get("asr_quality_reasons"),
        "asr_version": versions.get("asr"),
        "runtime_seconds": runtime,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--p02-manifest", type=Path, required=True)
    parser.add_argument("--baseline-asr-comparison", type=Path, required=True)
    parser.add_argument("--baseline-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.dataset_root

    prior = json.loads(args.baseline_asr_comparison.read_text())
    p01_rows: list[dict[str, Any]] = []
    for dataset, block in prior["candidates"]["faster-whisper-small"]["datasets"].items():
        for sample in block["samples"]:
            audio_root = root / dataset
            if (audio_root / "audio").is_dir():
                audio_root = audio_root / "audio"
            audio = audio_root / sample["audio_file"]
            sample_id = str(sample["sample_id"])
            condition = sample_id.rsplit("_", 1)[-1] if sample_id.startswith("P01_") else dataset
            p01_rows.append(
                run_one(
                    sample_id,
                    condition,
                    audio,
                    str(sample["reference"]),
                    str(sample.get("audio_sha256", "")),
                )
            )

    p02_rows: list[dict[str, Any]] = []
    with args.p02_manifest.open(newline="", encoding="utf-8") as source:
        for sample in csv.DictReader(source):
            audio = root / "validation_new" / sample["audio_path"]
            p02_rows.append(
                run_one(
                    sample["sample_id"],
                    sample["condition"],
                    audio,
                    sample["reference"],
                    sample["sha256"],
                )
            )

    p02_by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in p02_rows:
        p02_by_condition[row["condition"]].append(row)
    baseline = json.loads(args.baseline_validation.read_text())
    prior_parakeet_by_speaker: dict[str, Any] = baseline["engine_summaries"]["parakeet-fp32"][
        "by_speaker"
    ]
    p01_integrated = aggregate(p01_rows)
    p02_integrated = aggregate(p02_rows)
    output = {
        "schema_version": 1,
        "provider_path": "audio_runtime.measure_audio",
        "provider_revision": "5fcc0122fe87e8365e339e467af90c67b746218f",
        "similarity_backend": "onnx-int8",
        "thresholds_changed": False,
        "p01_exact_prior_comparison_set": {
            "note": (
                "The prior 28-row set contains 20 stage_a_own P01 samples and "
                "8 MediaSpeech samples."
            ),
            "integrated": p01_integrated,
            "prior_faster_whisper_small": prior["candidates"]["faster-whisper-small"][
                "combined_summary"
            ],
            "prior_parakeet_fp32_by_speaker": prior_parakeet_by_speaker.get("P01"),
            "samples": p01_rows,
        },
        "p02": {
            "integrated": p02_integrated,
            "prior_parakeet_fp32_by_speaker": prior_parakeet_by_speaker.get("P02"),
            "by_condition": {
                condition: aggregate(rows) for condition, rows in sorted(p02_by_condition.items())
            },
            "samples": p02_rows,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "p01": p01_integrated,
                "p02": p02_integrated,
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
