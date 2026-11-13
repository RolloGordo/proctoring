#!/usr/bin/env python3
"""Download one pinned Parakeet sherpa-onnx model and verify every artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from huggingface_hub import snapshot_download

from parakeet_transcriber import ARTIFACTS
from spikes.network import configure_model_downloads


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--precision", choices=tuple(ARTIFACTS), default="fp32")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    artifact = ARTIFACTS[args.precision]
    configure_model_downloads()
    args.output.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=artifact.repo_id,
        revision=artifact.revision,
        allow_patterns=list(artifact.files),
        local_dir=args.output,
    )
    verified: dict[str, str] = {}
    for filename, expected in artifact.files.items():
        actual = sha256(args.output / filename)
        if actual != expected:
            raise SystemExit(f"SHA-256 mismatch for {filename}: expected {expected}, got {actual}")
        verified[filename] = actual
    manifest = {
        "repo_id": artifact.repo_id,
        "revision": artifact.revision,
        "precision": args.precision,
        "sha256": verified,
    }
    (args.output / "parakeet-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
