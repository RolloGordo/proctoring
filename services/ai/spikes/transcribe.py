"""SP-007: local Spanish ASR, timed through complete generator consumption."""

import argparse
import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from typing import Any

from spikes.metrics import word_errors


class Transcriber:
    """Load once so dataset timings separate model setup from inference."""

    def __init__(self, model: str = "small", threads: int = 4, offline: bool = False) -> None:
        from spikes.network import configure_model_downloads

        configure_model_downloads()
        from faster_whisper import WhisperModel

        started = perf_counter()
        self.engine = WhisperModel(
            model,
            device="cpu",
            compute_type="int8",
            cpu_threads=threads,
            download_root="models",
            local_files_only=offline,
        )
        self.load_seconds = perf_counter() - started
        self.model = model
        self.threads = threads

    def transcribe(self, audio: Path, reference: str | None = None) -> dict[str, Any]:
        if not audio.is_file():
            raise ValueError(f"No existe el audio: {audio}")
        started = perf_counter()
        segments, info = self.engine.transcribe(
            str(audio),
            language="es",
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        # Whisper executes lazily: the timer must include iterating every segment.
        output = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]
        elapsed = perf_counter() - started
        transcript = " ".join(s["text"] for s in output)
        result: dict[str, Any] = {
            "schema_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "audio_file": audio.name,
            "audio_sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
            "model": self.model,
            "device": "cpu",
            "compute_type": "int8",
            "cpu_threads": self.threads,
            "beam_size": 5,
            "language": "es",
            "vad_filter": True,
            "condition_on_previous_text": False,
            "model_load_seconds": self.load_seconds,
            "inference_seconds": elapsed,
            "audio_seconds": info.duration,
            "real_time_factor": elapsed / info.duration if info.duration > 0 else None,
            "transcript": transcript,
            "segments": output,
            "environment": {
                "python": platform.python_version(),
                "os": platform.platform(),
                "processor": platform.processor(),
                "faster_whisper": version("faster-whisper"),
                "ctranslate2": version("ctranslate2"),
            },
            "scope": "transcription_only_no_fraud_detection",
        }
        if reference is not None:
            result["reference"] = reference
            result["metrics"] = word_errors(reference, transcript)
        return result


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Transcribir audio en español (SP-007)")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--model", choices=["tiny", "base", "small"], default="small")
    parser.add_argument("--reference", type=Path, help="Texto de referencia UTF-8 opcional")
    parser.add_argument("--output", type=Path, default=Path("results/transcription.json"))
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--offline", action="store_true", help="Usar solo modelos ya descargados")
    args = parser.parse_args()
    try:
        if not args.audio.is_file() or args.threads < 1:
            raise ValueError("Se necesita un audio existente y threads mayor que cero.")
        reference = args.reference.read_text(encoding="utf-8-sig") if args.reference else None
        result = Transcriber(args.model, args.threads, args.offline).transcribe(
            args.audio, reference
        )
        save_json(args.output, result)
        print(result["transcript"] or "[Sin habla transcrita]")
        print(f"Inferencia: {result['inference_seconds']:.3f} s")
        print(f"Carga/descarga del modelo: {result['model_load_seconds']:.3f} s")
        if "metrics" in result and result["metrics"]["wer"] is not None:
            print(f"WER: {result['metrics']['wer'] * 100:.2f} %")
        print(f"Resultado: {args.output}")
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
