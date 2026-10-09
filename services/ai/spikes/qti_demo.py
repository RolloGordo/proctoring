"""Export a local QTI fixture as API-ready JSON, without sending it anywhere."""

import argparse
from dataclasses import asdict
from pathlib import Path

from spikes.qti_import import parse_qti
from spikes.transcribe import save_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = parse_qti(args.xml.read_bytes())
    questions = []
    for question in result.questions:
        payload = question.copy()
        payload["options"] = [
            {"option_text": text, "is_correct": correct} for text, correct in question["options"]
        ]
        for key in ("points", "correct_numeric_answer", "numeric_tolerance"):
            if payload[key] is not None:
                payload[key] = str(payload[key])
        questions.append(payload)
    if args.output.exists():
        raise ValueError("Choose a new filename to preserve previous evidence")
    save_json(
        args.output,
        {
            "questions": questions,
            "issues": [asdict(i) for i in result.issues],
            "warnings": [asdict(i) for i in result.warnings],
        },
    )
    print(f"Imported: {len(questions)}; skipped: {len(result.issues)}; output: {args.output}")


if __name__ == "__main__":
    main()
