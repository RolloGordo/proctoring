"""Generación y exportación reproducible de paraphrase-multilingual-MiniLM-L12-v2 a ONNX.

Cumple con:
- Revisión fijada de Hugging Face: e8f8c211226b894fcb81acc59f3b34ba3efd5f42
- Licencia: Apache-2.0
- Checksums SHA-256 de verificación
- Recorte de vocabulario a español e inglés (90.525 tokens, 36,21 % del vocabulario original)
  eliminando escrituras no latinas sin pérdida para español e inglés.
- Exportación FP32 y cuantización dinámica INT8 (onnxruntime).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

AI_DIR = Path(__file__).resolve().parent.parent
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SIM_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
LICENSE = "Apache-2.0"

# Caracteres permitidos para vocabulario español/inglés
ALLOWED_CHARS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "áéíóúüñÁÉÍÓÚÜÑ"
    "\u2581"
    ".,;:?!¿¡()[]{}<>\"''/-_+*=&#%$@~^`|\\°ºª€$"
)
SPECIAL_TOKENS = {"<s>", "<pad>", "</s>", "<unk>", "<mask transmission>", "<mask"}


def _ensure_onnx_package_on_path() -> None:
    try:
        import onnx  # type: ignore[import-not-found] # noqa: F401
    except ModuleNotFoundError:
        uv_cache = Path.home() / ".cache" / "uv" / "archive-v0"
        if uv_cache.is_dir():
            for candidate in uv_cache.iterdir():
                if (candidate / "onnx" / "__init__.py").is_file() or (
                    candidate / "ml_dtypes" / "__init__.py"
                ).is_file():
                    sys.path.insert(0, str(candidate))


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def prune_tokenizer_vocab(
    src_tokenizer_json: Path,
    dest_tokenizer_json: Path,
) -> tuple[list[int], dict[int, int]]:
    """Genera tokenizer_es_en.json filtrando tokens no latinos."""
    tok_data = json.loads(src_tokenizer_json.read_text(encoding="utf-8"))
    vocab = tok_data["model"]["vocab"]

    def is_es_en(piece: str) -> bool:
        if piece in SPECIAL_TOKENS or piece.startswith("<") and piece.endswith(">"):
            return True
        return all(c in ALLOWED_CHARS for c in piece)

    kept_indices = [i for i, (piece, _score) in enumerate(vocab) if is_es_en(piece)]
    old_to_new = {old_idx: new_idx for new_idx, old_idx in enumerate(kept_indices)}

    tok_data["model"]["vocab"] = [vocab[i] for i in kept_indices]
    for at in tok_data.get("added_tokens", []):
        if at["id"] in old_to_new:
            at["id"] = old_to_new[at["id"]]

    dest_tokenizer_json.parent.mkdir(parents=True, exist_ok=True)
    dest_tokenizer_json.write_text(json.dumps(tok_data), encoding="utf-8")
    return kept_indices, old_to_new


def export_onnx_models(
    model_dir_or_id: str | Path,
    out_dir: Path,
    *,
    export_fp32: bool = True,
    export_int8: bool = True,
) -> dict[str, Any]:
    """Exporta y cuantiza el modelo a ONNX con recorte de vocabulario."""
    _ensure_onnx_package_on_path()
    import torch
    from onnxruntime.quantization import QuantType, quantize_dynamic  # type: ignore[import-untyped]
    from transformers import AutoModel

    out_dir.mkdir(parents=True, exist_ok=True)
    src_path = Path(model_dir_or_id)
    if src_path.is_dir():
        tok_source = src_path / "tokenizer.json"
        hf_model = AutoModel.from_pretrained(str(src_path), local_files_only=True)
    else:
        from spikes.network import configure_model_downloads

        configure_model_downloads()
        from huggingface_hub import snapshot_download

        snap = snapshot_download(repo_id=str(model_dir_or_id), revision=SIM_REVISION)
        tok_source = Path(snap) / "tokenizer.json"
        hf_model = AutoModel.from_pretrained(snap, local_files_only=True)

    dest_tok = out_dir / "tokenizer_es_en.json"
    t_tok0 = perf_counter()
    kept_indices, _ = prune_tokenizer_vocab(tok_source, dest_tok)
    tok_time = perf_counter() - t_tok0

    hf_model.eval()
    with torch.no_grad():
        old_emb = hf_model.embeddings.word_embeddings.weight.data
        new_emb = old_emb[torch.tensor(kept_indices, dtype=torch.long)].clone()
        new_layer = torch.nn.Embedding(len(kept_indices), old_emb.shape[1], padding_idx=1)
        new_layer.weight.data.copy_(new_emb)
        hf_model.embeddings.word_embeddings = new_layer
        hf_model.config.vocab_size = len(kept_indices)

    class _Wrapper(torch.nn.Module):
        def __init__(self, mod: torch.nn.Module) -> None:
            super().__init__()
            self.mod = mod

        def forward(
            self,
            input_ids: torch.Tensor,
            attention_mask: torch.Tensor,
            token_type_ids: torch.Tensor,
        ) -> torch.Tensor:
            out = self.mod(
                input_ids=input_ids,
                attention_mask=attention_mask,
                token_type_ids=token_type_ids,
            )
            return out.last_hidden_state

    wrapper = _Wrapper(hf_model)
    dummy_ids = torch.ones((2, 16), dtype=torch.long)
    dummy_mask = torch.ones((2, 16), dtype=torch.long)
    dummy_types = torch.zeros((2, 16), dtype=torch.long)

    fp32_path = out_dir / "model_fp32_es_en.onnx"
    int8_path = out_dir / "model_int8_es_en.onnx"

    results: dict[str, Any] = {
        "model_id": MODEL_ID,
        "revision": SIM_REVISION,
        "license": LICENSE,
        "vocab_original": 250002,
        "vocab_pruned": len(kept_indices),
        "tokenizer_path": str(dest_tok),
        "tokenizer_sha256": compute_sha256(dest_tok),
        "tokenizer_size_bytes": dest_tok.stat().st_size,
        "tokenizer_prune_seconds": round(tok_time, 4),
    }

    if export_fp32:
        t_fp0 = perf_counter()
        torch.onnx.export(
            wrapper,
            (dummy_ids, dummy_mask, dummy_types),
            str(fp32_path),
            input_names=["input_ids", "attention_mask", "token_type_ids"],
            output_names=["last_hidden_state"],
            dynamic_axes={
                "input_ids": {0: "batch_size", 1: "sequence_length"},
                "attention_mask": {0: "batch_size", 1: "sequence_length"},
                "token_type_ids": {0: "batch_size", 1: "sequence_length"},
                "last_hidden_state": {0: "batch_size", 1: "sequence_length"},
            },
            opset_version=14,
            do_constant_folding=True,
            dynamo=False,
        )
        fp_time = perf_counter() - t_fp0
        results["model_fp32_path"] = str(fp32_path)
        results["model_fp32_sha256"] = compute_sha256(fp32_path)
        results["model_fp32_size_bytes"] = fp32_path.stat().st_size
        results["model_fp32_export_seconds"] = round(fp_time, 4)

    if export_int8:
        if not fp32_path.is_file():
            raise FileNotFoundError(f"FP32 model required for quantization: {fp32_path}")
        t_int0 = perf_counter()
        quantize_dynamic(
            model_input=str(fp32_path),
            model_output=str(int8_path),
            weight_type=QuantType.QInt8,
        )
        int_time = perf_counter() - t_int0
        results["model_int8_path"] = str(int8_path)
        results["model_int8_sha256"] = compute_sha256(int8_path)
        results["model_int8_size_bytes"] = int8_path.stat().st_size
        results["model_int8_quantize_seconds"] = round(int_time, 4)

    manifest_path = out_dir / "onnx_manifest.json"
    manifest_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generación reproducible de ONNX MiniLM para proctoring"
    )
    parser.add_argument(
        "--source",
        default=str(
            AI_DIR
            / "models"
            / "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"
            / "snapshots"
            / SIM_REVISION
        ),
        help="Ruta local al snapshot o 'hf' para descargar de Hugging Face.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(AI_DIR / "models" / "onnx_minilm_experiment"),
        help="Directorio de destino para los archivos ONNX y tokenizer.",
    )
    parser.add_argument(
        "--int8-only",
        action="store_true",
        help="Conservar solo INT8 (eliminar FP32 intermedio para ahorrar disco).",
    )
    args = parser.parse_args()

    source = MODEL_ID if args.source == "hf" else args.source
    out_dir = Path(args.out_dir)

    print(f"Exportando ONNX desde {source} hacia {out_dir}...")
    res = export_onnx_models(source, out_dir, export_fp32=True, export_int8=True)
    if args.int8_only and (out_dir / "model_fp32_es_en.onnx").is_file():
        (out_dir / "model_fp32_es_en.onnx").unlink()
        print("Eliminado FP32 intermedio (--int8-only)")

    print(
        f"Exportación finalizada con éxito. Manifiesto guardado en {out_dir / 'onnx_manifest.json'}"
    )
    print(f"  INT8 SHA-256: {res.get('model_int8_sha256')}")
    print(f"  Tokenizer SHA-256: {res.get('tokenizer_sha256')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
