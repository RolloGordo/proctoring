"""P1: small ASR -> multilingual MiniLM -> held-out similarity evaluation.

Reading and dictation are positive for textual similarity, NOT for fraud.
The threshold is selected on calibration only; this spike never emits alerts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import platform
from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from typing import Any

from spikes.network import configure_model_downloads
from spikes.transcribe import Transcriber, save_json

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CLASSES = {"reading", "dictation", "unrelated"}


def rates(labels: list[int], scores: list[float], threshold: float) -> dict[str, Any]:
    if (
        not labels
        or len(labels) != len(scores)
        or set(labels) != {0, 1}
        or any(not math.isfinite(s) or not 0 <= s <= 1 for s in scores)
        or not math.isfinite(threshold)
    ):
        raise ValueError("Finite scores in [0,1], both classes and equal lengths required")
    tp = sum(y == 1 and s >= threshold for y, s in zip(labels, scores, strict=True))
    fp = sum(y == 0 and s >= threshold for y, s in zip(labels, scores, strict=True))
    positives = sum(labels)
    negatives = len(labels) - positives
    return {
        "threshold": threshold,
        "tp": tp,
        "fp": fp,
        "fn": positives - tp,
        "tn": negatives - fp,
        "tpr": tp / positives,
        "fpr": fp / negatives,
        "accuracy": (tp + negatives - fp) / len(labels),
    }


def roc(labels: list[int], scores: list[float]) -> list[dict[str, Any]]:
    # Finite sentinel just above 1 represents rejecting all; safe in strict JSON.
    return [
        rates(labels, scores, value)
        for value in [math.nextafter(1.0, math.inf), *sorted(set(scores), reverse=True)]
    ]


def evaluate_scores(rows: list[dict[str, Any]], reference_threshold: float) -> dict[str, Any]:
    if not 0 <= reference_threshold <= 1:
        raise ValueError("Threshold must be in [0,1]")
    calibration = [r for r in rows if r["split"] == "calibration"]
    test = [r for r in rows if r["split"] == "test"]

    def arrays(samples: list[dict[str, Any]]) -> tuple[list[int], list[float]]:
        return (
            [int(r["label"] != "unrelated") for r in samples],
            [float(r["score"]) for r in samples],
        )

    candidates = roc(*arrays(calibration)) + [rates(*arrays(calibration), 1.0)]
    # Youden J; tie-break lower FPR, then higher threshold. Calibration only.
    chosen = max(
        (p for p in candidates if p["threshold"] <= 1),
        key=lambda p: (p["tpr"] - p["fpr"], -p["fpr"], p["threshold"]),
    )
    curve = roc(*arrays(test))
    auc = sum((b["fpr"] - a["fpr"]) * (b["tpr"] + a["tpr"]) / 2 for a, b in zip(curve, curve[1:]))
    return {
        "selection": "maximize Youden J on calibration; tie: lower FPR, higher threshold",
        "chosen_threshold": chosen["threshold"],
        "calibration": chosen,
        "test": rates(*arrays(test), chosen["threshold"]),
        "test_reference_threshold": rates(*arrays(test), reference_threshold),
        "test_roc": curve,
        "test_auc": auc,
        "test_by_class": {
            label: {
                "count": len(group),
                "above_threshold": sum(r["score"] >= chosen["threshold"] for r in group),
            }
            for label in sorted(CLASSES)
            if (group := [r for r in test if r["label"] == label])
        },
        "interpretation": "FPR is unrelated speech scored similar, NOT false fraud alerts",
    }


def load_pairs(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows: list[dict[str, Any]] = list(csv.DictReader(stream))
    if len(rows) < 60:
        raise ValueError("At least 60 recorded pairs are required")
    required = {
        "sample_id",
        "question_id",
        "question",
        "label",
        "split",
        "speaker_id",
        "audio_path",
        "sha256",
        "reference",
        "consent_id",
    }
    ids: set[str] = set()
    hashes: set[str] = set()
    groups: dict[str, str] = {}
    questions: dict[str, tuple[str, str]] = {}
    for row in rows:
        if not required <= row.keys() or any(
            not isinstance(row[key], str) or not row[key].strip() for key in required
        ):
            raise ValueError("Missing recording, reference, consent or manifest field")
        if row["label"] not in CLASSES or row["split"] not in {"calibration", "test"}:
            raise ValueError("Invalid class or split")
        if row["sample_id"] in ids or row["sha256"] in hashes:
            raise ValueError("Duplicate sample or audio hash")
        ids.add(row["sample_id"])
        hashes.add(row["sha256"])
        if groups.setdefault(row["question_id"], row["split"]) != row["split"]:
            raise ValueError("Question leaks between calibration and test")
        normalized = " ".join(row["question"].casefold().split())
        group = (row["question_id"], row["split"])
        if questions.setdefault(normalized, group) != group:
            raise ValueError("Repeated question with different group or split")
        audio = (path.parent / row["audio_path"]).resolve()
        if not audio.is_relative_to(path.parent.resolve()) or not audio.is_file():
            raise ValueError("Audio missing or outside dataset")
        if hashlib.sha256(audio.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError(f"Audio hash mismatch: {row['sample_id']}")
        row["resolved_path"] = str(audio)
    for split in ("calibration", "test"):
        if {r["label"] for r in rows if r["split"] == split} != CLASSES:
            raise ValueError("Each split needs all three classes")
    return rows


class SimilarityModel:
    backend = "torch"

    def __init__(self, revision: str, offline: bool = False) -> None:
        configure_model_downloads()
        if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
            raise ValueError("Pass a pinned 40-character model commit, not main")
        from sentence_transformers import SentenceTransformer

        self.revision = revision
        self.engine = SentenceTransformer(
            MODEL, revision=revision, device="cpu", cache_folder="models", local_files_only=offline
        )

    def score(self, question: str, transcript: str) -> float:
        if not question.strip():
            raise ValueError("Empty question")
        if not transcript.strip():
            return 0.0
        # Reject truncation: long inputs would otherwise lose part of the question.
        for text in (question, transcript):
            tokens = self.engine.tokenizer(text, truncation=False)["input_ids"]
            if len(tokens) > self.engine.max_seq_length:
                raise ValueError("Text exceeds model context; segment it before evaluation")
        vectors = self.engine.encode([question, transcript], normalize_embeddings=True)
        return max(0.0, min(1.0, float(vectors[0] @ vectors[1])))


class OnnxSimilarityModel:
    """Ejecuta paraphrase-multilingual-MiniLM-L12-v2 con onnxruntime sin torch."""

    def __init__(
        self,
        revision: str,
        *,
        variant: str = "int8",
        offline: bool = True,
        cache_dir: Path | str = "models",
        onnx_path: Path | None = None,
        tokenizer_path: Path | None = None,
        vocab_mode: str = "es_en",
        max_seq_length: int = 128,
        intra_op_num_threads: int = 1,
        enable_cpu_mem_arena: bool = False,
        enable_mem_pattern: bool = False,
        disable_prepacking: bool = False,
    ) -> None:
        if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
            raise ValueError("Pass a pinned 40-character model commit, not main")
        if variant not in ("int8", "fp32"):
            raise ValueError(f"Unsupported ONNX variant '{variant}'. Expected 'int8' or 'fp32'.")
        if vocab_mode not in ("es_en", "full"):
            raise ValueError(f"Unsupported ONNX vocab_mode '{vocab_mode}'.")

        import numpy as np
        import onnxruntime as ort  # type: ignore[import-untyped]
        from tokenizers import Tokenizer

        self._np = np
        self.revision = revision
        self.variant = variant
        self.backend = f"onnx-{variant}"
        self.version = f"multilingual-MiniLM-L12-v2@{revision};backend=onnx-{variant}"
        self.offline = offline
        self.max_seq_length = max_seq_length

        root = Path(cache_dir)
        onnx_dir = root / "onnx_minilm_experiment"
        snap_dir = (
            root
            / "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"
            / "snapshots"
            / revision
        )

        resolved_onnx = onnx_path
        resolved_tok = tokenizer_path
        used_vocab = vocab_mode

        if resolved_onnx is None:
            pruned_candidate = onnx_dir / f"model_{variant}_es_en.onnx"
            full_candidate = onnx_dir / f"model_{variant}.onnx"
            if vocab_mode == "es_en" and pruned_candidate.is_file():
                resolved_onnx = pruned_candidate
                used_vocab = "es_en"
            elif full_candidate.is_file():
                resolved_onnx = full_candidate
                used_vocab = "full"
            else:
                resolved_onnx = pruned_candidate if vocab_mode == "es_en" else full_candidate

        if resolved_tok is None:
            pruned_tok_candidate = onnx_dir / "tokenizer_es_en.json"
            full_tok_candidate = snap_dir / "tokenizer.json"
            if used_vocab == "es_en" and pruned_tok_candidate.is_file():
                resolved_tok = pruned_tok_candidate
            else:
                resolved_tok = full_tok_candidate

        if not resolved_onnx.is_file():
            raise OSError(f"ONNX similarity model file not found: {resolved_onnx}")
        if not resolved_tok.is_file():
            raise OSError(f"ONNX tokenizer file not found: {resolved_tok}")

        self.onnx_path = resolved_onnx
        self.tokenizer_path = resolved_tok
        self.vocab_mode = used_vocab

        self.tokenizer: Any = Tokenizer.from_file(str(resolved_tok))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()

        sess_options = ort.SessionOptions()
        sess_options.enable_cpu_mem_arena = enable_cpu_mem_arena
        sess_options.enable_mem_pattern = enable_mem_pattern
        if disable_prepacking:
            sess_options.add_session_config_entry("session.disable_prepacking", "1")
        if intra_op_num_threads > 0:
            sess_options.intra_op_num_threads = intra_op_num_threads
            sess_options.inter_op_num_threads = 1
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.session = ort.InferenceSession(
            str(resolved_onnx),
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )
        self.input_names = [inp.name for inp in self.session.get_inputs()]

    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> Any:
        np = self._np
        encodings = [self.tokenizer.encode(t) for t in texts]
        for enc in encodings:
            if len(enc.ids) > self.max_seq_length:
                raise ValueError("Text exceeds model context; segment it before evaluation")

        max_len = max(len(enc.ids) for enc in encodings)
        batch_size = len(encodings)
        input_ids = np.zeros((batch_size, max_len), dtype=np.int64)
        attention_mask = np.zeros((batch_size, max_len), dtype=np.int64)
        token_type_ids = np.zeros((batch_size, max_len), dtype=np.int64)

        for idx, enc in enumerate(encodings):
            length = len(enc.ids)
            input_ids[idx, :length] = enc.ids
            attention_mask[idx, :length] = enc.attention_mask
            if enc.type_ids:
                token_type_ids[idx, :length] = enc.type_ids

        feed: dict[str, Any] = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        if "token_type_ids" in self.input_names:
            feed["token_type_ids"] = token_type_ids

        outputs = self.session.run(["last_hidden_state"], feed)
        token_embeddings = outputs[0].astype(np.float32)

        mask_expanded = np.expand_dims(attention_mask, axis=-1).astype(np.float32)
        sum_embeddings = np.sum(token_embeddings * mask_expanded, axis=1)
        sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        pooled = sum_embeddings / sum_mask

        if normalize_embeddings:
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            pooled = pooled / np.clip(norms, a_min=1e-12, a_max=None)
        return pooled

    def score(self, question: str, transcript: str) -> float:
        if not question.strip():
            raise ValueError("Empty question")
        if not transcript.strip():
            return 0.0
        vectors = self.encode([question, transcript], normalize_embeddings=True)
        return max(0.0, min(1.0, float(vectors[0] @ vectors[1])))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--reference-threshold", type=float, required=True)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("results/similarity.json"))
    args = parser.parse_args()
    rows = load_pairs(args.manifest)  # Validate BEFORE downloading or running any model.
    if args.output.exists():
        raise ValueError("Use a new output filename to preserve previous evidence")
    started = perf_counter()
    asr = Transcriber("small", offline=args.offline)
    model = SimilarityModel(args.revision, args.offline)
    load_seconds = perf_counter() - started
    scored = []
    for row in rows:
        started = perf_counter()
        transcription = asr.transcribe(Path(row["resolved_path"]), row["reference"])
        score = model.score(row["question"], transcription["transcript"])
        scored.append(
            {k: v for k, v in row.items() if k != "resolved_path"}
            | {
                "score": score,
                "transcription": transcription,
                "processing_seconds": perf_counter() - started,
            }
        )
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "scope": "similarity_only_no_alerts",
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "model": MODEL,
        "revision": args.revision,
        "asr": "small",
        "score_transform": "cosine normalized embeddings, clipped to [0,1]",
        "model_load_seconds": load_seconds,
        "environment": {
            "python": platform.python_version(),
            "os": platform.platform(),
            "sentence_transformers": version("sentence-transformers"),
        },
        "counts": dict(Counter(r["split"] for r in rows)),
        "speaker_overlap": sorted(
            {r["speaker_id"] for r in rows if r["split"] == "test"}
            & {r["speaker_id"] for r in rows if r["split"] == "calibration"}
        ),
        "metrics": evaluate_scores(scored, args.reference_threshold),
        "samples": scored,
    }
    save_json(args.output, report)
    print(f"Saved {args.output}; this is NOT a fraud detector")


if __name__ == "__main__":
    main()
