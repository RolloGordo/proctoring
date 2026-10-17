"""Portable SP-007 demonstration with a verified sample and optional offline mode."""

import argparse
import sys
from pathlib import Path

from spikes.evaluate import load_manifest
from spikes.transcribe import Transcriber, save_json


def select_sample(manifest: Path) -> tuple[Path, str]:
    """Use the reference stored in Git; no ignored TXT sidecar is required."""
    sample = load_manifest(manifest)[0]
    return Path(sample["resolved_path"]), sample["reference"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Demostración de transcripción SP-007")
    parser.add_argument("--audio", type=Path, help="Audio propio opcional")
    parser.add_argument("--reference", type=Path, help="Referencia UTF-8 para un audio propio")
    parser.add_argument(
        "--manifest", type=Path, default=Path("datasets/mediaspeech_es/manifest.csv")
    )
    parser.add_argument("--model", choices=["base", "small", "tiny"], default="small")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("results/demo-local.json"))
    args = parser.parse_args(argv)
    if args.reference and not args.audio:
        parser.error("--reference requiere --audio")
    try:
        if args.audio:
            audio = args.audio
            if not audio.is_file():
                raise ValueError(f"No existe el audio: {audio}")
            reference = args.reference.read_text(encoding="utf-8-sig") if args.reference else None
        else:
            audio, reference = select_sample(args.manifest)
        if reference is not None:
            print(f"Referencia:\n{reference}\n")
        result = Transcriber(args.model, offline=args.offline).transcribe(audio, reference)
        save_json(args.output, result)
        print(result["transcript"] or "[Sin habla transcrita]")
        print(f"Inferencia: {result['inference_seconds']:.3f} s")
        print(f"Carga del modelo: {result['model_load_seconds']:.3f} s")
        if reference is not None and result["metrics"]["wer"] is not None:
            print(f"WER: {result['metrics']['wer'] * 100:.2f} %")
        print(f"Resultado: {args.output}")
        print("Esta demostración transcribe audio; no detecta fraude.")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
