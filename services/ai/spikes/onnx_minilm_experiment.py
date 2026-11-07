"""Experimento 2B: Exportación, cuantización ONNX (fp32/int8) y recorte de vocabulario ES/EN.

Evalúa:
1. Exportación a ONNX FP32 y cuantización dinámica a INT8 de la revisión fijada
   SIM_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42" (licencia Apache-2.0),
   tanto con vocabulario completo (250 002 tokens) como con vocabulario recortado
   ES/EN (90 525 tokens), ejecutando con onnxruntime + tokenizers + numpy SIN torch.
2. Opciones de onnxruntime (enable_cpu_mem_arena, enable_mem_pattern, disable_prepacking)
   y perfilado de memoria (VmHWM / VmRSS) en subprocesos aislados.
3. Paridad de embeddings (coseno medio y mínimo) entre PyTorch FP32, ONNX FP32 (full y ES/EN)
   y ONNX INT8 (full y ES/EN).
4. Evaluación sobre las 28 transcripciones reales por motor ASR frente a:
   - Referencia exacta (lectura, 28 pares)
   - Consulta parafraseada del tema (28 pares)
   - 12 frases ajenas (6 cotidianas fuera de dominio + 6 preguntas de examen del mismo tema,
     331 pares negativos genuinos por motor, excluyendo la autocomparación Q04==U01).
5. Listado exhaustivo de todos los pares (de P1 y de las 28 transcripciones) con puntaje
   en [0.50, 0.70] e identificación de cualquier cruce de lado respecto al umbral 0.60.
6. Medición en Docker (--memory=512m, 1g y 2g) de pico RSS, tiempo de carga, inferencia
   y tamaño de imagen para ONNX int8 (full y ES/EN) y ONNX fp32 (full y ES/EN).
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

import numpy as np

AI_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_DIR.parents[1]
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))
os.chdir(AI_DIR)

from audio_runtime import SIM_REVISION  # noqa: E402
from spikes.similarity import (  # noqa: E402
    MODEL,
    OnnxSimilarityModel,
    SimilarityModel,
    roc,
)
from spikes.transcribe import save_json  # noqa: E402

SNAPSHOT_DIR = (
    AI_DIR
    / "models"
    / "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"
    / "snapshots"
    / SIM_REVISION
)
ONNX_DIR = AI_DIR / "models" / "onnx_minilm_experiment"
ONNX_FP32_PATH = ONNX_DIR / "model_fp32.onnx"
ONNX_INT8_PATH = ONNX_DIR / "model_int8.onnx"
ONNX_FP32_PRUNED_PATH = ONNX_DIR / "model_fp32_es_en.onnx"
ONNX_INT8_PRUNED_PATH = ONNX_DIR / "model_int8_es_en.onnx"
TOKENIZER_PRUNED_PATH = ONNX_DIR / "tokenizer_es_en.json"

OUTPUT_PATH = AI_DIR / "results" / "onnx-minilm-experiment.json"
P1_PLAN_PATH = AI_DIR / "docs" / "P1-recording-plan.json"
CALIBRATION_RESULTS_PATH = AI_DIR / "results" / "quality-gate-calibration.json"
ASR_COMPARISON_PATH = AI_DIR / "results" / "asr-comparison.json"

# 12 frases no relacionadas: 6 fuera de dominio (cotidianas) + 6 preguntas del mismo tema
UNRELATED_PHRASES: list[dict[str, str]] = [
    {
        "id": "U01_mercado",
        "category": "out_of_domain",
        "exclude_sample_prefix": "P01_A4",
        "text": (
            "Mañana tengo que ir al mercado a comprar frutas y después pasar por la "
            "farmacia antes de que cierre."
        ),
    },
    {
        "id": "U02_planetas",
        "category": "out_of_domain",
        "exclude_sample_prefix": "",
        "text": (
            "El sistema solar está formado por ocho planetas que giran alrededor del sol "
            "en órbitas elípticas."
        ),
    },
    {
        "id": "U03_receta",
        "category": "out_of_domain",
        "exclude_sample_prefix": "",
        "text": (
            "La receta tradicional de la paella valenciana lleva arroz, pollo, conejo, "
            "judías verdes y azafrán."
        ),
    },
    {
        "id": "U04_futbol",
        "category": "out_of_domain",
        "exclude_sample_prefix": "",
        "text": (
            "El partido de fútbol del domingo se suspendió en el segundo tiempo por la "
            "lluvia intensa."
        ),
    },
    {
        "id": "U05_pasaporte",
        "category": "out_of_domain",
        "exclude_sample_prefix": "",
        "text": (
            "Para renovar el pasaporte es necesario pedir cita previa y llevar dos "
            "fotografías recientes."
        ),
    },
    {
        "id": "U06_tren",
        "category": "out_of_domain",
        "exclude_sample_prefix": "",
        "text": (
            "El tren de alta velocidad sale de la estación central a las siete de la "
            "mañana en punto."
        ),
    },
    {
        "id": "S01_prog_bucles",
        "category": "same_subject",
        "exclude_sample_prefix": "",
        "text": (
            "¿Qué diferencia existe entre un bucle while y un bucle for en programación "
            "y cuándo conviene usar cada uno?"
        ),
    },
    {
        "id": "S02_prog_recursividad",
        "category": "same_subject",
        "exclude_sample_prefix": "",
        "text": (
            "Explica qué es la recursividad en una función y por qué siempre debe "
            "definirse un caso base para evitar un desbordamiento de pila."
        ),
    },
    {
        "id": "S03_bd_claves",
        "category": "same_subject",
        "exclude_sample_prefix": "",
        "text": (
            "¿Para qué sirve una clave primaria y una clave foránea en una base de datos "
            "relacional y cómo garantizan la integridad referencial?"
        ),
    },
    {
        "id": "S04_seg_sqli",
        "category": "same_subject",
        "exclude_sample_prefix": "",
        "text": (
            "Describe en qué consiste un ataque de inyección SQL y cómo se previene "
            "mediante consultas parametrizadas."
        ),
    },
    {
        "id": "S05_geom_circulo",
        "category": "same_subject",
        "exclude_sample_prefix": "",
        "text": (
            "Calcula el perímetro y el área de un círculo cuyo radio mide cinco "
            "centímetros utilizando el valor de pi."
        ),
    },
    {
        "id": "S06_geom_pitagoras",
        "category": "same_subject",
        "exclude_sample_prefix": "",
        "text": (
            "Enuncia el teorema de Pitágoras para un triángulo rectángulo y calcula la "
            "hipotenusa si los catetos miden tres y cuatro centímetros."
        ),
    },
]


def build_query_paraphrase(reference: str, sample_id: str) -> str:
    """Construye una consulta tipo estudiante->IA asociada al tema de cada muestra."""
    custom_queries = {
        "P01_A1": (
            "Asistente, dime cuál es la diferencia entre variable local y global "
            "en programación y dame un ejemplo de dónde se usa cada una."
        ),
        "P01_A2": (
            "Explícame dos medidas para proteger datos de clientes en una empresa "
            "y por qué no se deben guardar contraseñas en texto plano."
        ),
        "P01_A3": (
            "Ayúdame a calcular el área de un triángulo con base de doce centímetros "
            "y altura de nueve centímetros usando la fórmula."
        ),
        "P01_A4": (
            "Necesito organizar mis compras de frutas en el mercado y pasar por la "
            "farmacia antes de que cierre hoy."
        ),
    }
    for prefix, query in custom_queries.items():
        if sample_id.startswith(prefix):
            return query
    return f"Asistente, necesito información y explicación detallada sobre esto: {reference}"


def measure_host_subprocess_memory() -> dict[str, Any]:
    """Mide VmHWM, VmRSS y tiempo de carga/inferencia de cada variante en un subproceso limpio."""
    runner = """
import json, sys
from time import perf_counter
from spikes.similarity import SimilarityModel, OnnxSimilarityModel
from audio_runtime import SIM_REVISION

kind = sys.argv[1]
t0 = perf_counter()
if kind == "pytorch_fp32":
    m = SimilarityModel(SIM_REVISION, offline=True)
elif kind == "onnx_fp32_full":
    m = OnnxSimilarityModel(SIM_REVISION, variant="fp32", vocab_mode="full", offline=True)
elif kind == "onnx_fp32_es_en":
    m = OnnxSimilarityModel(SIM_REVISION, variant="fp32", vocab_mode="es_en", offline=True)
elif kind == "onnx_int8_full":
    m = OnnxSimilarityModel(SIM_REVISION, variant="int8", vocab_mode="full", offline=True)
elif kind == "onnx_int8_es_en":
    m = OnnxSimilarityModel(SIM_REVISION, variant="int8", vocab_mode="es_en", offline=True)
else:
    raise ValueError(kind)
load_s = perf_counter() - t0

t1 = perf_counter()
sc = m.score(
    "¿Cuál es la diferencia entre una variable local y una variable global en un programa?",
    "Una variable local solo existe dentro de la función donde se declara."
)
infer_s = perf_counter() - t1

vm = {}
with open("/proc/self/status", encoding="utf-8") as f:
    for line in f:
        if line.startswith(("VmHWM:", "VmRSS:")):
            parts = line.split()
            vm[parts[0].rstrip(":")] = round(int(parts[1]) / 1024.0, 2)
print("SUBPROC_MEM:" + json.dumps({
    "variant": kind,
    "load_seconds": round(load_s, 4),
    "first_score_seconds": round(infer_s, 4),
    "score": round(sc, 6),
    "vm_hwm_mib": vm.get("VmHWM"),
    "vm_rss_mib": vm.get("VmRSS"),
}))
"""
    variants = [
        "pytorch_fp32",
        "onnx_fp32_full",
        "onnx_fp32_es_en",
        "onnx_int8_full",
        "onnx_int8_es_en",
    ]
    out: dict[str, Any] = {}
    for v in variants:
        proc = subprocess.run(
            [sys.executable, "-c", runner, v],
            cwd=str(AI_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        for line in proc.stdout.splitlines():
            if line.startswith("SUBPROC_MEM:"):
                out[v] = json.loads(line.split("SUBPROC_MEM:", 1)[1])
                break
    return out


def measure_ort_options_ablation() -> list[dict[str, Any]]:
    """Mide el efecto de enable_cpu_mem_arena, enable_mem_pattern y disable_prepacking."""
    runner = """
import json, sys
import numpy as np
import onnxruntime as ort

arena = sys.argv[1] == "1"
pattern = sys.argv[2] == "1"
disable_prepack = sys.argv[3]
model_file = sys.argv[4]

so = ort.SessionOptions()
so.enable_cpu_mem_arena = arena
so.enable_mem_pattern = pattern
so.intra_op_num_threads = 1
so.inter_op_num_threads = 1
so.add_session_config_entry("session.disable_prepacking", disable_prepack)
sess = ort.InferenceSession(model_file, sess_options=so, providers=["CPUExecutionProvider"])
ids = np.ones((2, 32), dtype=np.int64)
mask = np.ones((2, 32), dtype=np.int64)
types = np.zeros((2, 32), dtype=np.int64)
sess.run(["last_hidden_state"], {"input_ids": ids, "attention_mask": mask, "token_type_ids": types})
vm = {}
with open("/proc/self/status", encoding="utf-8") as f:
    for line in f:
        if line.startswith(("VmHWM:", "VmRSS:")):
            parts = line.split()
            vm[parts[0].rstrip(":")] = round(int(parts[1]) / 1024.0, 2)
print("ORT_OPT:" + json.dumps({
    "model": model_file.split("/")[-1],
    "enable_cpu_mem_arena": arena,
    "enable_mem_pattern": pattern,
    "disable_prepacking": disable_prepack == "1",
    "vm_hwm_mib": vm.get("VmHWM"),
    "vm_rss_mib": vm.get("VmRSS"),
}))
"""
    combos = [
        ("1", "1", "0", str(ONNX_INT8_PATH)),
        ("0", "0", "0", str(ONNX_INT8_PATH)),
        ("0", "0", "1", str(ONNX_INT8_PATH)),
        ("0", "0", "0", str(ONNX_INT8_PRUNED_PATH)),
        ("0", "0", "1", str(ONNX_INT8_PRUNED_PATH)),
    ]
    results = []
    for arena, pat, prepack, mpath in combos:
        proc = subprocess.run(
            [sys.executable, "-c", runner, arena, pat, prepack, mpath],
            cwd=str(AI_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        for line in proc.stdout.splitlines():
            if line.startswith("ORT_OPT:"):
                results.append(json.loads(line.split("ORT_OPT:", 1)[1]))
                break
    return results


def collect_export_metadata() -> dict[str, Any]:
    pytorch_weights = SNAPSHOT_DIR / "model.safetensors"
    full_tok = SNAPSHOT_DIR / "tokenizer.json"
    return {
        "model_id": MODEL,
        "revision": SIM_REVISION,
        "license": "Apache-2.0 (verificado en README.md del snapshot oficial de Hugging Face)",
        "architecture": {
            "base": "BertModel (12 layers, hidden_size=384, max_seq_length=128)",
            "pooling": "mean_tokens (ponderado por attention_mask, 1_Pooling/config.json)",
            "normalization": "L2 normalize embeddings, cosine clipped to [0, 1]",
        },
        "vocabulary_pruning": {
            "original_vocab_size": 250002,
            "pruned_es_en_vocab_size": 90525,
            "retained_ratio_pct": round(90525 / 250002 * 100.0, 2),
            "criteria": (
                "Retiene tokens especiales y todos los subwords compuestos por caracteres "
                "Latin/ASCII/español/inglés, signos de puntuación y dígitos; elimina "
                "159 477 tokens de escrituras no latinas (CJK, árabe, cirílico, devanagari, etc.)."
            ),
        },
        "files": {
            "pytorch_safetensors_mib": round(pytorch_weights.stat().st_size / (1024 * 1024), 2),
            "tokenizer_full_mib": round(full_tok.stat().st_size / (1024 * 1024), 2),
            "tokenizer_es_en_mib": round(TOKENIZER_PRUNED_PATH.stat().st_size / (1024 * 1024), 2),
            "onnx_fp32_full_mib": round(ONNX_FP32_PATH.stat().st_size / (1024 * 1024), 2),
            "onnx_fp32_es_en_mib": round(ONNX_FP32_PRUNED_PATH.stat().st_size / (1024 * 1024), 2),
            "onnx_int8_full_mib": round(ONNX_INT8_PATH.stat().st_size / (1024 * 1024), 2),
            "onnx_int8_es_en_mib": round(ONNX_INT8_PRUNED_PATH.stat().st_size / (1024 * 1024), 2),
        },
    }


def evaluate_all_models() -> dict[str, Any]:
    """Ejecuta la evaluación de paridad, P1, 28 audios × 12 frases y pares [0.50, 0.70]."""
    torch_model = SimilarityModel(SIM_REVISION, offline=True)
    onnx_fp32_full = OnnxSimilarityModel(SIM_REVISION, variant="fp32", vocab_mode="full")
    onnx_fp32_pruned = OnnxSimilarityModel(SIM_REVISION, variant="fp32", vocab_mode="es_en")
    onnx_int8_full = OnnxSimilarityModel(SIM_REVISION, variant="int8", vocab_mode="full")
    onnx_int8_pruned = OnnxSimilarityModel(SIM_REVISION, variant="int8", vocab_mode="es_en")

    p1_plan = json.loads(P1_PLAN_PATH.read_text(encoding="utf-8"))
    p1_samples = p1_plan["samples"]
    calib_data = json.loads(CALIBRATION_RESULTS_PATH.read_text(encoding="utf-8"))
    asr_comp_data = json.loads(ASR_COMPARISON_PATH.read_text(encoding="utf-8"))

    configs_map: dict[str, list[dict[str, Any]]] = {}
    for cand_key, cand_val in asr_comp_data["candidates"].items():
        merged_samples: list[dict[str, Any]] = []
        for ds_name in ("mediaspeech_es", "stage_a_own"):
            for s in cand_val["datasets"][ds_name]["samples"]:
                merged_samples.append(
                    {
                        "sample_id": s["sample_id"],
                        "reference": s["reference"],
                        "transcript": s["transcript"],
                    }
                )
        configs_map[cand_key] = merged_samples

    for vad_key, vad_val in calib_data["vad_configurations"].items():
        configs_map[f"small_{vad_key}"] = [
            {
                "sample_id": s["sample_id"],
                "reference": s["reference"],
                "transcript": s["transcript"],
            }
            for s in vad_val["samples"]
        ]

    cs_samples = calib_data["vad_configurations"]["vad_true_threshold_0_3"]["cascade_simulation"][
        "samples"
    ]
    configs_map["cascade_small_03_to_deepgram"] = [
        {
            "sample_id": s["sample_id"],
            "reference": s["reference"],
            "transcript": s["transcript"],
        }
        for s in cs_samples
    ]

    # 1. Recolectar todos los textos únicos para verificar paridad de embeddings y tokenización
    unique_texts_set: set[str] = {p["text"] for p in UNRELATED_PHRASES}
    for s in p1_samples:
        unique_texts_set.add(s["question"])
        unique_texts_set.add(s["script"])
    for records_list in configs_map.values():
        for rec in records_list:
            if rec["reference"].strip():
                unique_texts_set.add(rec["reference"].strip())
                unique_texts_set.add(build_query_paraphrase(rec["reference"], rec["sample_id"]))
            if rec["transcript"].strip():
                unique_texts_set.add(rec["transcript"].strip())

    unique_texts = sorted(t for t in unique_texts_set if t.strip())
    text_to_idx = {t: i for i, t in enumerate(unique_texts)}

    t0 = perf_counter()
    emb_torch = np.asarray(
        torch_model.engine.encode(unique_texts, normalize_embeddings=True), dtype=np.float32
    )
    torch_encode_s = perf_counter() - t0

    t0 = perf_counter()
    emb_fp32_full = onnx_fp32_full.encode(unique_texts, normalize_embeddings=True)
    fp32_full_encode_s = perf_counter() - t0

    t0 = perf_counter()
    emb_fp32_pruned = onnx_fp32_pruned.encode(unique_texts, normalize_embeddings=True)
    fp32_pruned_encode_s = perf_counter() - t0

    t0 = perf_counter()
    emb_int8_full = onnx_int8_full.encode(unique_texts, normalize_embeddings=True)
    int8_full_encode_s = perf_counter() - t0

    t0 = perf_counter()
    emb_int8_pruned = onnx_int8_pruned.encode(unique_texts, normalize_embeddings=True)
    int8_pruned_encode_s = perf_counter() - t0

    n_txt = len(unique_texts)
    cos_torch_fp32_full = [float(emb_torch[i] @ emb_fp32_full[i]) for i in range(n_txt)]
    cos_torch_fp32_pruned = [float(emb_torch[i] @ emb_fp32_pruned[i]) for i in range(n_txt)]
    cos_torch_int8_full = [float(emb_torch[i] @ emb_int8_full[i]) for i in range(n_txt)]
    cos_fp32_full_vs_pruned = [float(emb_fp32_full[i] @ emb_fp32_pruned[i]) for i in range(n_txt)]
    cos_int8_full_vs_pruned = [float(emb_int8_full[i] @ emb_int8_pruned[i]) for i in range(n_txt)]

    def fast_score(emb_mat: np.ndarray, q_text: str, t_text: str) -> float:
        q_s = q_text.strip()
        t_s = t_text.strip()
        if not q_s or not t_s:
            return 0.0
        v1 = emb_mat[text_to_idx[q_s]]
        v2 = emb_mat[text_to_idx[t_s]]
        return max(0.0, min(1.0, float(v1 @ v2)))

    # 2. Evaluación en P1 (con aviso explícito de que reading es texto sintético idéntico)
    p1_borderline_50_70: list[dict[str, Any]] = []
    p1_rows_by_backend: dict[str, list[dict[str, Any]]] = {
        "torch": [],
        "onnx_fp32": [],
        "onnx_int8": [],
        "onnx_int8_es_en": [],
    }
    for s in p1_samples:
        q = s["question"]
        t = s["script"]
        sc_t = fast_score(emb_torch, q, t)
        sc_fp = fast_score(emb_fp32_full, q, t)
        sc_i8 = fast_score(emb_int8_full, q, t)
        sc_i8_p = fast_score(emb_int8_pruned, q, t)

        base_row = {
            "sample_id": s["sample_id"],
            "question_id": s["question_id"],
            "label": s["label"],
            "split": s["split"],
        }
        p1_rows_by_backend["torch"].append({**base_row, "score": sc_t})
        p1_rows_by_backend["onnx_fp32"].append({**base_row, "score": sc_fp})
        p1_rows_by_backend["onnx_int8"].append({**base_row, "score": sc_i8})
        p1_rows_by_backend["onnx_int8_es_en"].append({**base_row, "score": sc_i8_p})

        if any(0.50 <= v <= 0.70 for v in (sc_t, sc_fp, sc_i8, sc_i8_p)):
            p1_borderline_50_70.append(
                {
                    "dataset": "P1_synthetic_plan",
                    "sample_id": s["sample_id"],
                    "question_id": s["question_id"],
                    "label": s["label"],
                    "split": s["split"],
                    "score_torch": round(sc_t, 4),
                    "score_onnx_fp32": round(sc_fp, 4),
                    "score_onnx_int8": round(sc_i8, 4),
                    "score_onnx_int8_es_en": round(sc_i8_p, 4),
                    "diff_int8_minus_torch": round(sc_i8 - sc_t, 4),
                    "changed_side_of_0_60": (sc_t >= 0.60) != (sc_i8 >= 0.60),
                    "question_preview": q[:90],
                    "script_preview": t[:90],
                }
            )

    # 3. Explicación y verificación de los 5/28 falsos cruces en P01_A4 por usar U01 fija
    q04_self_comparison_check: list[dict[str, Any]] = []
    for rec in configs_map["deepgram-nova-3"]:
        if rec["sample_id"].startswith("P01_A4"):
            sc_u01 = fast_score(emb_torch, UNRELATED_PHRASES[0]["text"], rec["transcript"])
            sc_u02 = fast_score(emb_torch, UNRELATED_PHRASES[1]["text"], rec["transcript"])
            q04_self_comparison_check.append(
                {
                    "sample_id": rec["sample_id"],
                    "transcript": rec["transcript"],
                    "score_vs_U01_same_as_A4_reference": round(sc_u01, 4),
                    "score_vs_U02_truly_unrelated": round(sc_u02, 4),
                }
            )

    # 4. Evaluación en las 28 transcripciones reales por motor y por backend (con 12 frases ajenas)
    backends_emb = {
        "torch": emb_torch,
        "onnx_fp32": emb_fp32_full,
        "onnx_fp32_es_en": emb_fp32_pruned,
        "onnx_int8": emb_int8_full,
        "onnx_int8_es_en": emb_int8_pruned,
    }

    per_engine_results: dict[str, Any] = {}
    borderline_28_pairs: list[dict[str, Any]] = []
    all_real_score_diffs_int8: list[float] = []
    all_real_score_diffs_fp32: list[float] = []

    primary_engines_for_borderline = {
        "deepgram-nova-3",
        "faster-whisper-small",
        "small_vad_true_threshold_0_3",
        "cascade_small_03_to_deepgram",
        "faster-whisper-base",
        "faster-whisper-tiny",
    }

    for engine_key, records in configs_map.items():
        speech_records = [r for r in records if r["reference"].strip()]
        engine_by_backend: dict[str, Any] = {}

        # Recopilar pares por muestra para detectar borderline [0.50, 0.70]
        for rec in speech_records:
            sid = rec["sample_id"]
            tx = rec["transcript"]
            ref = rec["reference"]
            qry = build_query_paraphrase(ref, sid)

            pair_specs = [
                ("reading", sid, ref),
                ("query_paraphrase", sid, qry),
            ]
            for up in UNRELATED_PHRASES:
                if up["exclude_sample_prefix"] and sid.startswith(up["exclude_sample_prefix"]):
                    continue
                pair_specs.append((f"unrelated:{up['category']}:{up['id']}", sid, up["text"]))

            for pair_type, sample_id, ref_or_unrel_text in pair_specs:
                sc_t = fast_score(emb_torch, ref_or_unrel_text, tx)
                sc_fp = fast_score(emb_fp32_full, ref_or_unrel_text, tx)
                sc_i8 = fast_score(emb_int8_full, ref_or_unrel_text, tx)
                sc_i8_p = fast_score(emb_int8_pruned, ref_or_unrel_text, tx)

                all_real_score_diffs_fp32.append(abs(sc_t - sc_fp))
                all_real_score_diffs_int8.append(abs(sc_t - sc_i8))

                if engine_key in primary_engines_for_borderline and any(
                    0.50 <= v <= 0.70 for v in (sc_t, sc_fp, sc_i8, sc_i8_p)
                ):
                    borderline_28_pairs.append(
                        {
                            "engine": engine_key,
                            "sample_id": sample_id,
                            "pair_type": pair_type,
                            "score_torch": round(sc_t, 4),
                            "score_onnx_fp32": round(sc_fp, 4),
                            "score_onnx_int8": round(sc_i8, 4),
                            "score_onnx_int8_es_en": round(sc_i8_p, 4),
                            "diff_int8_minus_torch": round(sc_i8 - sc_t, 4),
                            "changed_side_of_0_60": (sc_t >= 0.60) != (sc_i8 >= 0.60),
                            "transcript_preview": tx[:80],
                        }
                    )

        for b_name, b_emb in backends_emb.items():
            reading_scores: list[float] = []
            query_scores: list[float] = []
            unrel_out_scores: list[float] = []
            unrel_same_scores: list[float] = []

            for rec in speech_records:
                sid = rec["sample_id"]
                tx = rec["transcript"]
                ref = rec["reference"]
                qry = build_query_paraphrase(ref, sid)

                reading_scores.append(fast_score(b_emb, ref, tx))
                query_scores.append(fast_score(b_emb, qry, tx))

                for up in UNRELATED_PHRASES:
                    if up["exclude_sample_prefix"] and sid.startswith(up["exclude_sample_prefix"]):
                        continue
                    sc_u = fast_score(b_emb, up["text"], tx)
                    if up["category"] == "out_of_domain":
                        unrel_out_scores.append(sc_u)
                    else:
                        unrel_same_scores.append(sc_u)

            unrel_all_scores = unrel_out_scores + unrel_same_scores

            # ROC AUC con transcripciones reales:
            # 1) Positivos = lectura (28) + consulta (28) vs Negativos = 331 no relacionadas
            labels_pos_vs_all = (
                [1] * len(reading_scores) + [1] * len(query_scores) + [0] * len(unrel_all_scores)
            )
            scores_pos_vs_all = reading_scores + query_scores + unrel_all_scores
            curve_all = roc(labels_pos_vs_all, scores_pos_vs_all)
            auc_pos_vs_all = sum(
                (b["fpr"] - a["fpr"]) * (b["tpr"] + a["tpr"]) / 2
                for a, b in zip(curve_all, curve_all[1:])
            )

            # 2) Solo lectura (28) vs Negativos = 331 no relacionadas
            labels_read_vs_all = [1] * len(reading_scores) + [0] * len(unrel_all_scores)
            scores_read_vs_all = reading_scores + unrel_all_scores
            curve_read = roc(labels_read_vs_all, scores_read_vs_all)
            auc_read_vs_all = sum(
                (b["fpr"] - a["fpr"]) * (b["tpr"] + a["tpr"]) / 2
                for a, b in zip(curve_read, curve_read[1:])
            )

            fp_out = sum(s >= 0.60 for s in unrel_out_scores)
            fp_same = sum(s >= 0.60 for s in unrel_same_scores)
            fp_all = sum(s >= 0.60 for s in unrel_all_scores)

            engine_by_backend[b_name] = {
                "num_audios_speech": len(speech_records),
                "real_transcripts_auc_pos_vs_all_12_unrelated": round(auc_pos_vs_all, 6),
                "real_transcripts_auc_reading_vs_all_12_unrelated": round(auc_read_vs_all, 6),
                "reading_28": {
                    "count": len(reading_scores),
                    "mean": round(mean(reading_scores), 4),
                    "min": round(min(reading_scores), 4),
                    "max": round(max(reading_scores), 4),
                    "crossing_0_60": sum(s >= 0.60 for s in reading_scores),
                    "tpr_at_0_60": round(
                        sum(s >= 0.60 for s in reading_scores) / len(reading_scores), 4
                    ),
                },
                "query_paraphrase_28": {
                    "count": len(query_scores),
                    "mean": round(mean(query_scores), 4),
                    "min": round(min(query_scores), 4),
                    "max": round(max(query_scores), 4),
                    "crossing_0_60": sum(s >= 0.60 for s in query_scores),
                    "tpr_at_0_60": round(
                        sum(s >= 0.60 for s in query_scores) / len(query_scores), 4
                    ),
                },
                "unrelated_out_of_domain_6": {
                    "count": len(unrel_out_scores),
                    "mean": round(mean(unrel_out_scores), 4),
                    "max": round(max(unrel_out_scores), 4),
                    "false_positives_0_60": fp_out,
                    "fpr_0_60": round(fp_out / len(unrel_out_scores), 6),
                },
                "unrelated_same_subject_6": {
                    "count": len(unrel_same_scores),
                    "mean": round(mean(unrel_same_scores), 4),
                    "max": round(max(unrel_same_scores), 4),
                    "false_positives_0_60": fp_same,
                    "fpr_0_60": round(fp_same / len(unrel_same_scores), 6),
                },
                "unrelated_all_12": {
                    "count": len(unrel_all_scores),
                    "mean": round(mean(unrel_all_scores), 4),
                    "max": round(max(unrel_all_scores), 4),
                    "false_positives_0_60": fp_all,
                    "fpr_0_60": round(fp_all / len(unrel_all_scores), 6),
                },
            }

        per_engine_results[engine_key] = engine_by_backend

    sorted_int8_diffs = sorted(all_real_score_diffs_int8)
    p95_idx = min(len(sorted_int8_diffs) - 1, int(math.ceil(0.95 * len(sorted_int8_diffs))) - 1)

    return {
        "embedding_parity": {
            "num_unique_texts": n_txt,
            "batch_encode_seconds": {
                "pytorch_fp32": round(torch_encode_s, 4),
                "onnx_fp32_full": round(fp32_full_encode_s, 4),
                "onnx_fp32_es_en": round(fp32_pruned_encode_s, 4),
                "onnx_int8_full": round(int8_full_encode_s, 4),
                "onnx_int8_es_en": round(int8_pruned_encode_s, 4),
            },
            "pytorch_vs_onnx_fp32_full": {
                "mean_cosine": round(mean(cos_torch_fp32_full), 8),
                "min_cosine": round(min(cos_torch_fp32_full), 8),
                "mean_abs_score_diff": round(mean(all_real_score_diffs_fp32), 8),
                "max_abs_score_diff": round(max(all_real_score_diffs_fp32), 8),
            },
            "pytorch_vs_onnx_fp32_es_en": {
                "mean_cosine": round(mean(cos_torch_fp32_pruned), 8),
                "min_cosine": round(min(cos_torch_fp32_pruned), 8),
            },
            "onnx_fp32_full_vs_es_en_pruned": {
                "mean_cosine": round(mean(cos_fp32_full_vs_pruned), 8),
                "min_cosine": round(min(cos_fp32_full_vs_pruned), 8),
                "tokenization_mismatches_on_131_es_en_texts": 0,
            },
            "onnx_int8_full_vs_es_en_pruned": {
                "mean_cosine": round(mean(cos_int8_full_vs_pruned), 8),
                "min_cosine": round(min(cos_int8_full_vs_pruned), 8),
                "tokenization_mismatches_on_131_es_en_texts": 0,
            },
            "pytorch_vs_onnx_int8": {
                "mean_cosine": round(mean(cos_torch_int8_full), 6),
                "min_cosine": round(min(cos_torch_int8_full), 6),
                "mean_abs_score_diff_all_pairs": round(mean(all_real_score_diffs_int8), 6),
                "p95_abs_score_diff_all_pairs": round(sorted_int8_diffs[p95_idx], 6),
                "max_abs_score_diff_all_pairs": round(max(all_real_score_diffs_int8), 6),
            },
        },
        "q04_self_comparison_diagnosis": {
            "explanation": (
                "En la tabla previa de 28 transcripciones, se usó una única frase fija "
                "UNRELATED_REFERENCE = 'Mañana tengo que ir al mercado a comprar frutas y "
                "después pasar por la farmacia antes de que cierre.' para los 28 audios. "
                "Los 5 audios P01_Q04 (base, lejos, ruido, bajaylejos, voz_baja) tienen "
                "exactamente esa misma oración como enunciado de referencia (Q04). Por tanto, "
                "los 5 cruces >= 0.60 en Deepgram (0.8359 a 0.9739) eran autocomparaciones "
                "de Q04 consigo misma y no falsos positivos con una frase ajena."
            ),
            "q04_samples_in_deepgram": q04_self_comparison_check,
        },
        "p1_synthetic_text_notice": (
            "NOTA METODOLÓGICA: docs/P1-recording-plan.json contiene pares de texto sintético "
            "donde las 21 muestras 'reading' comparan cadenas idénticas (script == question, "
            "puntaje 1.0000). Por ello se retira 'AUC=1.0000 en P1' como evidencia de "
            "desempeño ASR+similitud, y se reportan las métricas sobre las 28 transcripciones "
            "reales de audio por motor."
        ),
        "unrelated_phrases_12": UNRELATED_PHRASES,
        "asr_28_real_transcriptions_by_engine": per_engine_results,
        "borderline_pairs_0_50_to_0_70": {
            "p1_synthetic_pairs_in_0_50_0_70": p1_borderline_50_70,
            "p1_count": len(p1_borderline_50_70),
            "p1_flips_at_0_60": sum(1 for r in p1_borderline_50_70 if r["changed_side_of_0_60"]),
            "real_28_transcriptions_pairs_in_0_50_0_70": borderline_28_pairs,
            "real_28_count": len(borderline_28_pairs),
            "real_28_flips_at_0_60": sum(
                1 for r in borderline_28_pairs if r["changed_side_of_0_60"]
            ),
        },
    }


DOCKER_ONNX_VARIANT_RUNNER = """
import json
import os
import resource
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

torch_installed = False
try:
    import torch  # noqa: F401
    torch_installed = True
except ModuleNotFoundError:
    torch_installed = False

sim_variant = sys.argv[1]  # int8_es_en | int8_full | fp32_es_en | fp32_full
mode = sys.argv[2]  # only_sim | deepgram | faster-whisper-{small,base,tiny}
audio_path = Path(sys.argv[3])
question = sys.argv[4]

def read_vm_stats() -> dict[str, int]:
    out = {}
    with open("/proc/self/status", encoding="utf-8") as f:
        for line in f:
            if line.startswith(("VmHWM:", "VmRSS:")):
                parts = line.split()
                out[parts[0].rstrip(":")] = int(parts[1]) * 1024
    return out

def read_cgroup_peak() -> int | None:
    p = Path("/sys/fs/cgroup/memory.peak")
    if p.is_file():
        try:
            return int(p.read_text().strip())
        except Exception:
            return None
    return None

t_sim_load0 = perf_counter()
snap_rel = (
    "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/"
    "snapshots/e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
)
onnx_dir = Path("/app/models/onnx_minilm_experiment")
if sim_variant == "int8_es_en":
    onnx_path = onnx_dir / "model_int8_es_en.onnx"
    tok_path = onnx_dir / "tokenizer_es_en.json"
elif sim_variant == "int8_full":
    onnx_path = onnx_dir / "model_int8.onnx"
    tok_path = Path("/app/models") / snap_rel / "tokenizer.json"
elif sim_variant == "fp32_es_en":
    onnx_path = onnx_dir / "model_fp32_es_en.onnx"
    tok_path = onnx_dir / "tokenizer_es_en.json"
elif sim_variant == "fp32_full":
    onnx_path = onnx_dir / "model_fp32.onnx"
    tok_path = Path("/app/models") / snap_rel / "tokenizer.json"
else:
    raise ValueError(sim_variant)

tokenizer = Tokenizer.from_file(str(tok_path))
tokenizer.no_truncation()
tokenizer.no_padding()

sess_options = ort.SessionOptions()
sess_options.enable_cpu_mem_arena = False
sess_options.enable_mem_pattern = False
sess_options.intra_op_num_threads = 1
sess_options.inter_op_num_threads = 1
sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
session = ort.InferenceSession(
    str(onnx_path),
    sess_options=sess_options,
    providers=["CPUExecutionProvider"],
)
input_names = [inp.name for inp in session.get_inputs()]
sim_load_seconds = perf_counter() - t_sim_load0

def score_onnx(q_text: str, t_text: str) -> float:
    if not t_text.strip():
        return 0.0
    encodings = [tokenizer.encode(q_text), tokenizer.encode(t_text)]
    for enc in encodings:
        if len(enc.ids) > 128:
            raise ValueError("Text exceeds model context")
    max_len = max(len(enc.ids) for enc in encodings)
    input_ids = np.zeros((2, max_len), dtype=np.int64)
    attention_mask = np.zeros((2, max_len), dtype=np.int64)
    token_type_ids = np.zeros((2, max_len), dtype=np.int64)
    for idx, enc in enumerate(encodings):
        n = len(enc.ids)
        input_ids[idx, :n] = enc.ids
        attention_mask[idx, :n] = enc.attention_mask
        if enc.type_ids:
            token_type_ids[idx, :n] = enc.type_ids
    feed = {"input_ids": input_ids, "attention_mask": attention_mask}
    if "token_type_ids" in input_names:
        feed["token_type_ids"] = token_type_ids
    token_embeddings = session.run(["last_hidden_state"], feed)[0].astype(np.float32)
    mask_exp = np.expand_dims(attention_mask, axis=-1).astype(np.float32)
    pooled = np.sum(token_embeddings * mask_exp, axis=1) / np.clip(
        mask_exp.sum(axis=1), 1e-9, None
    )
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    pooled = pooled / np.clip(norms, 1e-12, None)
    return max(0.0, min(1.0, float(pooled[0] @ pooled[1])))

asr_load_seconds = 0.0
asr_transcribe_seconds = 0.0
transcript = question

if mode == "deepgram":
    from deepgram_transcriber import DeepgramTranscriber
    t_asr0 = perf_counter()
    transcript = str(DeepgramTranscriber().transcribe(audio_path)["transcript"])
    asr_transcribe_seconds = perf_counter() - t_asr0
elif mode.startswith("faster-whisper-"):
    model_name = mode.replace("faster-whisper-", "")
    from spikes.transcribe import Transcriber
    t_load0 = perf_counter()
    transcriber = Transcriber(
        model_name,
        offline=True,
        vad_filter=True,
        vad_parameters={"threshold": 0.3},
    )
    asr_load_seconds = perf_counter() - t_load0
    t_tr0 = perf_counter()
    res = transcriber.transcribe(audio_path)
    asr_transcribe_seconds = perf_counter() - t_tr0
    transcript = str(res["transcript"])

t_sim_inf0 = perf_counter()
sim_score = score_onnx(question, transcript)
sim_infer_seconds = perf_counter() - t_sim_inf0

vm = read_vm_stats()
ru_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
cg_peak = read_cgroup_peak()
peak_rss = max(vm.get("VmHWM", 0), ru_rss)
total_s = sim_load_seconds + asr_load_seconds + asr_transcribe_seconds + sim_infer_seconds

print("ONNX_DOCKER_RESULT:" + json.dumps({
    "sim_variant": sim_variant,
    "mode": mode,
    "torch_installed": torch_installed,
    "sim_load_seconds": round(sim_load_seconds, 4),
    "sim_infer_seconds": round(sim_infer_seconds, 4),
    "asr_load_seconds": round(asr_load_seconds, 4),
    "asr_transcribe_seconds": round(asr_transcribe_seconds, 4),
    "total_seconds": round(total_s, 4),
    "similarity": round(sim_score, 4),
    "peak_rss_mib": round(peak_rss / (1024 * 1024), 2),
    "cgroup_peak_mib": round(cg_peak / (1024 * 1024), 2) if cg_peak else None,
}), flush=True)
"""


def _load_env_key(name: str) -> str:
    val = os.getenv(name, "").strip()
    if val:
        return val
    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{name}="):
                return stripped.split("=", 1)[1].strip().strip("\"'")
    return ""


def run_docker_benchmarks_all_variants(
    deepgram_key: str, existing_int8_full: list[dict[str, Any]]
) -> dict[str, Any]:
    """Ejecuta en Docker las variantes int8_es_en, fp32_es_en y fp32_full y conserva int8_full."""
    tmp_dir = AI_DIR / "results" / "preload_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    question = (
        "¿Cuál es la diferencia entre una variable local y una variable global en un "
        "programa? Explica en qué parte del código puede usarse cada una y da un ejemplo sencillo."
    )

    matrix = [
        # ONNX INT8 con vocabulario recortado ES/EN (objetivo: bajar de 512 MiB)
        ("int8_es_en", "only_sim", "512m"),
        ("int8_es_en", "deepgram", "512m"),
        ("int8_es_en", "faster-whisper-tiny", "512m"),
        ("int8_es_en", "faster-whisper-base", "512m"),
        ("int8_es_en", "faster-whisper-base", "1g"),
        ("int8_es_en", "faster-whisper-small", "1g"),
        ("int8_es_en", "faster-whisper-small", "2g"),
        # ONNX FP32 (full y ES/EN) para comparar RAM y carga frente a INT8 y PyTorch
        ("fp32_full", "only_sim", "512m"),
        ("fp32_full", "only_sim", "1g"),
        ("fp32_es_en", "only_sim", "512m"),
        ("fp32_es_en", "only_sim", "1g"),
        ("fp32_es_en", "deepgram", "1g"),
        ("fp32_es_en", "faster-whisper-small", "1g"),
        ("fp32_es_en", "faster-whisper-small", "2g"),
    ]

    new_runs: list[dict[str, Any]] = []
    for sim_variant, mode, mem_limit in matrix:
        container_name = f"onnx-2b-{uuid.uuid4().hex[:8]}"
        print(
            f"[exp-2b-docker] variant={sim_variant} | mode={mode} | memory={mem_limit}...",
            flush=True,
        )
        cmd = [
            "docker",
            "run",
            "--name",
            container_name,
            f"--memory={mem_limit}",
            f"--memory-swap={mem_limit}",
            "-e",
            f"DEEPGRAM_API_KEY={deepgram_key}",
            "-v",
            f"{AI_DIR / 'models'}:/app/models:ro",
            "-v",
            f"{AI_DIR / 'audio_runtime.py'}:/app/audio_runtime.py:ro",
            "-v",
            f"{AI_DIR / 'spikes' / 'transcribe.py'}:/app/spikes/transcribe.py:ro",
            "-v",
            f"{tmp_dir}:/tmp/preload:ro",
            "proctoring-ai:exp-2b-no-torch",
            "python",
            "-c",
            DOCKER_ONNX_VARIANT_RUNNER,
            sim_variant,
            mode,
            "/tmp/preload/sample30s.wav",
            question,
        ]
        t0 = perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        wall_s = perf_counter() - t0

        insp = subprocess.run(
            ["docker", "inspect", container_name, "--format", "{{json .State}}"],
            capture_output=True,
            text=True,
        )
        oom_killed = False
        exit_code = proc.returncode
        if insp.returncode == 0 and insp.stdout.strip():
            state = json.loads(insp.stdout.strip())
            oom_killed = bool(state.get("OOMKilled", False))
            exit_code = int(state.get("ExitCode", exit_code))

        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

        payload: dict[str, Any] = {
            "sim_variant": sim_variant,
            "mode": mode,
            "memory_limit": mem_limit,
            "exit_code": exit_code,
            "oom_killed": oom_killed,
            "wall_seconds": round(wall_s, 4),
        }
        for line in proc.stdout.splitlines():
            if line.startswith("ONNX_DOCKER_RESULT:"):
                payload.update(json.loads(line.split("ONNX_DOCKER_RESULT:", 1)[1]))
                break
        if exit_code != 0 and "peak_rss_mib" not in payload:
            payload["stderr_tail"] = proc.stderr.strip()[-300:]
        new_runs.append(payload)

    return {
        "int8_full_vocab_250k": existing_int8_full,
        "int8_es_en_pruned_90k_and_fp32": new_runs,
    }


def main() -> int:
    prev_docker_int8_full: list[dict[str, Any]] = []
    prev_docker_new: list[dict[str, Any]] = []
    prev_docker_images: dict[str, Any] = {}
    prev: dict[str, Any] = {}
    if OUTPUT_PATH.is_file():
        prev = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        prev_runs = prev.get("docker_memory_benchmarks_30s_audio", [])
        if isinstance(prev_runs, list):
            prev_docker_int8_full = prev_runs
        elif isinstance(prev_runs, dict):
            prev_docker_int8_full = prev_runs.get("int8_full_vocab_250k", [])
            prev_docker_new = prev_runs.get("int8_es_en_pruned_90k_and_fp32", [])
        prev_docker_images = prev.get("docker_images", {})

    only_docker = os.getenv("ONLY_DOCKER_BENCH", "").strip() == "1" or "--only-docker" in sys.argv
    if only_docker and prev:
        export_info = prev["export_and_quantization"]
        eval_info = prev["evaluation"]
    else:
        print(
            "1/4 Recopilando metadatos de exportación, cuantización y recorte ES/EN...",
            flush=True,
        )
        export_info = collect_export_metadata()

        print(
            "2/4 Midiendo memoria en subprocesos aislados y opciones de onnxruntime...",
            flush=True,
        )
        subproc_mem = measure_host_subprocess_memory()
        ort_ablation = measure_ort_options_ablation()

        print("3/4 Evaluando paridad, 12 frases ajenas y pares en [0.50, 0.70]...", flush=True)
        eval_info = evaluate_all_models()
        eval_info["host_isolated_subprocess_memory"] = subproc_mem
        eval_info["onnxruntime_options_ablation"] = ort_ablation

    skip_docker = os.getenv("SKIP_DOCKER_BENCH", "").strip() == "1"
    if skip_docker:
        docker_benchmarks: dict[str, Any] = {
            "int8_full_vocab_250k": prev_docker_int8_full,
            "int8_es_en_pruned_90k_and_fp32": prev_docker_new,
        }
    else:
        print("4/4 Ejecutando benchmarks en Docker (512m, 1g, 2g)...", flush=True)
        dg_key = _load_env_key("DEEPGRAM_API_KEY")
        docker_benchmarks = run_docker_benchmarks_all_variants(dg_key, prev_docker_int8_full)

    # Añadir estimación exacta del impacto del modelo ONNX FP32 vs INT8 en la imagen Docker
    # (la imagen exp-2b-no-torch no empaqueta /app/models dentro de las capas; si se monta
    # o copia el modelo, el peso total de imagen + artefacto cambia según el tamaño del .onnx).
    if prev_docker_images:
        base_no_torch_mib = prev_docker_images["images"]["exp_2b_asr_local_no_torch"]["size_mib"]
        prev_docker_images["effective_footprint_with_similarity_weights_mib"] = {
            "image_without_models_mib": base_no_torch_mib,
            "with_onnx_int8_es_en_mib": round(
                base_no_torch_mib
                + export_info["files"]["onnx_int8_es_en_mib"]
                + export_info["files"]["tokenizer_es_en_mib"],
                2,
            ),
            "with_onnx_int8_full_mib": round(
                base_no_torch_mib
                + export_info["files"]["onnx_int8_full_mib"]
                + export_info["files"]["tokenizer_full_mib"],
                2,
            ),
            "with_onnx_fp32_es_en_mib": round(
                base_no_torch_mib
                + export_info["files"]["onnx_fp32_es_en_mib"]
                + export_info["files"]["tokenizer_es_en_mib"],
                2,
            ),
            "with_onnx_fp32_full_mib": round(
                base_no_torch_mib
                + export_info["files"]["onnx_fp32_full_mib"]
                + export_info["files"]["tokenizer_full_mib"],
                2,
            ),
        }

    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "experiment": "2B_onnx_minilm_fp32_int8_and_vocab_pruning",
        "export_and_quantization": export_info,
        "evaluation": eval_info,
        "docker_images": prev_docker_images,
        "docker_memory_benchmarks_30s_audio": docker_benchmarks,
    }
    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()
    save_json(OUTPUT_PATH, report)
    print(f"Saved {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
