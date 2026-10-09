"""SPEC-005: comparación facial en CPU, sin persistir fotos del estudiante.

El resultado es una medida, no un veredicto; la API aplica su umbral.
InsightFace y el runtime ONNX se cargan sólo al usar esta funcionalidad.
"""
from __future__ import annotations

import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

MAX_IMAGE_BYTES = 2 * 1024 * 1024


class FaceInconclusive(Exception):
    """Imagen ilegible, sin rostro o con múltiples rostros."""


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a or len(a) > 1024:
        raise FaceInconclusive('Embeddings incompatibles')
    if not all(math.isfinite(v) for v in [*a, *b]):
        raise FaceInconclusive('Embedding no finito')
    norm_a = math.sqrt(sum(v * v for v in a))
    norm_b = math.sqrt(sum(v * v for v in b))
    if norm_a <= 0 or norm_b <= 0:
        raise FaceInconclusive('Embedding nulo')
    # El contrato de la API exige [0,1]. Mantener calibración explícita de este
    # valor; NO es una probabilidad, sólo un coseno recortado a [0,1].
    return max(0.0, min(1.0, sum(x * y for x, y in zip(a, b)) / (norm_a * norm_b)))


@lru_cache(maxsize=1)
def _engine() -> Any:
    try:
        from insightface.app import FaceAnalysis  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError('Instalar dependencia opcional: uv pip install -r requirements-face.txt') from exc
    # Models privados/no incluidos: revisar la licencia antes de descargarlos.
    model = FaceAnalysis(
        name=os.getenv('FACE_MODEL_NAME', 'buffalo_sc'),
        root=str(Path(os.getenv('FACE_MODEL_ROOT', 'models')).resolve()),
        providers=['CPUExecutionProvider'],
    )
    model.prepare(ctx_id=-1, det_size=(320, 320))
    return model


def embedding_from_bytes(content: bytes) -> list[float]:
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise FaceInconclusive('Imagen vacía o demasiado grande')
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError('Dependencias de reconocimiento facial ausentes') from exc
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise FaceInconclusive('Imagen ilegible')
    faces = _engine().get(image)
    if len(faces) != 1:
        raise FaceInconclusive(f'Se detectaron {len(faces)} rostros; se esperaba 1')
    embedding = faces[0].embedding
    if embedding is None:
        raise FaceInconclusive('No se pudo extraer embedding')
    return [float(value) for value in embedding]


def get_storage_image(bucket: str, path: str) -> bytes:
    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    secret = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not url or not secret:
        raise RuntimeError('Faltan SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY')
    if not bucket or not path or path.startswith('/') or '..' in path.split('/'):
        raise ValueError('Ruta de Storage inválida')
    # No interpolar URLs externas: bucket/path provienen de la API confiable.
    endpoint = f'{url}/storage/v1/object/authenticated/{quote(bucket, safe="")}/{quote(path, safe="/")}'
    headers = {'apikey': secret, 'Authorization': f'Bearer {secret}'}
    with httpx.stream('GET', endpoint, headers=headers, timeout=15, follow_redirects=False) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > MAX_IMAGE_BYTES:
                raise FaceInconclusive('Imagen supera 2MB')
        return bytes(data)


def compare_job(job: dict[str, Any]) -> tuple[float, list[float] | None]:
    """Devuelve (similitud, embedding_nuevo_referencia_si_aplica).

    La captura SIEMPRE se analiza y exige exactamente un rostro.
    """
    capture = get_storage_image(job['capture_bucket'], job['capture_path'])
    capture_vector = embedding_from_bytes(capture)
    reference = job.get('reference_embedding')
    new_reference: list[float] | None = None
    if reference is None:
        original = get_storage_image(job['reference_bucket'], job['reference_path'])
        reference = embedding_from_bytes(original)
        new_reference = reference
    return cosine_similarity([float(x) for x in reference], capture_vector), new_reference
