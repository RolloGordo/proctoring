"""Realtime de punta a punta, con WebSocket de verdad (batería completa, 18/11/2026).

    uv run --with websockets python completa/tiempo_real.py --escenario escenario-rt.json \
        --minutos 4 --salida resultados/completa-realtime.json

Lo que hace la web, sin navegador:

- **Cada docente** abre el canal de `SesionEnVivo.tsx`: inserciones en `alerts` y
  `events` de su examen y cambios en `session_participants`.
- **Cada estudiante** abre el de `SalaDeEspera.tsx` y `useAvisosExamen.ts`: su
  fila de participante y las alertas de su examen (RLS le deja ver solo las suyas).
- Los estudiantes entran con el código y se matriculan; el docente los admite
  por la API y se cronometra **cuánto tarda el «admitido» en llegar al
  estudiante** por Realtime (lo que antes resolvía el sondeo cada 10 s).
- Durante `--minutos`, cada estudiante manda señales de todos los tipos cada
  `--cada` segundos. Se cronometra, por tipo, **desde que el cliente manda la
  señal hasta que el docente la ve** (meta SMART: alerta en < 5 s), y cuántas
  alertas no llegaron nunca.

Los relojes son el mismo: todo corre en la misma máquina.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import websockets

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from preparar import API, DATOS, estado_supabase  # noqa: E402

SENALES: list[tuple[str, int, int]] = [
    ("focus_lost", 1_000, 45_000),
    ("gaze_away", 2_000, 20_000),
    ("face_absent", 2_000, 25_000),
    ("extra_person", 1_000, 5_000),
    ("suspicious_process", 0, 0),
    ("extra_display", 0, 0),
    ("speech_detected", 1_000, 8_000),
    ("copy_attempt", 0, 0),
    ("prohibited_object", 1_000, 5_000),
    ("framing_lost", 5_000, 40_000),
]

#: Lo que llega por Realtime: id -> instante (time.monotonic()).
eventos_vistos: dict[str, float] = {}
alertas_vistas_docente: dict[str, float] = {}
alertas_vistas_estudiante: dict[str, float] = {}
admisiones_vistas: dict[str, float] = {}
#: Lo que se mandó: id del evento -> (instante, tipo, severidad).
enviados: dict[str, tuple[float, str, str]] = {}
admisiones_pedidas: dict[str, float] = {}
latencias_api: dict[str, list[float]] = defaultdict(list)
errores: dict[str, int] = defaultdict(int)
canales = {"pedidos": 0, "unidos": 0, "suscritos": 0, "caidos": 0}


class Canal:
    """Un canal de Realtime con su latido, como `supabase-js`."""

    def __init__(self, url: str, token: str, tema: str, cambios: list[dict[str, str]]) -> None:
        self.url, self.token, self.tema, self.cambios = url, token, tema, cambios
        self.listo = asyncio.Event()
        self.ref = 1

    async def correr(self, fin: asyncio.Event) -> None:
        canales["pedidos"] += 1
        try:
            async with websockets.connect(self.url, max_size=2**22, open_timeout=60) as ws:
                await ws.send(
                    json.dumps(
                        {
                            "topic": f"realtime:{self.tema}",
                            "event": "phx_join",
                            "payload": {
                                "config": {
                                    "broadcast": {"ack": False, "self": False},
                                    "presence": {"key": ""},
                                    "postgres_changes": self.cambios,
                                    "private": False,
                                },
                                "access_token": self.token,
                            },
                            "ref": "1",
                            "join_ref": "1",
                        }
                    )
                )
                latido = asyncio.create_task(self._latir(ws))
                lector = asyncio.create_task(self._leer(ws))
                await fin.wait()
                latido.cancel()
                lector.cancel()
        except Exception as fallo:  # noqa: BLE001 — se cuenta, no se esconde
            canales["caidos"] += 1
            errores[f"ws: {type(fallo).__name__}"] += 1

    async def _latir(self, ws: Any) -> None:
        while True:
            await asyncio.sleep(25)
            self.ref += 1
            await ws.send(
                json.dumps(
                    {"topic": "phoenix", "event": "heartbeat", "payload": {}, "ref": str(self.ref)}
                )
            )

    async def _leer(self, ws: Any) -> None:
        async for crudo in ws:
            t = time.monotonic()
            m = json.loads(crudo)
            ev, carga = m.get("event"), m.get("payload") or {}
            if ev == "phx_reply" and m.get("ref") == "1":
                if carga.get("status") == "ok":
                    canales["unidos"] += 1
                else:
                    errores[f"unión: {str(carga)[:80]}"] += 1
            elif (
                ev == "system"
                and carga.get("status") == "ok"
                and carga.get("extension") == "postgres_changes"
            ):
                canales["suscritos"] += 1
                self.listo.set()
            elif ev == "postgres_changes":
                self.recibir(carga.get("data") or {}, t)

    def recibir(self, datos: dict[str, Any], t: float) -> None:  # se sobreescribe
        raise NotImplementedError


class CanalDocente(Canal):
    def recibir(self, datos: dict[str, Any], t: float) -> None:
        r = datos.get("record") or {}
        tabla = datos.get("table")
        if tabla == "alerts":
            alertas_vistas_docente.setdefault(r.get("event_id", ""), t)
        elif tabla == "events":
            eventos_vistos.setdefault(r.get("id", ""), t)


class CanalEstudiante(Canal):
    def __init__(self, *a: Any, yo: str) -> None:
        super().__init__(*a)
        self.yo = yo

    def recibir(self, datos: dict[str, Any], t: float) -> None:
        r = datos.get("record") or {}
        if datos.get("table") == "alerts":
            alertas_vistas_estudiante.setdefault(r.get("event_id", ""), t)
        elif datos.get("table") == "session_participants" and r.get("verification_status") in (
            "verified",
            "manually_approved",
        ):
            admisiones_vistas.setdefault(r.get("student_id", ""), t)


async def llamar(
    cliente: httpx.AsyncClient, nombre: str, metodo: str, ruta: str, token: str, cuerpo: Any = None
) -> httpx.Response | None:
    t = time.monotonic()
    try:
        r = await cliente.request(
            metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
        )
    except httpx.HTTPError as fallo:
        errores[f"{nombre}: {type(fallo).__name__}"] += 1
        return None
    latencias_api[nombre].append((time.monotonic() - t) * 1000)
    if r.status_code >= 400:
        errores[f"{nombre}: HTTP {r.status_code}"] += 1
    return r


async def estudiante(
    cliente: httpx.AsyncClient,
    examen: dict[str, Any],
    yo: dict[str, Any],
    hasta: float,
    cada: float,
) -> None:
    sid, tok = examen["id"], yo["token"]
    r = await llamar(
        cliente, "ingreso: código", "POST", "/sessions/join", tok, {"access_code": examen["codigo"]}
    )
    if r is None or r.status_code != 200:
        return
    await llamar(
        cliente,
        "ingreso: matrícula",
        "POST",
        f"/exam/{sid}/enroll",
        tok,
        {"accepts_supervision": True},
    )
    # Espera a que el docente lo admita (lo sabrá por Realtime; aquí basta mirar el dict).
    while yo["id"] not in admisiones_vistas and time.monotonic() < hasta:
        await asyncio.sleep(0.5)
    while time.monotonic() < hasta:
        await asyncio.sleep(random.uniform(cada * 0.6, cada * 1.4))
        tipo, minimo, maximo = random.choice(SENALES)
        t = time.monotonic()
        r = await llamar(
            cliente,
            "señal",
            "POST",
            "/events",
            tok,
            {
                "session_id": sid,
                "student_id": yo["id"],
                "question_id": random.choice(examen["preguntas"]),
                "event_type": tipo,
                "started_at": datetime.now(UTC).isoformat(),
                "duration_ms": random.randint(minimo, maximo),
                "metadata": {"carga": "realtime"},
            },
        )
        if r is not None and r.status_code == 201:
            enviados[r.json()["id"]] = (t, tipo, r.json()["severity"])


async def docente(cliente: httpx.AsyncClient, examen: dict[str, Any], hasta: float) -> None:
    """Admite a quien espera, de cinco en cinco como una persona con prisa."""
    admitidos: set[str] = set()
    while time.monotonic() < hasta and len(admitidos) < len(examen["estudiantes"]):
        r = await llamar(
            cliente,
            "docente: sala",
            "GET",
            f"/sessions/{examen['id']}/participants",
            examen["docente_token"],
        )
        if r is not None and r.status_code == 200:
            for p in [
                p
                for p in r.json()
                if p["verification_status"] == "pending" and p["student_id"] not in admitidos
            ][:5]:
                admisiones_pedidas[p["student_id"]] = time.monotonic()
                await llamar(
                    cliente,
                    "docente: admitir",
                    "POST",
                    f"/sessions/{examen['id']}/participants/{p['student_id']}/identity",
                    examen["docente_token"],
                    {"approve": True},
                )
                admitidos.add(p["student_id"])
        await asyncio.sleep(1)


def resumen(valores: list[float]) -> dict[str, Any]:
    if not valores:
        return {"n": 0}
    v = sorted(valores)
    pct = lambda q: v[min(len(v) - 1, int(q * len(v)))]  # noqa: E731
    return {
        "n": len(v),
        "p50": round(pct(0.5)),
        "p95": round(pct(0.95)),
        "p99": round(pct(0.99)),
        "max": round(v[-1]),
        "media": round(statistics.fmean(v)),
    }


async def principal(a: argparse.Namespace) -> dict[str, Any]:
    esc = json.loads((DATOS / a.escenario).read_text(encoding="utf-8"))
    anon = estado_supabase()["ANON_KEY"]
    url = f"ws://127.0.0.1:54321/realtime/v1/websocket?apikey={anon}&vsn=1.0.0"
    fin = asyncio.Event()
    tareas: list[asyncio.Task[None]] = []
    docentes: list[Canal] = []

    for e in esc["examenes"]:
        f = f"session_id=eq.{e['id']}"
        c = CanalDocente(
            url,
            e["docente_token"],
            f"docente-{e['id']}",
            [
                {"event": "INSERT", "schema": "public", "table": "alerts", "filter": f},
                {"event": "INSERT", "schema": "public", "table": "events", "filter": f},
                {"event": "*", "schema": "public", "table": "session_participants", "filter": f},
            ],
        )
        docentes.append(c)
        tareas.append(asyncio.create_task(c.correr(fin)))
    await asyncio.wait_for(asyncio.gather(*(c.listo.wait() for c in docentes)), 60)

    t_conexion = time.monotonic()
    alumnos: list[Canal] = []
    for e in esc["examenes"]:
        f = f"session_id=eq.{e['id']}"
        for s in e["estudiantes"]:
            c = CanalEstudiante(
                url,
                s["token"],
                f"sala-{s['id']}",
                [
                    {
                        "event": "UPDATE",
                        "schema": "public",
                        "table": "session_participants",
                        "filter": f,
                    },
                    {"event": "INSERT", "schema": "public", "table": "alerts", "filter": f},
                ],
                yo=s["id"],
            )
            alumnos.append(c)
            tareas.append(asyncio.create_task(c.correr(fin)))
    try:
        await asyncio.wait_for(asyncio.gather(*(c.listo.wait() for c in alumnos)), 120)
    except TimeoutError:
        errores["canales de estudiante sin suscribir a los 120 s"] += sum(
            not c.listo.is_set() for c in alumnos
        )
    conexion_s = time.monotonic() - t_conexion
    print(f"{canales['suscritos']} canales suscritos en {conexion_s:.1f} s", flush=True)

    hasta = time.monotonic() + a.minutos * 60
    limites = httpx.Limits(max_connections=200, max_keepalive_connections=200)
    async with httpx.AsyncClient(base_url=API, timeout=30, limits=limites) as cliente:
        await asyncio.gather(
            *(docente(cliente, e, hasta) for e in esc["examenes"]),
            *(
                estudiante(cliente, e, s, hasta, a.cada)
                for e in esc["examenes"]
                for s in e["estudiantes"]
            ),
        )
    await asyncio.sleep(10)  # lo que esté en camino
    fin.set()
    await asyncio.gather(*tareas, return_exceptions=True)

    por_tipo: dict[str, list[float]] = defaultdict(list)
    alerta_docente: dict[str, list[float]] = defaultdict(list)
    alerta_estudiante: list[float] = []
    perdidas = 0
    for eid, (t, tipo, sev) in enviados.items():
        if eid in eventos_vistos:
            por_tipo[tipo].append((eventos_vistos[eid] - t) * 1000)
        if sev in ("medium", "high"):
            if eid in alertas_vistas_docente:
                alerta_docente[tipo].append((alertas_vistas_docente[eid] - t) * 1000)
            else:
                perdidas += 1
            if eid in alertas_vistas_estudiante:
                alerta_estudiante.append((alertas_vistas_estudiante[eid] - t) * 1000)
    admision = [
        (admisiones_vistas[s] - t) * 1000
        for s, t in admisiones_pedidas.items()
        if s in admisiones_vistas
    ]
    todas = [x for v in alerta_docente.values() for x in v]
    con_alerta = sum(1 for (_, _, s) in enviados.values() if s in ("medium", "high"))
    return {
        "estudiantes": sum(len(e["estudiantes"]) for e in esc["examenes"]),
        "examenes": len(esc["examenes"]),
        "minutos": a.minutos,
        "canales": canales,
        "suscripcion_s": round(conexion_s, 1),
        "senales_enviadas": len(enviados),
        "senales_vistas_por_docente": sum(1 for e in enviados if e in eventos_vistos),
        "alertas_enviadas": con_alerta,
        "alertas_perdidas": perdidas,
        "senal_a_docente_ms": {k: resumen(v) for k, v in sorted(por_tipo.items())},
        "alerta_a_docente_ms": {
            "todas": resumen(todas),
            **{k: resumen(v) for k, v in sorted(alerta_docente.items())},
        },
        "alerta_a_estudiante_ms": resumen(alerta_estudiante),
        "admision_a_estudiante_ms": resumen(admision),
        "admisiones": {"pedidas": len(admisiones_pedidas), "vistas": len(admision)},
        "api_ms": {k: resumen(v) for k, v in latencias_api.items()},
        "errores": dict(errores),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--escenario", required=True)
    p.add_argument("--minutos", type=float, default=4)
    p.add_argument(
        "--cada", type=float, default=6, help="segundos medios entre señales de un estudiante"
    )
    p.add_argument("--salida", required=True)
    args = p.parse_args()
    res = asyncio.run(principal(args))
    Path(args.salida).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                k: res[k]
                for k in (
                    "canales",
                    "senales_enviadas",
                    "alertas_enviadas",
                    "alertas_perdidas",
                    "errores",
                )
            },
            ensure_ascii=False,
        )
    )
    print("alerta->docente", res["alerta_a_docente_ms"]["todas"])
    print("admisión->estudiante", res["admision_a_estudiante_ms"])
