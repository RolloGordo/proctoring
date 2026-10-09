"""Evalúa predicciones exportadas del spike contra intervalos etiquetados.

Uso: python tools/evaluate.py --predictions-dir datasets/predictions --split final
"""
import argparse
import csv
import hashlib
import json
import platform
from pathlib import Path
from dataset import ROOT, etiquetas

NAMES = ('gaze_away', 'face_absent', 'extra_person')
DURATION_MS = {'gaze_away': 3000, 'face_absent': 5000, 'extra_person': 2000}
LABELS = {
    'gaze_away': {'mirando_lado'},
    'face_absent': {'sin_rostro'},
    'extra_person': {'persona_extra'},
}


def episodes(rows: list[dict], name: str, min_ms: int, tolerance_ms: int = 400):
    """Filtra secuencias con duración, sin convertir cada frame en evento."""
    entries = sorted((float(r['time_ms']), r[name] == '1') for r in rows)
    start = last_true = None
    found = []

    def append():
        if start is not None and last_true is not None and last_true - start >= min_ms:
            found.append((start, last_true))

    for t, active in entries:
        if start is not None and last_true is not None and t - last_true > tolerance_ms:
            append()
            start = last_true = None
        if active:
            if start is None:
                start = t
            last_true = t
    append()
    return found


def metrics(counts):
    tp, tn, fp, fn = (counts[x] for x in ('tp', 'tn', 'fp', 'fn'))
    n = tp + tn + fp + fn
    return {
        'confusion_matrix': counts,
        'accuracy': (tp + tn) / n if n else None,
        'fpr': fp / (fp + tn) if fp + tn else None,
        'samples': n,
        'target_accuracy_at_least_0_8': (tp + tn) / n >= .8 if n else None,
        'target_fpr_less_than_0_2': fp / (fp + tn) < .2 if fp + tn else None,
    }


def evaluate(predictions: Path, out: Path, split: str):
    with (ROOT / 'manifest.csv').open(newline='', encoding='utf-8') as f:
        clips = list(csv.DictReader(f))
    if not clips:
        raise ValueError('No hay videos registrados: no se pueden calcular accuracy/FPR reales')
    totals = {key: dict(tp=0, tn=0, fp=0, fn=0) for key in NAMES}
    details = []
    for clip in clips:
        csv_path = predictions / f'{clip["id"]}.csv'
        if not csv_path.is_file():
            raise FileNotFoundError(f'No hay inferencias para {clip["id"]}: {csv_path}')
        intervals = etiquetas(clip['id'])
        with csv_path.open(newline='', encoding='utf-8') as f:
            frames = list(csv.DictReader(f))
        # Evaluación por ventanas de 1 segundo (no por fotograma) para impedir sesgo por FPS.
        buckets = {}
        for row in frames:
            second = int(float(row['time_ms']) // 1000)
            if second < 0:
                continue
            buckets.setdefault(second, []).append(row)
        confirmed = {name: episodes(frames, name, DURATION_MS[name]) for name in NAMES}
        used = 0
        for second, rows in buckets.items():
            label = next((name for lo, hi, name in intervals if lo <= second < hi), None)
            if label is None:
                continue
            used += 1
            for name in NAMES:
                # Ventana positiva sólo si hubo un episodio confirmado que toca
                # ese segundo. Un giro breve no produce alerta por sí mismo.
                predicted = any(lo < (second + 1) * 1000 and hi >= second * 1000
                                for lo, hi in confirmed[name])
                truth = label in LABELS[name]
                group = 'tp' if predicted and truth else 'fp' if predicted else 'fn' if truth else 'tn'
                totals[name][group] += 1
        if not used:
            raise ValueError(f'No se pudieron comparar intervalos de {clip["id"]}')
        details.append({'id': clip['id'], 'seconds_evaluated': used, 'prediction_sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest()})
    summary = {
        'task': 'SPEC-007', 'selection': split,
        'method': 'one-second windows of duration-filtered episodes, aligned to labeled intervals',
        'manifest_sha256': hashlib.sha256((ROOT/'manifest.csv').read_bytes()).hexdigest(),
        'platform': platform.platform(),
        'detectors': {key: metrics(counts) for key, counts in totals.items()},
        'samples': details,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(summary['detectors'], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions-dir', type=Path, required=True)
    parser.add_argument('--split', choices=['exploratory_not_final_test', 'final_test'], default='exploratory_not_final_test')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'results/evaluation.json')
    a = parser.parse_args()
    evaluate(a.predictions_dir, a.output, a.split)
