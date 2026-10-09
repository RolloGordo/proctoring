"""P2: frozen XLS-R embeddings + logistic baseline versus frozen AASIST.

Train/calibration/test are supplied in a manifest, never randomly split clips.
This experiment classifies synthetic content, not the number of speakers or fraud.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import platform
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from typing import Any

from spikes.network import configure_model_downloads
from spikes.transcribe import save_json

XLSR = "facebook/wav2vec2-xls-r-300m"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def operating_point(labels: list[int], scores: list[float], threshold: float) -> dict[str, Any]:
    if (
        len(labels) != len(scores)
        or set(labels) != {0, 1}
        or any(not math.isfinite(s) or not 0 <= s <= 1 for s in scores)
        or not math.isfinite(threshold)
    ):
        raise ValueError("Both classes, equal lengths and finite probabilities are required")
    tp = sum(y == 1 and s >= threshold for y, s in zip(labels, scores, strict=True))
    fp = sum(y == 0 and s >= threshold for y, s in zip(labels, scores, strict=True))
    p = sum(labels)
    n = len(labels) - p
    return {
        "threshold": threshold,
        "tp": tp,
        "fp": fp,
        "fn": p - tp,
        "tn": n - fp,
        "fpr": fp / n,
        "fnr": (p - tp) / p,
        "accuracy": (tp + n - fp) / len(labels),
    }


def detection_metrics(labels: list[int], scores: list[float], threshold: float) -> dict[str, Any]:
    curve = [
        operating_point(labels, scores, t)
        for t in [math.nextafter(1.0, math.inf), *sorted(set(scores), reverse=True)]
    ]
    eer = None
    for a, b in zip(curve, curve[1:]):
        da, db = a["fpr"] - a["fnr"], b["fpr"] - b["fnr"]
        if da <= 0 <= db:
            fraction = -da / (db - da) if db != da else 0
            eer = a["fpr"] + fraction * (b["fpr"] - a["fpr"])
            break
    return operating_point(labels, scores, threshold) | {
        "eer": eer,
        "eer_method": "linear interpolation of empirical ROC crossing FPR=FNR",
        "roc": curve,
    }


def choose_threshold(labels: list[int], scores: list[float]) -> float:
    points = [operating_point(labels, scores, t) for t in sorted({0.0, 1.0, *scores})]
    return float(
        min(points, key=lambda p: (p["fpr"] + p["fnr"], p["fpr"], -p["threshold"]))["threshold"]
    )


def validate_rows(rows: list[dict[str, str]], held_out_engine: str) -> None:
    required = {
        "sample_id",
        "audio_path",
        "sha256",
        "label",
        "engine",
        "split",
        "speaker_id",
        "source_id",
        "text_id",
        "condition",
        "source",
        "license",
        "consent_id",
    }
    seen: set[str] = set()
    hashes: set[str] = set()
    groups: dict[tuple[str, str], str] = {}
    for row in rows:
        if not required <= row.keys() or any(
            not isinstance(row[k], str) or not row[k].strip() for k in required
        ):
            raise ValueError("Missing provenance, consent/license or manifest field")
        if row["label"] not in {"real", "synthetic"}:
            raise ValueError("Label must be real or synthetic")
        if row["split"] not in {"train", "calibration", "test"}:
            raise ValueError("Invalid split")
        if row["condition"] not in {"clean", "speaker_mic", "mixed"}:
            raise ValueError("Invalid recording condition")
        if row["sample_id"] in seen or row["sha256"] in hashes:
            raise ValueError("Duplicate sample or audio hash")
        seen.add(row["sample_id"])
        hashes.add(row["sha256"])
        if (row["label"] == "real") != (row["engine"] == "human"):
            raise ValueError("Real recordings use engine=human only")
        if row["engine"] == held_out_engine and row["split"] != "test":
            raise ValueError("Held-out engine leaked into training/calibration")
        for field in ("speaker_id", "source_id", "text_id"):
            # Mixed recordings must list every component identity/source with |.
            for value in row[field].split("|"):
                if not value.strip():
                    raise ValueError(f"Empty component in {field}")
                key = (field, value.strip())
                if groups.setdefault(key, row["split"]) != row["split"]:
                    raise ValueError(f"{field} leaks across partitions")
    engines = {r["engine"] for r in rows if r["label"] == "synthetic"}
    trained = {r["engine"] for r in rows if r["label"] == "synthetic" and r["split"] == "train"}
    if len(engines) < 3 or len(trained) < 2 or held_out_engine not in engines:
        raise ValueError("Need two training TTS engines and a third held-out engine")
    for split in ("train", "calibration", "test"):
        if {r["label"] for r in rows if r["split"] == split} != {"real", "synthetic"}:
            raise ValueError("Every partition needs real and synthetic recordings")
    test = [r for r in rows if r["split"] == "test"]
    if not any(r["condition"] == "mixed" and r["engine"] == held_out_engine for r in test):
        raise ValueError("Test needs held-out TTS played through speaker and mixed with human")
    if not any(r["condition"] == "speaker_mic" and r["label"] == "real" for r in test):
        raise ValueError("Test needs real speaker/microphone controls to avoid channel confounding")


def load_manifest(path: Path, held_out_engine: str) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    validate_rows(rows, held_out_engine)
    for row in rows:
        audio = (path.parent / row["audio_path"]).resolve()
        if not audio.is_relative_to(path.parent.resolve()) or not audio.is_file():
            raise ValueError("Audio missing or outside dataset")
        if sha256(audio) != row["sha256"]:
            raise ValueError(f"Hash mismatch: {row['sample_id']}")
        row["resolved_path"] = str(audio)
    return rows


def decode_audio(path: Path) -> Any:
    import av
    import numpy as np

    chunks = []
    resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
    count = 0
    with av.open(str(path)) as container:
        for frame in container.decode(audio=0):
            for output in resampler.resample(frame):
                values = output.to_ndarray().reshape(-1)
                count += len(values)
                if count > 30 * 16000:
                    raise ValueError("Segment exceeds 30 seconds; segment before evaluation")
                chunks.append(values)
        for output in resampler.resample(None):
            chunks.append(output.to_ndarray().reshape(-1))
    if not chunks:
        raise ValueError("No decoded audio")
    audio = np.concatenate(chunks)
    if len(audio) < 1600 or len(audio) > 480000 or not np.isfinite(audio).all():
        raise ValueError("Audio must be finite and 0.1..30 seconds")
    return audio


class VoiceModels:
    def __init__(
        self, revision: str, aasist_source: Path, config: Path, weights: Path, offline: bool
    ) -> None:
        configure_model_downloads()
        import torch
        from transformers import AutoFeatureExtractor, AutoModel

        if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
            raise ValueError("XLS-R revision must be a commit SHA")
        torch.manual_seed(20261008)
        self.extractor = AutoFeatureExtractor.from_pretrained(
            XLSR, revision=revision, cache_dir="models", local_files_only=offline
        )
        self.encoder = AutoModel.from_pretrained(
            XLSR, revision=revision, cache_dir="models", local_files_only=offline
        ).eval()
        # Source is an explicitly supplied, reviewed copy of official models/AASIST.py.
        spec = importlib.util.spec_from_file_location("aasist_official", aasist_source)
        if spec is None or spec.loader is None:
            raise ValueError("Cannot load AASIST source")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        settings = json.loads(config.read_text(encoding="utf-8"))["model_config"]
        self.aasist = module.Model(settings).cpu().eval()
        self.aasist.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))

    def infer(self, audio: Any) -> tuple[list[float], float]:
        import numpy as np
        import torch

        inputs = self.extractor(audio, sampling_rate=16000, return_tensors="pt")
        with torch.inference_mode():
            # One unpadded sample: all feature positions are valid.
            embedding = self.encoder(**inputs).last_hidden_state.mean(dim=1)[0].tolist()
            # Official AASIST input is 64600 samples; tile short clips. For long
            # clips score all consecutive windows, average synthetic probabilities.
            probabilities = []
            for start in range(0, len(audio), 64600):
                window = audio[start : start + 64600]
                window = np.tile(window, math.ceil(64600 / len(window)))[:64600]
                _, logits = self.aasist(torch.from_numpy(window).float().unsqueeze(0))
                # Official training labels: spoof=0, bona fide=1.
                probabilities.append(float(torch.softmax(logits, dim=1)[0, 0]))
        return embedding, sum(probabilities) / len(probabilities)


def compare(
    rows: list[dict[str, Any]],
    embeddings: list[list[float]],
    aasist_scores: list[float],
    held_out_engine: str,
) -> dict[str, Any]:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    train = [i for i, row in enumerate(rows) if row["split"] == "train"]
    features = np.asarray(embeddings)
    labels = [int(row["label"] == "synthetic") for row in rows]
    classifier = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=1.0, max_iter=2000, random_state=20261008, class_weight="balanced"),
    )
    classifier.fit(features[train], np.asarray(labels)[train])
    scores = classifier.predict_proba(features)[:, 1].tolist()
    result: dict[str, Any] = {}
    for name, predictions in (("xlsr_logistic", scores), ("aasist_frozen", aasist_scores)):
        calibration = [i for i, row in enumerate(rows) if row["split"] == "calibration"]
        threshold = choose_threshold(
            [labels[i] for i in calibration], [predictions[i] for i in calibration]
        )
        metrics: dict[str, Any] = {"threshold": threshold}
        subsets = {
            "test": [i for i, r in enumerate(rows) if r["split"] == "test"],
            "held_out_engine": [
                i
                for i, r in enumerate(rows)
                if r["split"] == "test" and r["engine"] in {"human", held_out_engine}
            ],
        }
        for condition in ("clean", "speaker_mic", "mixed"):
            subsets[condition] = [
                i
                for i, r in enumerate(rows)
                if r["split"] == "test" and r["condition"] == condition
            ]
        for subset, indices in subsets.items():
            if {labels[i] for i in indices} != {0, 1}:
                metrics[subset] = {
                    "count": len(indices),
                    "metrics": None,
                    "reason": "Both classes needed",
                }
            else:
                metrics[subset] = detection_metrics(
                    [labels[i] for i in indices], [predictions[i] for i in indices], threshold
                )
        result[name] = metrics | {"scores": predictions}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--held-out-engine", required=True)
    parser.add_argument("--xlsr-revision", required=True)
    parser.add_argument("--aasist-source", type=Path, required=True)
    parser.add_argument("--aasist-config", type=Path, required=True)
    parser.add_argument("--aasist-weights", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = load_manifest(args.manifest, args.held_out_engine)
    if args.output.exists():
        raise ValueError("Use a new output path to preserve previous evidence")
    started = perf_counter()
    models = VoiceModels(
        args.xlsr_revision,
        args.aasist_source,
        args.aasist_config,
        args.aasist_weights,
        args.offline,
    )
    load_seconds = perf_counter() - started
    embeddings, aasist_scores, samples = [], [], []
    for row in rows:
        started = perf_counter()
        audio = decode_audio(Path(row["resolved_path"]))
        vector, score = models.infer(audio)
        embeddings.append(vector)
        aasist_scores.append(score)
        samples.append(
            {k: v for k, v in row.items() if k != "resolved_path"}
            | {"audio_seconds": len(audio) / 16000, "inference_seconds": perf_counter() - started}
        )
    metrics = compare(rows, embeddings, aasist_scores, args.held_out_engine)
    save_json(
        args.output,
        {
            "created_at": datetime.now(UTC).isoformat(),
            "manifest_sha256": sha256(args.manifest),
            "scope": "synthetic_content_experiment_not_diarization_or_fraud_detection",
            "held_out_engine": args.held_out_engine,
            "xlsr": XLSR,
            "xlsr_revision": args.xlsr_revision,
            "aasist_source_sha256": sha256(args.aasist_source),
            "aasist_config_sha256": sha256(args.aasist_config),
            "aasist_weights_sha256": sha256(args.aasist_weights),
            "model_load_seconds": load_seconds,
            "seed": 20261008,
            "threshold_selection": "minimum calibration FPR+FNR",
            "environment": {
                "python": platform.python_version(),
                "os": platform.platform(),
                **{p: version(p) for p in ("torch", "transformers", "scikit-learn")},
            },
            "baseline": {
                "pooling": "mean",
                "scaler": "train_only",
                "C": 1.0,
                "class_weight": "balanced",
                "max_iter": 2000,
            },
            "metrics": metrics,
            "samples": samples,
            "limitations": [
                "Held-out means unseen in this experiment, not proven unseen in pretraining",
                "Synthetic content score cannot establish a second speaker",
            ],
        },
    )
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
