"""La cola de IA por voz bajo carga, con audio y worker de verdad (18/11/2026).

    uv run python completa/ia_audio.py --escenario escenario-ia.json --audios video/voz \
        --rafagas 1,10,30 --salida resultados/completa-ia.json

El camino completo de un fragmento con habla, igual que la web:

1. pedir la URL firmada (`POST /evidence/upload-url`);
2. subir el WAV **directo a Storage** (la API no lo ve);
3. mandar `speech_detected` con `evidence_path` y la pregunta en curso: la API
   lo guarda y lo encola en Redis;
4. el worker de IA (la imagen de producción, con sus mismos límites) baja el
   audio, lo transcribe con faster-whisper, lo compara con el enunciado y
   devuelve el análisis a la API.

Se mide, por ráfaga de N estudiantes que hablan a la vez, desde que el cliente
manda el evento hasta que el análisis está guardado (meta SMART: < 10 s), cuánto
de eso es espera en la cola y cuánto proceso, y si la similitud con el
enunciado sale alta cuando el audio es el enunciado leído en voz alta.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from preparar import API, AUTH_LOCAL, DATOS, estado_supabase  # noqa: E402


def resumen(v: list[float]) -> dict[str, Any]:
    if not v:
        return {"n": 0}
    v = sorted(v)
    q = lambda x: v[min(len(v) - 1, int(x * len(v)))]  # noqa: E731
    return {
        "n": len(v),
        "p50": round(q(0.5)),
        "p95": round(q(0.95)),
        "max": round(v[-1]),
        "media": round(statistics.fmean(v)),
    }


def local(url: str) -> str:
    """La URL firmada trae el host de Docker; desde el VPS se llega por 54321."""
    p = urlsplit(url)
    return urlunsplit(("http", "127.0.0.1:54321", p.path, p.query, ""))


def preparar_estudiantes(esc: dict[str, Any]) -> list[dict[str, Any]]:
    """Entran, se matriculan, el docente los admite y bajan las preguntas."""
    listos: list[dict[str, Any]] = []
    with httpx.Client(base_url=API, timeout=30) as api:
        for e in esc["examenes"]:
            hd = {"Authorization": f"Bearer {e['docente_token']}"}
            for s in e["estudiantes"]:
                h = {"Authorization": f"Bearer {s['token']}"}
                api.post(
                    "/sessions/join", headers=h, json={"access_code": e["codigo"]}
                ).raise_for_status()
                r = api.post(
                    f"/exam/{e['id']}/enroll", headers=h, json={"accepts_supervision": True}
                )
                if r.status_code >= 400 and "ya" not in r.text.lower():
                    r.raise_for_status()
                api.post(
                    f"/sessions/{e['id']}/participants/{s['id']}/identity",
                    headers=hd,
                    json={"approve": True},
                ).raise_for_status()
                q = api.get(f"/exam/{e['id']}/questions", headers=h)
                q.raise_for_status()
                listos.append({**s, "sid": e["id"], "preguntas": q.json()})
    return listos


def hablar(a: dict[str, Any], wav: bytes, pregunta: dict[str, Any]) -> dict[str, Any]:
    """Un estudiante habla: URL firmada, subida, evento. Devuelve el id y los tiempos."""
    h = {"Authorization": f"Bearer {a['token']}"}
    with httpx.Client(base_url=API, timeout=60) as api:
        t0 = time.time()
        u = api.post(
            "/evidence/upload-url",
            headers=h,
            json={
                "session_id": a["sid"],
                "student_id": a["id"],
                "kind": "audio",
                "extension": "wav",
                "event_type": "speech_detected",
            },
        )
        u.raise_for_status()
        permiso = u.json()
        subida = httpx.put(
            local(permiso["url"]), content=wav, headers={"Content-Type": "audio/wav"}, timeout=60
        )
        subida.raise_for_status()
        t_subida = time.time()
        r = api.post(
            "/events",
            headers=h,
            json={
                "session_id": a["sid"],
                "student_id": a["id"],
                "question_id": pregunta["id"],
                "event_type": "speech_detected",
                "started_at": datetime.now(UTC).isoformat(),
                "duration_ms": 8000,
                "metadata": {"carga": "ia"},
                "evidence_path": permiso["path"],
            },
        )
        r.raise_for_status()
        return {"id": r.json()["id"], "t_evento": time.time(), "subida_ms": (t_subida - t0) * 1000}


def esperar_analisis(
    ids: list[str], servicio: dict[str, str], limite_s: float
) -> dict[str, dict[str, Any]]:
    vistos: dict[str, dict[str, Any]] = {}
    fin = time.time() + limite_s
    with httpx.Client(base_url=AUTH_LOCAL, headers=servicio, timeout=30) as db:
        while len(vistos) < len(ids) and time.time() < fin:
            faltan = [i for i in ids if i not in vistos]
            for trozo in range(0, len(faltan), 100):
                r = db.get(
                    "/rest/v1/audio_analyses",
                    params={
                        "event_id": f"in.({','.join(faltan[trozo : trozo + 100])})",
                        "select": "event_id,transcript,similarity,synthetic_voice_score,processing_ms,processed_at",
                    },
                )
                r.raise_for_status()
                ahora = time.time()
                for fila in r.json():
                    vistos[fila["event_id"]] = {**fila, "visto": ahora}
            time.sleep(0.5)
    return vistos


def principal(a: argparse.Namespace) -> dict[str, Any]:
    esc = json.loads((DATOS / a.escenario).read_text(encoding="utf-8"))
    s = estado_supabase()
    servicio = {"apikey": s["SERVICE_ROLE_KEY"], "Authorization": f"Bearer {s['SERVICE_ROLE_KEY']}"}
    audios = sorted(Path(a.audios).glob("*.wav"))
    assert audios, f"no hay .wav en {a.audios}"
    wavs = {p.stem: p.read_bytes() for p in audios}
    alumnos = preparar_estudiantes(esc)
    print(f"{len(alumnos)} estudiantes listos; audios: {', '.join(wavs)}", flush=True)

    resultado: dict[str, Any] = {"audios": {k: len(v) for k, v in wavs.items()}, "rafagas": []}
    usado = 0
    for n in [int(x) for x in a.rafagas.split(",")]:
        grupo = alumnos[usado : usado + n]
        usado += n
        assert len(grupo) == n, "faltan estudiantes para esa ráfaga"
        nombres = list(wavs)
        trabajos = []
        for i, al in enumerate(grupo):
            nombre = nombres[i % len(nombres)]
            # El audio es el enunciado leído: la pregunta en curso es la numérica,
            # cuyo enunciado es el que se grabó (ver README de la batería).
            pregunta = next(p for p in al["preguntas"] if p["question_type"] == "numeric")
            trabajos.append((al, nombre, pregunta))
        t_inicio = time.time()
        with ThreadPoolExecutor(max_workers=n) as hilos:
            enviados = list(
                hilos.map(lambda t: {**hablar(t[0], wavs[t[1]], t[2]), "audio": t[1]}, trabajos)
            )
        vistos = esperar_analisis([e["id"] for e in enviados], servicio, a.limite)
        e2e, proceso, cola, subida = [], [], [], []
        similitudes: dict[str, list[float]] = {}
        for e in enviados:
            subida.append(e["subida_ms"])
            fila = vistos.get(e["id"])
            if not fila:
                continue
            total = (fila["visto"] - e["t_evento"]) * 1000
            e2e.append(total)
            if fila.get("processing_ms") is not None:
                proceso.append(fila["processing_ms"])
                cola.append(max(0.0, total - fila["processing_ms"]))
            if fila.get("similarity") is not None:
                similitudes.setdefault(e["audio"], []).append(float(fila["similarity"]))
        ejemplo = next(iter(vistos.values()), {})
        r = {
            "estudiantes": n,
            "analizados": len(vistos),
            "segundos_hasta_el_ultimo": round(
                max((v["visto"] for v in vistos.values()), default=t_inicio) - t_inicio, 1
            ),
            "subida_ms": resumen(subida),
            "evento_a_analisis_ms": resumen(e2e),
            "proceso_ms": resumen(proceso),
            "espera_en_cola_ms": resumen(cola),
            "bajo_10s": sum(1 for x in e2e if x < 10_000),
            "similitud_media_por_audio": {
                k: round(statistics.fmean(v), 3) for k, v in similitudes.items()
            },
            "ejemplo_transcripcion": (ejemplo.get("transcript") or "")[:160],
        }
        resultado["rafagas"].append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        time.sleep(a.pausa)
    return resultado


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--escenario", required=True)
    p.add_argument("--audios", required=True, help="carpeta con .wav (16 kHz mono)")
    p.add_argument("--rafagas", default="1,10,30")
    p.add_argument(
        "--limite", type=float, default=900, help="segundos máximos esperando una ráfaga"
    )
    p.add_argument("--pausa", type=float, default=20)
    p.add_argument("--salida", required=True)
    args = p.parse_args()
    res = principal(args)
    Path(args.salida).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
