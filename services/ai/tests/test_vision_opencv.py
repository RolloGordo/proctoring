"""API de imagen propia (vision/): integridad de modelos, selección de motor y
cambio de motor sin dejar a nadie sin verificar.

Las pruebas que necesitan OpenCV se saltan si `cv2` no está instalado (el CI
instala el entorno sin el extra `face`); las demás corren siempre.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

import face_pipeline
import worker_stub
from face_pipeline import FaceInconclusive, compare_job
from vision import MODELOS, verificar_modelos


@pytest.fixture(autouse=True)
def _sin_cache() -> None:
    face_pipeline._motor_opencv.cache_clear()


def test_modelos_versionados_coinciden_con_su_procedencia() -> None:
    verificar_modelos()  # no lanza: archivos, tamaños y sha256 correctos


def test_modelos_son_livianos() -> None:
    procedencia = json.loads((MODELOS / "PROCEDENCIA.json").read_text(encoding="utf-8"))
    total = sum(modelo["bytes"] for modelo in procedencia["modelos"])
    assert total < 15 * 1024 * 1024
    assert {modelo["licencia"] for modelo in procedencia["modelos"]} == {"MIT", "Apache-2.0"}


def test_modelo_truncado_es_fallo_de_infraestructura(tmp_path: Path) -> None:
    for archivo in MODELOS.iterdir():
        shutil.copy(archivo, tmp_path / archivo.name)
    (tmp_path / "face_detection_yunet_2023mar.onnx").write_bytes(b"version https://git-lfs")
    with pytest.raises(RuntimeError, match="tamaño inesperado"):
        verificar_modelos(tmp_path)


def test_modelo_ausente_es_fallo_de_infraestructura(tmp_path: Path) -> None:
    shutil.copy(MODELOS / "PROCEDENCIA.json", tmp_path / "PROCEDENCIA.json")
    with pytest.raises(RuntimeError, match="Falta el modelo"):
        verificar_modelos(tmp_path)


def test_motor_por_defecto_no_cambia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FACE_ENGINE", raising=False)
    assert face_pipeline.motor_seleccionado() == "insightface"
    assert face_pipeline.model_version().startswith("insightface/")


def test_motor_opencv_se_registra_en_el_resultado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACE_ENGINE", "opencv")
    assert face_pipeline.model_version().startswith("opencv/yunet")


def test_motor_desconocido_es_error_de_despliegue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACE_ENGINE", "rekognition")
    with pytest.raises(RuntimeError, match="FACE_ENGINE"):
        face_pipeline.motor_seleccionado()


def test_referencia_de_otro_motor_se_recalcula() -> None:
    """Un embedding de 512 (InsightFace) no se compara con uno de 128 (SFace)."""
    job = {
        "reference_embedding": [0.1] * 512,
        "capture_bucket": "evidences",
        "capture_path": "snap.jpg",
        "reference_bucket": "reference-faces",
        "reference_path": "reference.jpg",
    }
    with (
        patch("face_pipeline.get_storage_image", return_value=b"jpeg") as download,
        patch("face_pipeline.embedding_from_bytes", side_effect=[[1.0, 0.0], [1.0, 0.0]]),
    ):
        score, updated = compare_job(job)
    assert score == 1 and updated == [1.0, 0.0]
    assert download.call_count == 2


def test_referencia_de_otro_motor_sin_foto_es_inconclusa() -> None:
    job = {
        "reference_embedding": [0.1] * 512,
        "capture_bucket": "evidences",
        "capture_path": "snap.jpg",
    }
    with (
        patch("face_pipeline.get_storage_image", return_value=b"jpeg"),
        patch("face_pipeline.embedding_from_bytes", return_value=[1.0, 0.0]),
        pytest.raises(FaceInconclusive),
    ):
        compare_job(job)


def test_precalentar_fallido_no_detiene_el_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FACE_WARMUP", raising=False)
    with patch("face_pipeline.precalentar", side_effect=RuntimeError("sin modelo")):
        worker_stub._precalentar_motor_facial()
    assert worker_stub.MOTOR_FACIAL["status"] == "error"
    assert "sin modelo" in worker_stub.MOTOR_FACIAL["detail"]


def test_precalentar_correcto_queda_en_salud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FACE_WARMUP", raising=False)
    worker_stub.MOTOR_FACIAL.clear()
    with patch("face_pipeline.precalentar", return_value="opencv/test"):
        worker_stub._precalentar_motor_facial()
    assert worker_stub.MOTOR_FACIAL["status"] == "ready"
    assert worker_stub.MOTOR_FACIAL["version"] == "opencv/test"


def test_precalentar_se_puede_apagar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACE_WARMUP", "0")
    with patch("face_pipeline.precalentar") as precalentar:
        worker_stub._precalentar_motor_facial()
    precalentar.assert_not_called()
    assert worker_stub.MOTOR_FACIAL["status"] == "disabled"


# ---------------------------------------------------------------------------
# Con OpenCV instalado (en el worker real y en local con el extra `face`).
# ---------------------------------------------------------------------------


def _jpeg_sin_rostro() -> bytes:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    imagen = np.full((240, 320, 3), 128, dtype=np.uint8)
    ok, datos = cv2.imencode(".jpg", imagen)
    assert ok
    return bytes(datos.tobytes())


def test_opencv_carga_los_modelos(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("cv2")
    monkeypatch.setenv("FACE_ENGINE", "opencv")
    assert face_pipeline.precalentar().startswith("opencv/")


def test_opencv_imagen_sin_rostro_es_inconclusa(monkeypatch: pytest.MonkeyPatch) -> None:
    contenido = _jpeg_sin_rostro()
    monkeypatch.setenv("FACE_ENGINE", "opencv")
    with pytest.raises(FaceInconclusive, match="0 rostros"):
        face_pipeline.embedding_from_bytes(contenido)


def test_opencv_imagen_ilegible_es_inconclusa(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("cv2")
    monkeypatch.setenv("FACE_ENGINE", "opencv")
    with pytest.raises(FaceInconclusive, match="ilegible"):
        face_pipeline.embedding_from_bytes(b"no soy una imagen")


def test_opencv_embedding_tiene_128_valores() -> None:
    """SFace sobre un recorte sintético: comprueba forma, no identidad."""
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from vision import VerificadorOpenCV

    verificador = VerificadorOpenCV()
    imagen = np.random.default_rng(7).integers(0, 255, (240, 320, 3), dtype=np.uint8)
    # Fila con el formato de YuNet: caja, 5 puntos (ojos, nariz, boca) y confianza.
    cara = np.array(
        [[100, 60, 112, 112, 130, 100, 180, 100, 155, 125, 135, 150, 175, 150, 0.99]],
        dtype=np.float32,
    )
    with patch.object(verificador, "contar_rostros", return_value=cara):
        _, datos = cv2.imencode(".png", imagen)
        vector = verificador.embedding(bytes(datos.tobytes()))
    assert len(vector) == 128
    assert all(np.isfinite(vector))
