"""Download only eight audio files from the official MediaSpeech archive.

The archive is streamed (up to 582 MB transferred); only selected audio and
references are retained. No archive paths are extracted onto the filesystem.
"""

import argparse
import csv
import hashlib
import re
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath

from spikes.transcribe import save_json

URL = "https://openslr.trmal.net/resources/108/ES.tgz"


def restore_sample(output: Path) -> None:
    """Restore audio selected by the committed manifest; never rewrite metadata."""
    manifest = output / "manifest.csv"
    with manifest.open(encoding="utf-8-sig", newline="") as manifest_source:
        rows = list(csv.DictReader(manifest_source))
    if not rows:
        raise ValueError("El manifiesto no contiene muestras.")
    expected: dict[str, str] = {}
    for row in rows:
        name = row.get("audio_path", "")
        digest = row.get("sha256", "")
        if not name or not re.fullmatch(r"[A-Za-z0-9_-]+\.flac", name):
            raise ValueError("Ruta de audio inválida en el manifiesto.")
        if name in expected or not digest or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Audio duplicado o SHA-256 inválido en el manifiesto.")
        expected[name] = digest
    missing = {}
    for name, digest in expected.items():
        target = output / name
        if target.is_file():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Audio local modificado: {name}. No se sobrescribirá.")
        else:
            missing[name] = digest
    if not missing:
        print(f"Las {len(expected)} muestras ya están disponibles y verificadas.")
        return
    recovered: dict[str, bytes] = {}
    with urllib.request.urlopen(URL, timeout=120) as response:
        with tarfile.open(fileobj=response, mode="r|gz") as archive:
            for member in archive:
                if not member.isfile() or member.size > 5_000_000:
                    continue
                # Compare full archive names rather than extracting paths supplied by the TAR.
                name = PurePosixPath(member.name).name
                if member.name != f"ES/{name}" or name not in missing:
                    continue
                source = archive.extractfile(member)
                if source is None:
                    continue
                data = source.read()
                if hashlib.sha256(data).hexdigest() != missing[name]:
                    raise ValueError(f"SHA-256 distinto al registrado para {name}.")
                recovered[name] = data
                if len(recovered) == len(missing):
                    break
    if len(recovered) != len(missing):
        raise ValueError("El archivo remoto no contiene todas las muestras registradas.")
    for name, data in recovered.items():
        (output / name).write_bytes(data)
    print(f"Restauradas {len(recovered)} muestras; manifiesto y procedencia conservados.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("datasets/mediaspeech_es"))
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--restore", action="store_true", help="Recuperar audios del manifiesto")
    args = parser.parse_args()
    if args.restore:
        try:
            restore_sample(args.output)
        except (OSError, ValueError, tarfile.TarError) as exc:
            parser.exit(1, f"Error: {exc}\n")
        return
    if not 1 <= args.count <= 30:
        parser.error("count debe estar entre 1 y 30")
    if (args.output / "manifest.csv").exists():
        parser.error("Ya existe un manifiesto; use --restore o elija otra carpeta.")
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
