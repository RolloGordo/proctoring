"""Adaptador de verificación facial con OpenCV: YuNet detecta, SFace compara.

Mismo contrato que el motor InsightFace de `face_pipeline.py`: recibe los
bytes de una imagen y devuelve un embedding, o lanza `FaceInconclusive` si no
hay exactamente un rostro. Las fotos no se guardan en ningún sitio.

Usa `cv2.FaceDetectorYN` y `cv2.FaceRecognizerSF`, que vienen en
`opencv-python-headless`, una dependencia que el worker ya tenía: no añade
paquetes ni compiladores a la imagen.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from face_pipeline import FaceInconclusive

#: Carpeta con los `.onnx` versionados y su procedencia. Se llama `modelos/`
#: y no `models/` porque `services/ai/.gitignore` ignora cualquier `models/`.
MODELOS = Path(__file__).resolve().parent / "modelos"
DETECTOR = "face_detection_yunet_2023mar.onnx"
RECONOCEDOR = "face_recognition_sface_2021dec_int8.onnx"

#: Confianza mínima de YuNet para contar una cara. 0,8 es el valor de las
#: demos de OpenCV Zoo; más bajo cuenta como cara sombras y reflejos.
CONFIANZA_MINIMA = 0.8


def verificar_modelos(carpeta: Path = MODELOS) -> None:
    """Comprueba que los modelos estén y sean los registrados en PROCEDENCIA.json.

    Lanza `RuntimeError` (fallo de infraestructura, el trabajo se reintenta),
    nunca `FaceInconclusive`: un modelo truncado o un marcador de Git LFS sin
    resolver no es «no se ve la cara», y no debe parecerlo.
    """
    procedencia = json.loads((carpeta / "PROCEDENCIA.json").read_text(encoding="utf-8"))
    for modelo in procedencia["modelos"]:
        ruta = carpeta / modelo["archivo"]
        if not ruta.is_file():
            raise RuntimeError(f"Falta el modelo {ruta.name} en {carpeta}")
        contenido = ruta.read_bytes()
        if len(contenido) != modelo["bytes"]:
            raise RuntimeError(f"Modelo {ruta.name} con tamaño inesperado ({len(contenido)} B)")
        if hashlib.sha256(contenido).hexdigest() != modelo["sha256"]:
            raise RuntimeError(f"Modelo {ruta.name} con sha256 distinto al registrado")


class VerificadorOpenCV:
    """Motor facial liviano y autónomo. Cárgalo una vez y reutilízalo."""

    version = "opencv/yunet-2023mar+sface-2021dec-int8-cpu"

    def __init__(self, carpeta: Path = MODELOS) -> None:
        try:
            import cv2  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("Dependencias de reconocimiento facial ausentes (cv2)") from exc
        verificar_modelos(carpeta)
        self._cv2: Any = cv2
        # El tamaño de entrada real se fija por imagen en `embedding`.
        self._detector: Any = cv2.FaceDetectorYN.create(
            str(carpeta / DETECTOR), "", (320, 320), CONFIANZA_MINIMA
        )
        self._reconocedor: Any = cv2.FaceRecognizerSF.create(str(carpeta / RECONOCEDOR), "")

    def contar_rostros(self, imagen: Any) -> Any:
        """Devuelve las filas de YuNet (una por cara) o una lista vacía."""
        alto, ancho = imagen.shape[:2]
        self._detector.setInputSize((ancho, alto))
        _, caras = self._detector.detect(imagen)
        return [] if caras is None else caras

    def embedding(self, contenido: bytes) -> list[float]:
        try:
            import numpy as np  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("Dependencias de reconocimiento facial ausentes (numpy)") from exc
        imagen = self._cv2.imdecode(
            np.frombuffer(contenido, dtype=np.uint8), self._cv2.IMREAD_COLOR
        )
        if imagen is None:
            raise FaceInconclusive("Imagen ilegible")
        caras = self.contar_rostros(imagen)
        if len(caras) != 1:
            raise FaceInconclusive(f"Se detectaron {len(caras)} rostros; se esperaba 1")
        alineada = self._reconocedor.alignCrop(imagen, caras[0])
        vector = self._reconocedor.feature(alineada)
        return [float(valor) for valor in vector.flatten()]
