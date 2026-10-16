"""Valida un evaluation.json REAL; sin muestras nunca informa cumplimiento.

Uso: python tools/verificar_metricas.py results/evaluation.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DETECTORES = ("gaze_away", "face_absent", "extra_person")


def comprobar(path: Path) -> tuple[bool, list[str]]:
    if not path.is_file():
        return False, ["No existe el archivo de resultados; primero evaluar clips consentidos."]
    data = json.loads(path.read_text(encoding="utf-8"))
    msgs: list[str] = []
    valid = data.get("selection") == "final_test"
    if not valid:
        msgs.append("El conjunto NO está marcado final_test; no es prueba final.")
    for name in DETECTORES:
        metrics = data.get("detectors", {}).get(name)
        if not isinstance(metrics, dict):
            msgs.append(f"{name}: no hay datos.")
            valid = False
            continue
        acc, fpr, fnr, n = (metrics.get(k) for k in ("accuracy", "fpr", "fnr", "samples"))
        cm = metrics.get("confusion_matrix")
        if not isinstance(cm, dict) or not all(isinstance(cm.get(k), int) for k in ("tp", "tn", "fp", "fn")):
            msgs.append(f"{name}: matriz de confusión inválida.")
            valid = False
            continue
        if not isinstance(n, int) or n == 0 or sum(cm[k] for k in ("tp", "tn", "fp", "fn")) != n:
            msgs.append(f"{name}: faltan muestras o los conteos no coinciden.")
            valid = False
            continue
        if not isinstance(acc, (float, int)) or not isinstance(fpr, (float, int)) or not isinstance(fnr, (float, int)):
            msgs.append(f"{name}: accuracy, FPR o FNR no medido.")
            valid = False
            continue
        passed = acc >= .8 and fpr < .2
        msgs.append(f"{name}: accuracy={acc:.3f}, FPR={fpr:.3f}, FNR={fnr:.3f}, muestras={n}: {'CUMPLE' if passed else 'NO CUMPLE'}")
        valid &= passed
    return valid, msgs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    passed, lines = comprobar(args.results)
    print("\n".join(lines))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
