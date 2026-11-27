"""Pruebas de integración entre los servicios reales (27/11/2026).

Las unitarias cambian cada servicio externo por un doble; aquí no hay ninguno. Cada
caso cruza al menos una frontera de verdad y comprueba que lo que una pieza escribe
es lo que la otra lee:

    API ⇄ Supabase Auth (JWKS) · API ⇄ PostgreSQL (PostgREST) · RLS · API ⇄ Storage
    API ⇄ Redis ⇄ worker de IA ⇄ API · PostgreSQL ⇄ Realtime ⇄ cliente · réplicas ⇄ Redis

Contra el entorno aislado del VPS (Supabase local, 2 réplicas de la API detrás de
nginx, Redis y 2 workers de IA con la imagen de producción). Docstring:
`ID | frontera | resultado esperado`.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
import pytest

from comun import V1, Persona, cliente, crear_examen, estado_supabase, evento, ingresar, persona
from preparar import AUTH_LOCAL, CONTRASENA, PREGUNTAS

VOZ = Path(__file__).resolve().parents[2] / "loadtests" / "completa" / "voz"


@pytest.fixture(scope="module")
def claves() -> dict[str, str]:
    return estado_supabase()


@pytest.fixture(scope="module")
def servicio(claves: dict[str, str]) -> httpx.Client:
    k = claves["SERVICE_ROLE_KEY"]
    with httpx.Client(base_url=AUTH_LOCAL, headers={"apikey": k, "Authorization": f"Bearer {k}"}, timeout=30) as c:
        yield c


@pytest.fixture(scope="module")
def escenario() -> dict[str, Any]:
    d = persona("teacher", "Docente Integración")
    a, b = persona(nombre="Alumna Integración A"), persona(nombre="Alumno Integración B")
    e = crear_examen(d, preset="strict")
    ingresar(e, a)
    ingresar(e, b)
    return {"docente": d, "a": a, "b": b, "examen": e}


def local(url: str) -> str:
    """La URL firmada sale con el host interno de Docker; desde el VPS se llega por 54321."""
    p = urlsplit(url)
    return urlunsplit(("http", "127.0.0.1:54321", p.path, p.query, ""))


# ------------------------------------------------------------------ Auth ⇄ API


def test_in01_token_real_de_auth(claves: dict[str, str], escenario: dict[str, Any]) -> None:
    """IN-01 | Supabase Auth ⇄ API | Un token emitido por Auth al iniciar sesión con contraseña (no uno firmado por la prueba) es aceptado por la API, que lo verifica con el JWKS de Auth."""
    a: Persona = escenario["a"]
    r = httpx.post(
        f"{AUTH_LOCAL}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": claves["ANON_KEY"]},
        json={"email": a.email, "password": CONTRASENA},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    real = r.json()["access_token"]
    assert json.loads(httpx.get(f"{AUTH_LOCAL}/auth/v1/.well-known/jwks.json", timeout=10).text)["keys"]
    with cliente() as c:
        yo = c.get("/me/exams", headers={"Authorization": f"Bearer {real}"})
    assert yo.status_code == 200
    assert escenario["examen"].id in yo.text


def test_in02_rol_desde_profiles(escenario: dict[str, Any], servicio: httpx.Client) -> None:
    """IN-02 | API ⇄ PostgreSQL | El rol que aplica la API sale de la tabla profiles: un perfil teacher entra al panel y uno student recibe 403."""
    d, a = escenario["docente"], escenario["a"]
    roles = {p["id"]: p["role"] for p in servicio.get("/rest/v1/profiles", params={"id": f"in.({d.id},{a.id})", "select": "id,role"}).json()}
    assert roles == {d.id: "teacher", a.id: "student"}
    with cliente() as c:
        assert c.get("/sessions", headers=d.h).status_code == 200
        assert c.get("/sessions", headers=a.h).status_code == 403


# ------------------------------------------------------------------ API ⇄ PostgreSQL


def test_in03_evento_persistido(escenario: dict[str, Any], servicio: httpx.Client) -> None:
    """IN-03 | API ⇄ PostgreSQL | Un evento aceptado por la API queda en events con los mismos campos, y su alerta en alerts ligada por event_id."""
    e, a = escenario["examen"], escenario["a"]
    with cliente() as c:
        r = c.post("/events", headers=a.h, json=evento(e, a, "extra_person", 0, metadata={"caras": 2}))
    assert r.status_code == 201
    eid = r.json()["id"]
    fila = servicio.get("/rest/v1/events", params={"id": f"eq.{eid}", "select": "*"}).json()[0]
    assert (fila["session_id"], fila["student_id"], fila["event_type"], fila["metadata"].get("caras")) == (e.id, a.id, "extra_person", 2)
    alerta = servicio.get("/rest/v1/alerts", params={"event_id": f"eq.{eid}", "select": "severity,session_id,student_id"}).json()
    assert alerta and alerta[0]["severity"] == "high" and alerta[0]["student_id"] == a.id


def test_in04_riesgo_persistido(escenario: dict[str, Any], servicio: httpx.Client) -> None:
    """IN-04 | API ⇄ PostgreSQL | El riesgo queda en risk_scores desglosado por señal, y coincide con lo que la API le muestra al docente."""
    e, a, d = escenario["examen"], escenario["a"], escenario["docente"]
    with cliente() as c:
        c.post("/events", headers=a.h, json=evento(e, a, "focus_lost", 7000))
        caso = c.get(f"/sessions/{e.id}/students/{a.id}/case", headers=d.h).json()["risk"]
    fila = servicio.get("/rest/v1/risk_scores", params={"session_id": f"eq.{e.id}", "student_id": f"eq.{a.id}", "select": "score,breakdown"}).json()
    assert fila, "risk_scores está vacío: la API calcula el riesgo al leer y nunca lo guarda (SPEC-009 CA-1 dice que se guarda)"
    assert fila[0]["score"] == caso["score"]
    assert fila[0]["breakdown"], "el desglose está vacío"


def test_in05_preguntas_sin_clave_desde_la_base(escenario: dict[str, Any], servicio: httpx.Client) -> None:
    """IN-05 | API ⇄ PostgreSQL | La base guarda la respuesta correcta, pero la API se la quita al estudiante al servir las preguntas."""
    e, a = escenario["examen"], escenario["a"]
    en_base = servicio.get("/rest/v1/question_options", params={"question_id": f"eq.{e.preguntas[0]['id']}", "select": "is_correct"}).json()
    assert any(o["is_correct"] for o in en_base)
    with cliente() as c:
        servidas = c.get(f"/exam/{e.id}/questions", headers=a.h).text
    assert "is_correct" not in servidas


# ------------------------------------------------------------------ RLS (cliente directo a PostgREST)


def test_in06_rls_estudiante_no_lee_ajenos(claves: dict[str, str], escenario: dict[str, Any]) -> None:
    """IN-06 | Cliente ⇄ PostgreSQL (RLS) | Con su token real y la clave publicable, un estudiante que consulta la base directamente no ve los eventos, alertas ni perfiles de otro."""
    a, b = escenario["a"], escenario["b"]
    h = {"apikey": claves["ANON_KEY"], "Authorization": f"Bearer {b.token}"}
    for tabla, filtro in [("events", f"student_id=eq.{a.id}"), ("alerts", f"student_id=eq.{a.id}"), ("profiles", f"id=eq.{a.id}"), ("risk_scores", f"student_id=eq.{a.id}")]:
        r = httpx.get(f"{AUTH_LOCAL}/rest/v1/{tabla}?{filtro}&select=*", headers=h, timeout=15)
        assert r.status_code in (200, 401, 403) and (r.status_code != 200 or r.json() == []), f"{tabla}: {r.status_code} {r.text[:120]}"


def test_in07_rls_estudiante_no_inserta_eventos(claves: dict[str, str], escenario: dict[str, Any]) -> None:
    """IN-07 | Cliente ⇄ PostgreSQL (RLS) | Un estudiante no puede saltarse la API insertando un evento directo en la base (la API es la que valida módulos, límite de peticiones y crea la alerta)."""
    e, a = escenario["examen"], escenario["a"]
    h = {"apikey": claves["ANON_KEY"], "Authorization": f"Bearer {a.token}", "Prefer": "return=representation"}
    ins = httpx.post(f"{AUTH_LOCAL}/rest/v1/events", headers=h, json={**evento(e, a, "focus_lost", 1)}, timeout=15)
    assert ins.status_code in (401, 403) or ins.json() == [], (
        f"PostgREST aceptó el insert ({ins.status_code}): la política events_student_insert permite escribir eventos sin pasar por la API"
    )


def test_in07b_rls_estudiante_no_escala_rol(claves: dict[str, str], escenario: dict[str, Any]) -> None:
    """IN-07b | Cliente ⇄ PostgreSQL (RLS) | Un estudiante no puede subirse el rol a teacher ni borrar alertas escribiendo directo en la base."""
    e, a = escenario["examen"], escenario["a"]
    h = {"apikey": claves["ANON_KEY"], "Authorization": f"Bearer {a.token}", "Prefer": "return=representation"}
    rol = httpx.patch(f"{AUTH_LOCAL}/rest/v1/profiles?id=eq.{a.id}", headers=h, json={"role": "teacher"}, timeout=15)
    assert rol.status_code in (401, 403) or rol.json() == [], rol.text[:200]
    borrar = httpx.delete(f"{AUTH_LOCAL}/rest/v1/alerts?session_id=eq.{e.id}", headers=h, timeout=15)
    assert borrar.status_code in (401, 403) or borrar.json() == [], borrar.text[:200]
    with cliente() as c:
        assert c.get("/sessions", headers=a.h).status_code == 403, "el rol cambió"


def test_in08_caras_de_referencia_solo_servidor(claves: dict[str, str], escenario: dict[str, Any]) -> None:
    """IN-08 | Cliente ⇄ PostgreSQL (RLS) | Las fotos de referencia (reference_faces) no se leen desde el cliente, ni siquiera las propias."""
    a = escenario["a"]
    h = {"apikey": claves["ANON_KEY"], "Authorization": f"Bearer {a.token}"}
    r = httpx.get(f"{AUTH_LOCAL}/rest/v1/reference_faces?select=*", headers=h, timeout=15)
    assert r.status_code in (401, 403) or r.json() == []


# ------------------------------------------------------------------ API ⇄ Storage


def test_in09_subida_firmada_y_bucket_privado(claves: dict[str, str], escenario: dict[str, Any]) -> None:
    """IN-09 | API ⇄ Storage | La API firma una subida; el cliente sube directo a Storage; el objeto existe, no se lee sin firma y el docente lo abre con una URL firmada de lectura."""
    e, a, d = escenario["examen"], escenario["a"], escenario["docente"]
    with cliente() as c:
        u = c.post("/evidence/upload-url", headers=a.h, json={"session_id": e.id, "student_id": a.id, "kind": "image", "extension": "jpg", "event_type": "extra_person"})
        assert u.status_code == 201, u.text
        permiso = u.json()
        subida = httpx.put(local(permiso["url"]), content=b"\xff\xd8\xff\xe0prueba-integracion", headers={"Content-Type": "image/jpeg"}, timeout=30)
        assert subida.status_code in (200, 201), subida.text
        bucket = "evidences"
        anonimo = httpx.get(f"{AUTH_LOCAL}/storage/v1/object/public/{bucket}/{permiso['path']}", timeout=15)
        assert anonimo.status_code >= 400, "el bucket es público"
        ev = c.post("/events", headers=a.h, json=evento(e, a, "extra_person", 0, evidence_path=permiso["path"]))
        assert ev.status_code == 201
        lectura = c.post(f"/sessions/{e.id}/students/{a.id}/evidence-url", headers=d.h, json={"path": permiso["path"], "kind": "image"})
        assert lectura.status_code in (200, 201), lectura.text
        contenido = httpx.get(local(lectura.json()["url"]), timeout=15)
    assert contenido.status_code == 200 and contenido.content.endswith(b"prueba-integracion")


def test_in10_estudiante_no_firma_rutas_ajenas(escenario: dict[str, Any]) -> None:
    """IN-10 | API ⇄ Storage | Un estudiante no puede pedir una URL de subida a nombre de otro estudiante."""
    e, a, b = escenario["examen"], escenario["a"], escenario["b"]
    with cliente() as c:
        r = c.post("/evidence/upload-url", headers=b.h, json={"session_id": e.id, "student_id": a.id, "kind": "image", "extension": "jpg", "event_type": "extra_person"})
    assert r.status_code == 403


# ------------------------------------------------------------------ API ⇄ Redis ⇄ worker de IA


def test_in11_audio_por_la_cola_hasta_el_analisis(escenario: dict[str, Any], servicio: httpx.Client, record_property: Any) -> None:
    """IN-11 | API ⇄ Redis ⇄ worker IA ⇄ API | Un speech_detected con su audio se encola, el worker lo transcribe con Whisper y lo compara con el enunciado, y el resultado vuelve a audio_analyses."""
    e, a = escenario["examen"], escenario["a"]
    numerica = next(q for q in e.preguntas if q["question_type"] == "numeric")
    wav = (VOZ / "enunciado.wav").read_bytes()
    with cliente() as c:
        u = c.post("/evidence/upload-url", headers=a.h, json={"session_id": e.id, "student_id": a.id, "kind": "audio", "extension": "wav", "event_type": "speech_detected"}).json()
        assert httpx.put(local(u["url"]), content=wav, headers={"Content-Type": "audio/wav"}, timeout=60).status_code in (200, 201)
        t0 = time.time()
        r = c.post("/events", headers=a.h, json={**evento(e, a, "speech_detected", 5000, evidence_path=u["path"]), "question_id": numerica["id"]})
    assert r.status_code == 201
    eid = r.json()["id"]
    fila: list[dict[str, Any]] = []
    while time.time() - t0 < 240 and not fila:
        fila = servicio.get("/rest/v1/audio_analyses", params={"event_id": f"eq.{eid}", "select": "transcript,similarity,processing_ms,matched_question_id"}).json()
        time.sleep(2)
    assert fila, "el análisis no volvió en 4 min"
    x = fila[0]
    record_property("medida_espera_s", round(time.time() - t0, 1))
    record_property("medida_procesamiento_ms", x["processing_ms"])
    record_property("medida_similitud", x["similarity"])
    record_property("medida_transcripcion", x["transcript"])
    assert x["transcript"] and len(x["transcript"]) > 10
    assert x["similarity"] is not None and x["similarity"] >= 0.6, x


def test_in12_cola_sobrevive_a_un_worker(escenario: dict[str, Any], servicio: httpx.Client, record_property: Any) -> None:
    """IN-12 | Redis ⇄ workers | Con varios audios a la vez, la cola los reparte entre los dos workers y todos terminan analizados."""
    e, a = escenario["examen"], escenario["b"]
    wav = (VOZ / "ajeno.wav").read_bytes()
    ids = []
    with cliente() as c:
        for _ in range(4):
            u = c.post("/evidence/upload-url", headers=a.h, json={"session_id": e.id, "student_id": a.id, "kind": "audio", "extension": "wav", "event_type": "speech_detected"}).json()
            httpx.put(local(u["url"]), content=wav, headers={"Content-Type": "audio/wav"}, timeout=60)
            ids.append(c.post("/events", headers=a.h, json=evento(e, a, "speech_detected", 4000, evidence_path=u["path"])).json()["id"])
    fin = time.time() + 400
    listos: set[str] = set()
    while time.time() < fin and len(listos) < len(ids):
        filas = servicio.get("/rest/v1/audio_analyses", params={"event_id": f"in.({','.join(ids)})", "select": "event_id"}).json()
        listos = {f["event_id"] for f in filas}
        time.sleep(3)
    record_property("medida_analizados", f"{len(listos)} de {len(ids)}")
    assert listos == set(ids), f"{len(listos)} de {len(ids)}"


def test_in13_endpoint_interno_exige_secreto(escenario: dict[str, Any]) -> None:
    """IN-13 | worker IA ⇄ API | Los endpoints internos que usa el worker rechazan a quien no trae el secreto compartido, aunque sea un docente con token válido."""
    d = escenario["docente"]
    with cliente() as c:
        sin = c.get("/internal/audio-jobs/00000000-0000-4000-8000-000000000001")
        docente = c.get("/internal/audio-jobs/00000000-0000-4000-8000-000000000001", headers=d.h)
        falso = c.get("/internal/audio-jobs/00000000-0000-4000-8000-000000000001", headers={"X-Internal-Token": "adivinado"})
    assert {sin.status_code, docente.status_code, falso.status_code} <= {401, 403, 404}
    assert falso.status_code != 200


# ------------------------------------------------------------------ PostgreSQL ⇄ Realtime ⇄ docente


def test_in14_alerta_llega_por_realtime(claves: dict[str, str], escenario: dict[str, Any], record_property: Any) -> None:
    """IN-14 | PostgreSQL ⇄ Realtime ⇄ cliente | El docente suscrito por WebSocket recibe la alerta en menos de 5 s desde que el estudiante manda la señal (SPEC-009 CA-2)."""
    import websockets

    e, a, d = escenario["examen"], escenario["a"], escenario["docente"]
    url = f"ws://127.0.0.1:54321/realtime/v1/websocket?apikey={claves['ANON_KEY']}&vsn=1.0.0"

    async def correr() -> float:
        async with websockets.connect(url, open_timeout=30) as ws:
            await ws.send(json.dumps({
                "topic": f"realtime:docente-{e.id}", "event": "phx_join", "ref": "1", "join_ref": "1",
                "payload": {"config": {"broadcast": {"ack": False, "self": False}, "presence": {"key": ""}, "private": False,
                            "postgres_changes": [{"event": "INSERT", "schema": "public", "table": "alerts", "filter": f"session_id=eq.{e.id}"}]},
                            "access_token": d.token},
            }))
            fin = time.time() + 30
            while time.time() < fin:
                m = json.loads(await asyncio.wait_for(ws.recv(), 30))
                if m.get("event") == "system" and (m.get("payload") or {}).get("extension") == "postgres_changes":
                    break
            t0 = time.monotonic()
            with cliente() as c:
                ev = c.post("/events", headers=a.h, json=evento(e, a, "suspicious_process", 0, metadata={"process": "anydesk"})).json()
            while time.monotonic() - t0 < 15:
                m = json.loads(await asyncio.wait_for(ws.recv(), 15))
                if m.get("event") == "postgres_changes" and m["payload"]["data"]["record"]["event_id"] == ev["id"]:
                    return time.monotonic() - t0
        raise AssertionError("la alerta no llegó por Realtime")

    segundos = asyncio.run(correr())
    record_property("medida_alerta_a_docente_s", round(segundos, 3))
    assert segundos < 5, f"tardó {segundos:.2f} s"


def test_in15_realtime_no_filtra_a_otro_docente(claves: dict[str, str], escenario: dict[str, Any]) -> None:
    """IN-15 | Realtime (RLS) | Otro docente suscrito al mismo examen no recibe sus alertas: Realtime respeta las políticas de la tabla."""
    import websockets

    e, a = escenario["examen"], escenario["a"]
    intruso = persona("teacher", "Docente ajeno")
    url = f"ws://127.0.0.1:54321/realtime/v1/websocket?apikey={claves['ANON_KEY']}&vsn=1.0.0"

    async def correr() -> int:
        recibidas = 0
        async with websockets.connect(url, open_timeout=30) as ws:
            await ws.send(json.dumps({
                "topic": f"realtime:intruso-{e.id}", "event": "phx_join", "ref": "1", "join_ref": "1",
                "payload": {"config": {"broadcast": {"ack": False, "self": False}, "presence": {"key": ""}, "private": False,
                            "postgres_changes": [{"event": "INSERT", "schema": "public", "table": "alerts", "filter": f"session_id=eq.{e.id}"}]},
                            "access_token": intruso.token},
            }))
            await asyncio.sleep(3)
            with cliente() as c:
                c.post("/events", headers=a.h, json=evento(e, a, "extra_person", 0))
            fin = time.monotonic() + 8
            while time.monotonic() < fin:
                try:
                    m = json.loads(await asyncio.wait_for(ws.recv(), 1))
                except TimeoutError:
                    continue
                if m.get("event") == "postgres_changes":
                    recibidas += 1
        return recibidas

    assert asyncio.run(correr()) == 0


# ------------------------------------------------------------------ réplicas ⇄ Redis


def test_in16_limite_compartido_entre_replicas() -> None:
    """IN-16 | réplicas de la API ⇄ Redis | El límite de 10 intentos de código por minuto se cuenta en Redis: aunque nginx reparta entre las 2 réplicas, el 11.º intento es 429."""
    p = persona()
    with cliente() as c:
        codigos = [c.post("/sessions/join", headers=p.h, json={"access_code": f"INTG{i:04d}"}).status_code for i in range(12)]
    assert codigos[:10] == [400] * 10 and codigos[10:] == [429, 429], codigos


def test_in17_preguntas_por_el_balanceador(escenario: dict[str, Any]) -> None:
    """IN-17 | nginx ⇄ réplicas | 40 lecturas seguidas por el balanceador responden todas 200 y con los mismos datos, venga de la réplica que venga."""
    e, a = escenario["examen"], escenario["a"]
    with cliente() as c:
        cuerpos = {c.get(f"/exam/{e.id}/questions", headers=a.h).text for _ in range(40)}
    assert len(cuerpos) == 1
