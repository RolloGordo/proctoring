"""Siembra exámenes con presets distintos para la batería completa (18/11/2026).

    uv run python completa/sembrar.py --presets strict,standard,basic,custom-vista,custom-voz \
        --por-examen 60 --salida escenario-k6.json

A diferencia de `preparar.py datos` (todo con el preset por defecto), aquí cada
examen lleva su preset, y los `custom` solo vigilan algunos módulos. Así la
prueba puede comprobar, con carga, que una señal de un módulo apagado se
rechaza y una de uno encendido se acepta con la severidad que dicta el dominio.

Solo contra el entorno local: reutiliza `preparar.py`, que se niega a tocar otra
cosa que Supabase local.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from preparar import (  # noqa: E402
    API,
    AUTH_LOCAL,
    DATOS,
    PREGUNTAS,
    Firmador,
    crear_usuario,
    estado_supabase,
)

#: Los `custom`: qué módulos enciende el docente. El resto queda apagado y sus
#: señales tienen que rechazarse.
CUSTOM: dict[str, dict[str, dict[str, Any]]] = {
    "custom-vista": {
        "gaze": {"yaw_degrees": 25, "min_duration_ms": 3000},
        "extra_person": {"min_faces": 2},
    },
    "custom-voz": {
        "ai_voice": {"similarity_threshold": 0.6, "synthetic_threshold": 0.5},
        "external_voices": {"min_speakers": 2},
    },
}


def sembrar(presets: list[str], por_examen: int, salida: str) -> None:
    s = estado_supabase()
    firmador = Firmador()
    marca = int(time.time())
    cab = {"apikey": s["SERVICE_ROLE_KEY"], "Authorization": f"Bearer {s['SERVICE_ROLE_KEY']}"}
    correo_docente = f"docente.completa.{marca}@carga.test"

    with httpx.Client(base_url=AUTH_LOCAL, headers=cab, timeout=30) as admin:
        docente = crear_usuario(admin, correo_docente, "Docente batería completa")
        admin.patch(
            "/rest/v1/profiles", params={"id": f"eq.{docente}"}, json={"role": "teacher"}
        ).raise_for_status()
        correos = [
            f"alumno{n}.completa.{marca}@carga.test" for n in range(len(presets) * por_examen)
        ]
        print(f"Creando {len(correos)} estudiantes…")
        with ThreadPoolExecutor(max_workers=16) as hilos:
            ids = list(hilos.map(lambda c: crear_usuario(admin, c, c.split("@")[0]), correos))

    token_docente = firmador.token(docente, correo_docente, horas=8)
    h = {"Authorization": f"Bearer {token_docente}"}
    ahora = datetime.now(UTC)
    escenario: dict[str, Any] = {"creado": ahora.isoformat(), "examenes": []}

    with httpx.Client(base_url=API, timeout=30) as api:
        for e, nombre in enumerate(presets):
            preset = "custom" if nombre.startswith("custom") else nombre
            cuerpo: dict[str, Any] = {
                "title": f"Batería completa · {nombre} · {e + 1}",
                "starts_at": (ahora - timedelta(minutes=1)).isoformat(),
                "duration_minutes": 180,
                "entry_tolerance_minutes": 120,
                "preset": preset,
            }
            if preset == "custom":
                cuerpo["modules"] = CUSTOM[nombre]
            r = api.post("/sessions", headers=h, json=cuerpo)
            r.raise_for_status()
            sesion = r.json()
            sid = sesion["id"]
            q = api.post(f"/sessions/{sid}/questions", headers=h, json={"questions": PREGUNTAS})
            q.raise_for_status()
            # La mirada y la voz exigen la pregunta en curso (sin ella no hay
            # con qué comparar lo que se dijo): las pruebas mandan una de estas.
            preguntas = [p["id"] for p in q.json()]
            grupo = range(e * por_examen, (e + 1) * por_examen)
            escenario["examenes"].append(
                {
                    "id": sid,
                    "codigo": sesion["access_code"],
                    "preset": nombre,
                    "modulos": sesion["watched_modules"],
                    "preguntas": preguntas,
                    "docente_id": docente,
                    "docente_email": correo_docente,
                    "docente_token": token_docente,
                    "estudiantes": [
                        {
                            "id": ids[n],
                            "email": correos[n],
                            "token": firmador.token(ids[n], correos[n], horas=8),
                        }
                        for n in grupo
                    ],
                }
            )
            print(f"  {nombre}: {sid} · vigila {', '.join(sesion['watched_modules'])}")

    (DATOS / salida).write_text(json.dumps(escenario), encoding="utf-8")
    print(f"Listo -> .datos/{salida}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--presets", required=True)
    p.add_argument("--por-examen", type=int, default=60)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    sembrar(a.presets.split(","), a.por_examen, a.salida)
