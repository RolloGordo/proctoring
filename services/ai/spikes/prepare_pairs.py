"""Build a manifest from reviewed recording metadata; never invent recordings."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path


def prepare(plan: Path, dataset: Path) -> Path:
    samples = json.loads(plan.read_text(encoding="utf-8"))["samples"]
    fields = [
        "sample_id",
        "question_id",
        "question",
        "label",
        "split",
        "speaker_id",
        "consent_id",
        "audio_path",
        "sha256",
        "reference",
    ]
    output = dataset / "manifest.csv"
    if output.exists():
        raise ValueError("Manifest exists; preserve the original evidence")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for sample in samples:
        row = {field: sample.get(field, "") for field in fields}
        if any(not row[field].strip() for field in fields if field != "sha256"):
            raise ValueError(f"Incomplete recording metadata: {row['sample_id']}")
        audio = (dataset / row["audio_path"]).resolve()
        if not audio.is_relative_to(dataset.resolve()) or not audio.is_file():
            raise ValueError("Missing audio or path outside dataset")
        row["sha256"] = hashlib.sha256(audio.read_bytes()).hexdigest()
        writer.writerow(row)
    output.write_text(buffer.getvalue(), encoding="utf-8", newline="")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    print(prepare(args.plan, args.dataset))


if __name__ == "__main__":
    main()
