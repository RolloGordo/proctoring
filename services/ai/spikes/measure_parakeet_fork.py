"""Measure Parakeet initialization/decode before and after a Linux fork.

Run in the configured model environment with PARakeet_MODEL_DIR set to an
already verified FP32 model directory. This script is an operational probe, not
an automated unit test.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import time
from pathlib import Path

import numpy as np

from parakeet_transcriber import ParakeetTranscriber


def _child(mode: str, model_dir: str, queue: mp.Queue) -> None:
    try:
        started = time.perf_counter()
        model = ParakeetTranscriber(model_dir, precision="fp32", num_threads=4)
        load_seconds = time.perf_counter() - started
        audio = np.zeros(16_000, dtype=np.float32)
        started = time.perf_counter()
        model._recognizer.create_stream().accept_waveform(16_000, audio)
        queue.put({"mode": mode, "load_seconds": load_seconds, "status": "constructed"})
    except Exception as exc:  # pragma: no cover - reports native runtime behavior
        queue.put({"mode": mode, "status": "error", "error": type(exc).__name__})


def main() -> int:
    if os.name != "posix":
        raise SystemExit("Linux/POSIX fork is required")
    model_dir = os.environ.get("PARAKEET_MODEL_DIR")
    if not model_dir:
        raise SystemExit("Set PARAKEET_MODEL_DIR to verified FP32 model files")
    model = ParakeetTranscriber(Path(model_dir), precision="fp32", num_threads=4)
    del model  # This simple probe validates construction/fork, not decoding quality.
    ctx = mp.get_context("fork")
    queue = ctx.Queue()
    process = ctx.Process(target=_child, args=("child-initialized", model_dir, queue))
    process.start()
    print(queue.get(timeout=60))
    process.join(timeout=60)
    return 0 if process.exitcode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
