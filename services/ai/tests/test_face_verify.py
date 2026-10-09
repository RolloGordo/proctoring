"""Pruebas sin imágenes privadas ni dependencias biométricas instaladas."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import tasks
from face_pipeline import FaceInconclusive, compare_job, cosine_similarity
from spikes.face_verify import report


def test_cosine_similarity_identity_orthogonal_and_invalid() -> None:
    assert cosine_similarity([1, 0], [1, 0]) == 1
    assert cosine_similarity([1, 0], [0, 1]) == 0
    assert cosine_similarity([1, 0], [-1, 0]) == 0
    with pytest.raises(FaceInconclusive):
        cosine_similarity([0, 0], [1, 0])


def test_reference_embedding_is_reused() -> None:
    job = {
        "reference_embedding": [1.0, 0.0],
        "capture_bucket": "evidences",
        "capture_path": "snap.jpg",
    }
    with (
        patch("face_pipeline.get_storage_image", return_value=b"jpeg") as download,
        patch("face_pipeline.embedding_from_bytes", return_value=[1, 0]),
    ):
        score, updated = compare_job(job)
    assert score == 1
    assert updated is None
    download.assert_called_once_with("evidences", "snap.jpg")


def test_new_reference_is_returned_to_api() -> None:
    job = {
        "reference_embedding": None,
        "capture_bucket": "evidences",
        "capture_path": "snap.jpg",
        "reference_bucket": "reference-faces",
        "reference_path": "reference.jpg",
    }
    with (
        patch("face_pipeline.get_storage_image", return_value=b"jpeg") as download,
        patch("face_pipeline.embedding_from_bytes", side_effect=[[1, 0], [1, 0]]),
    ):
        score, updated = compare_job(job)
    assert score == 1 and updated == [1, 0]
    assert download.call_count == 2


def test_worker_reports_inconclusive_without_similarity() -> None:
    job = {"session_id": "s1", "student_id": "u1", "similarity_threshold": 0.45}
    with (
        patch.object(tasks, "_get", return_value=job),
        patch.object(tasks, "_post", return_value={"result": "inconclusive"}) as post,
        patch("face_pipeline.compare_job", side_effect=FaceInconclusive("no face")),
    ):
        tasks.verify_face("p1", "snap.jpg")
    payload = post.call_args.args[1]
    assert payload["inconclusive"] is True
    assert payload["similarity"] is None
    assert payload["reference_embedding"] is None


def test_worker_reports_similarity_and_embedding() -> None:
    job = {"session_id": "s1", "student_id": "u1", "similarity_threshold": 0.45}
    with (
        patch.object(tasks, "_get", return_value=job),
        patch.object(tasks, "_post", return_value={}) as post,
        patch("face_pipeline.compare_job", return_value=(0.84, [1.0, 0.0])),
    ):
        tasks.verify_face("p1", "snap.jpg")
    payload = post.call_args.args[1]
    assert payload["inconclusive"] is False and payload["similarity"] == 0.84
    assert payload["reference_embedding"] == [1.0, 0.0]


def test_worker_fails_openly_on_infrastructure_error() -> None:
    job = {"session_id": "s1", "student_id": "u1", "similarity_threshold": 0.45}
    with (
        patch.object(tasks, "_get", return_value=job),
        patch("face_pipeline.compare_job", side_effect=RuntimeError("model missing")),
    ):
        with pytest.raises(RuntimeError, match="model missing"):
            tasks.verify_face("p1", "snap.jpg")


def test_threshold_curve_and_latency_p90() -> None:
    metrics = report([(0.92, True), (0.87, True), (0.12, False), (0.18, False)], [100, 110, 220])
    assert metrics["pairs_genuine"] == 2
    assert metrics["pairs_impostor"] == 2
    assert metrics["latency_p90_cpu_ms"] == 220
    assert any(x["FAR"] == 0 and x["FRR"] == 0 for x in metrics["curves"])
