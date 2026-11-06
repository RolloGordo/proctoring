"""Carga de exámenes reales: estudiantes que rinden y docentes que vigilan (ADR-0011).

Cada usuario virtual es **una persona del escenario** (`preparar.py datos`), con
su token, su examen y sus preguntas: nada de mil copias del mismo usuario, que
en la base serían una sola fila y medirían otra cosa.

El ritmo copia al cliente de verdad, no un bucle a todo gas:

- **Sala de espera:** consulta su estado cada 10 s (`SalaDeEspera.tsx`,
  `ESPERA_MS`) hasta que su docente lo admite.
- **Examen:** guarda respuestas cada 8-15 s (la web agrupa lo escrito cada medio
  segundo y un estudiante responde una pregunta cada pocos segundos a minutos)
  y manda una señal de supervisión de vez en cuando.
- **Entrega:** todos a la vez al final, con un margen de un minuto: es el pico
  real de un examen, igual que el ingreso.
- **Docente:** refresca la sala y las alertas cada 5 s y admite a quien espera.

Presupuestos (salen con código 1 si se rompen, para el CI):
`UMBRAL_P95_MS` (500) por endpoint, `UMBRAL_ENTREGA_P95_MS` (1500) para la
entrega, que califica, y `UMBRAL_ERRORES` (0.01).
"""

from __future__ import annotations

import itertools
import json
import os
import random
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from locust import HttpUser, between, constant, events, task
from locust.exception import StopUser

ESCENARIO = json.loads(
    (Path(__file__).resolve().parent / ".datos" / "escenario.json").read_text(encoding="utf-8")
)
#: Cuánto dura el examen desde que el estudiante entra hasta que entrega.
EXAMEN_SEGUNDOS = float(os.environ.get("EXAMEN_SEGUNDOS", "240"))
#: Ventana en la que entregan todos: el pico de la entrega.
MARGEN_ENTREGA_SEGUNDOS = float(os.environ.get("MARGEN_ENTREGA_SEGUNDOS", "60"))
UMBRAL_P95_MS = float(os.environ.get("UMBRAL_P95_MS", "500"))
UMBRAL_ENTREGA_P95_MS = float(os.environ.get("UMBRAL_ENTREGA_P95_MS", "1500"))
UMBRAL_ERRORES = float(os.environ.get("UMBRAL_ERRORES", "0.01"))
#: La sala de espera con el margen al azar de `sondeo.ts` (1) o el intervalo fijo
#: de antes (0). Así se mide el antes y el después del cambio en el cliente.
SONDEO_CON_MARGEN = os.environ.get("SONDEO_CON_MARGEN", "1") == "1"
#: Cuántos admite el docente en cada vuelta de 5 s. La web admite de uno en uno
#: con un clic (`Participantes.tsx`): 5 cada 5 s ya es rápido para una persona.
#: Con 30 por vuelta y un docente para tres exámenes, el límite de 120
#: escrituras por minuto y persona lo cortaba con 429, y con razón.
ADMITIR_POR_VUELTA = int(os.environ.get("ADMITIR_POR_VUELTA", "5"))

_lock = threading.Lock()
_estudiantes = itertools.cycle(
    [
        (examen, estudiante)
        for examen in ESCENARIO["examenes"]
        for estudiante in examen["estudiantes"]
    ]
)
_examenes = itertools.cycle(ESCENARIO["examenes"])


def _siguiente(iterador: Any) -> Any:
    with _lock:
        return next(iterador)


def _ahora() -> str:
    return datetime.now(UTC).isoformat()


class Estudiante(HttpUser):
    """Rinde un examen de principio a fin."""

    def wait_time(self) -> float:
        # En la sala, el ritmo del sondeo; rindiendo, el de quien piensa y responde.
        if self.fase == "espera":
            return random.uniform(8, 12) if SONDEO_CON_MARGEN else 10.0
        return random.uniform(8, 15)

    def on_start(self) -> None:
        self.examen, persona = _siguiente(_estudiantes)
        self.sid = self.examen["id"]
        self.yo = persona["id"]
        self.client.headers["Authorization"] = f"Bearer {persona['token']}"
        self.fase = "espera"
        self.preguntas: list[dict[str, Any]] = []
        self.entrega_en = time.time() + EXAMEN_SEGUNDOS + random.uniform(0, MARGEN_ENTREGA_SEGUNDOS)

        self.client.post(
            "/api/v1/sessions/join",
            json={"access_code": self.examen["codigo"]},
            name="ingreso: código",
        )
        with self.client.post(
            f"/api/v1/exam/{self.sid}/enroll",
            json={"accepts_supervision": True},
            name="ingreso: matrícula",
            catch_response=True,
        ) as r:
            # De una corrida anterior puede estar ya matriculado: no es un fallo.
            if r.status_code == 400 and "ya" in r.text.lower():
                r.success()

    @task
    def paso(self) -> None:
        if self.fase == "espera":
            self._sala_de_espera()
        elif self.fase == "rindiendo":
            if time.time() >= self.entrega_en:
                self._entregar()
            else:
                random.choices([self._guardar, self._senal, self._estado], weights=[70, 25, 5])[0]()
        else:
            raise StopUser()

    def _sala_de_espera(self) -> None:
        r = self.client.get(f"/api/v1/exam/{self.sid}/me", name="sala de espera: mi estado")
        if r.ok and r.json().get("can_take_exam"):
            q = self.client.get(f"/api/v1/exam/{self.sid}/questions", name="examen: preguntas")
            if q.ok:
                self.preguntas = q.json()
                self.fase = "rindiendo"

    def _respuesta(self, pregunta: dict[str, Any]) -> dict[str, Any]:
        if pregunta["question_type"] == "numeric":
            return {"question_id": pregunta["id"], "numeric_answer": str(random.choice([10, 8]))}
        return {
            "question_id": pregunta["id"],
            "selected_option_id": random.choice(pregunta["options"])["id"],
        }

    def _guardar(self) -> None:
        lote = [
            self._respuesta(p) for p in random.sample(self.preguntas, k=min(2, len(self.preguntas)))
        ]
        self.client.put(
            f"/api/v1/exam/{self.sid}/answers",
            json={"answers": lote},
            name="examen: guardar respuestas",
        )

    def _senal(self) -> None:
        self.client.post(
            "/api/v1/events",
            json={
                "session_id": self.sid,
                "student_id": self.yo,
                "question_id": random.choice(self.preguntas)["id"] if self.preguntas else None,
                "event_type": "focus_lost",
                "started_at": _ahora(),
                "duration_ms": random.randint(500, 8000),
                "metadata": {"carga": True},
            },
            name="examen: señal de supervisión",
        )

    def _estado(self) -> None:
        self.client.get(f"/api/v1/exam/{self.sid}/me", name="examen: mi estado")

    def _entregar(self) -> None:
        self.client.post(f"/api/v1/exam/{self.sid}/submit", name="entrega")
        self.fase = "entregado"


class Docente(HttpUser):
    """Vigila un examen: refresca la sala y las alertas, y admite a quien espera."""

    # Uno por examen: el escenario decide cuántos, no el reparto por pesos.
    fixed_count = len(ESCENARIO["examenes"])
    wait_time = constant(5)

    def on_start(self) -> None:
        self.examen = _siguiente(_examenes)
        self.sid = self.examen["id"]
        self.client.headers["Authorization"] = f"Bearer {self.examen['docente_token']}"

    @task
    def vigilar(self) -> None:
        r = self.client.get(
            f"/api/v1/sessions/{self.sid}/participants", name="docente: sala de espera"
        )
        if r.ok:
            pendientes = [p for p in r.json() if p["verification_status"] == "pending"]
            for p in pendientes[:ADMITIR_POR_VUELTA]:
                self.client.post(
                    f"/api/v1/sessions/{self.sid}/participants/{p['student_id']}/identity",
                    json={"approve": True},
                    name="docente: admitir",
                )
        self.client.get(f"/api/v1/sessions/{self.sid}/alerts", name="docente: alertas")


_ = between  # re-exportado para quien quiera cambiar el ritmo desde aquí


@events.quitting.add_listener
def _presupuestos(environment: Any, **_kw: Any) -> None:
    """Falla la corrida si se rompe un presupuesto: así sirve de puerta en el CI."""
    stats = environment.stats
    rotos: list[str] = []
    if stats.total.fail_ratio > UMBRAL_ERRORES:
        rotos.append(f"errores {stats.total.fail_ratio:.2%} > {UMBRAL_ERRORES:.0%}")
    for entrada in stats.entries.values():
        if entrada.num_requests == 0:
            continue
        umbral = UMBRAL_ENTREGA_P95_MS if entrada.name == "entrega" else UMBRAL_P95_MS
        p95 = entrada.get_response_time_percentile(0.95)
        if p95 > umbral:
            rotos.append(f"p95 de «{entrada.name}» {p95:.0f} ms > {umbral:.0f} ms")
    if rotos:
        print("PRESUPUESTO ROTO: " + "; ".join(rotos))
        environment.process_exit_code = 1
    else:
        print("Presupuestos cumplidos.")
