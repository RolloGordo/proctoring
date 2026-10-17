"""Registra/valida un dataset de visión; no sube vídeos ni fotos a Git."""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'datasets'
COLS = ('id', 'archivo', 'persona', 'condicion', 'duracion_s', 'sha256')
FORMAT = re.compile(r'^([0-9]{2}):([0-9]{2})-([0-9]{2}):([0-9]{2})\s+([a-z_]+)$')


def etiquetas(video_id: str):
    path = ROOT / 'etiquetas' / f'{video_id}.txt'
    lineas = [x.strip() for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
    if not lineas:
        raise ValueError(f'Etiquetas vacías: {path}')
    intervalos = []
    for line in lineas:
        match = FORMAT.fullmatch(line)
        if not match:
            raise ValueError(f'Etiqueta inválida: {line}')
        sm, ss, em, es, condicion = match.groups()
        inicio, fin = int(sm) * 60 + int(ss), int(em) * 60 + int(es)
        if fin <= inicio or (intervalos and inicio < intervalos[-1][1]):
            raise ValueError(f'Segmentos solapados o vacíos: {line}')
        intervalos.append((inicio, fin, condicion))
    return intervalos


def ruta_segura(path: str):
    target = (ROOT / path).resolve()
    if not target.is_relative_to(ROOT.resolve()):
        raise ValueError('Ruta fuera del dataset')
    return target


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open('rb') as entrada:
        for block in iter(lambda: entrada.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def cargar():
    with (ROOT / 'manifest.csv').open(newline='', encoding='utf-8') as fp:
        filas = list(csv.DictReader(fp))
    ids = set()
    for fila in filas:
        if fila['id'] in ids:
            raise ValueError(f'ID duplicado: {fila["id"]}')
        ids.add(fila['id'])
        archivo = ruta_segura(fila['archivo'])
        if not archivo.is_file():
            raise ValueError(f'Archivo inexistente: {archivo}')
        if sha256(archivo) != fila['sha256']:
            raise ValueError(f'Hash no coincide: {archivo}')
        if float(fila['duracion_s']) <= 0:
            raise ValueError(f'Duración inválida: {fila["id"]}')
        if not etiquetas(fila['id']):
            raise ValueError(f'Faltan etiquetas: {fila["id"]}')
    return filas


def registrar(args):
    video = ruta_segura(args.archivo)
    if not video.is_file():
        raise FileNotFoundError(video)
    intervalos = etiquetas(args.id)
    data = []
    with (ROOT / 'manifest.csv').open(newline='', encoding='utf-8') as fp:
        data = list(csv.DictReader(fp))
    if any(row['id'] == args.id for row in data):
        raise ValueError(f'El ID ya está registrado: {args.id}')
    row = dict(zip(COLS, (args.id, args.archivo, args.persona, args.condicion,
                          str(intervalos[-1][1]), sha256(video))))
    with (ROOT / 'manifest.csv').open('w', newline='', encoding='utf-8') as fp:
        writer = csv.DictWriter(fp, fieldnames=COLS)
        writer.writeheader(); writer.writerows([*data, row])
    provenance = ROOT / 'provenance.json'
    document = json.loads(provenance.read_text(encoding='utf-8'))
    document['sample_count'] = len(data) + 1
    document['collection_status'] = 'recordings_available_locally'
    provenance.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Registrado {args.id}; SHA-256={row["sha256"]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('verificar')
    add = sub.add_parser('registrar')
    add.add_argument('id'); add.add_argument('archivo'); add.add_argument('persona')
    add.add_argument('condicion')
    args = parser.parse_args()
    if args.command == 'registrar':
        registrar(args)
    else:
        filas = cargar()
        if not filas:
            raise SystemExit('INCOMPLETO: aún no hay videos consentidos registrados.')
        print(f'OK: {len(filas)} videos con SHA-256 y etiquetas válidos')


if __name__ == '__main__':
    main()
