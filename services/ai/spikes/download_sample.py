"""Download only eight audio files from the official MediaSpeech archive.

The archive is streamed (up to 582 MB transferred); only selected audio and
references are retained. No archive paths are extracted onto the filesystem.
"""

import argparse
import csv
import hashlib
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath

from spikes.transcribe import save_json

URL = "https://openslr.trmal.net/resources/108/ES.tgz"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("datasets/mediaspeech_es"))
    parser.add_argument("--count", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.count <= 30:
        parser.error("count debe estar entre 1 y 30")
    if (args.output / "manifest.csv").exists():
        parser.error("Ya existe un manifiesto; use otra carpeta para no sobrescribirlo.")
    args.output.mkdir(parents=True, exist_ok=True)
    audio: dict[str, bytes] = {}
    texts: dict[str, str] = {}
    with urllib.request.urlopen(URL, timeout=120) as response:
        with tarfile.open(fileobj=response, mode="r|gz") as archive:
            for member in archive:
                path = PurePosixPath(member.name)
                if not member.isfile() or member.size > 5_000_000:
                    continue
                if path.suffix == ".txt" or (path.suffix == ".flac" and len(audio) < args.count):
                    source = archive.extractfile(member)
                    if source is None:
                        continue
                    data = source.read()
                    if path.suffix == ".txt":
                        texts[path.stem] = data.decode("utf-8").strip()
                    else:
                        audio[path.stem] = data
                if len(audio) == args.count and all(key in texts for key in audio):
                    break
    if len(audio) != args.count or not all(key in texts for key in audio):
        raise RuntimeError("No se encontraron todas las parejas audio/texto.")
    with (args.output / "manifest.csv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(
            target,
            fieldnames=[
                "sample_id",
                "audio_path",
                "reference",
                "sha256",
                "source",
                "license",
                "split",
            ],
        )
        writer.writeheader()
        for sample_id, data in audio.items():
            name = f"{sample_id}.flac"
            (args.output / name).write_bytes(data)
            (args.output / f"{sample_id}.txt").write_text(texts[sample_id], encoding="utf-8")
            writer.writerow(
                {
                    "sample_id": sample_id,
                    "audio_path": name,
                    "reference": texts[sample_id],
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "source": "MediaSpeech SLR108",
                    "license": "CC BY 4.0",
                    "split": "exploratory",
                }
            )
    save_json(
        args.output / "provenance.json",
        {
            "url": URL,
            "dataset_page": "https://openslr.org/108/",
            "authors": "Kolobov et al. (2021)",
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "selection": f"First {args.count} FLAC entries in archive order; not random",
            "changes": "Subset only; no audio edits. Reference text stripped at edges.",
            "limitations": "Media speech, not student exams; speaker independence unknown.",
        },
    )
    print(f"Preparadas {len(audio)} muestras en {args.output}")


if __name__ == "__main__":
    main()
