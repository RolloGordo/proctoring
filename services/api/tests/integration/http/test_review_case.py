"""Riesgo por estudiante de una sesión."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.integration


class TestRiesgoDeLaSesion:
    """`GET /sessions/{id}/risk`: el semáforo de Entregas (revisión del 14/11)."""

    def test_ordena_de_mas_a_menos_sospechoso(self, client: Any, contract_example: Any) -> None:
        tranquilo = {**contract_example("focus_lost"), "duration_ms": 1000}
        sospechoso = {
            **contract_example("suspicious_process"),
            "student_id": "11111111-2222-4333-8444-555555555555",
        }
        client.post("/api/v1/events", json=tranquilo)
        for _ in range(3):
            client.post("/api/v1/events", json=sospechoso)

        r = client.get(f"/api/v1/sessions/{tranquilo['session_id']}/risk")

        assert r.status_code == 200
        cuerpo = r.json()
        assert [x["student_id"] for x in cuerpo] == [
            sospechoso["student_id"],
            tranquilo["student_id"],
        ]
        assert cuerpo[0]["level"] == "high" and cuerpo[0]["top_signal"] == "suspicious_process"
        assert cuerpo[0]["signal_count"] == 3
        assert cuerpo[1]["level"] == "low"

    def test_un_estudiante_no_lo_ve(self, authed_client: Any, contract_example: Any) -> None:
        from tests.conftest import STUDENT_TOKEN

        sid = contract_example("focus_lost")["session_id"]
        r = authed_client.get(
            f"/api/v1/sessions/{sid}/risk", headers={"Authorization": f"Bearer {STUDENT_TOKEN}"}
        )

        assert r.status_code == 403
