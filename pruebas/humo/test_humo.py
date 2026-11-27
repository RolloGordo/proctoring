"""Pruebas de humo de producción (27/11/2026).

Lo mínimo que tiene que ser verdad para que valga la pena probar cualquier otra
cosa, o para dar por bueno un despliegue: que cada pieza está arriba y responde
como debe. **Solo lectura**: no inicia sesión, no crea cuentas ni datos. Corre en
un par de minutos y es lo que se repite después de cada despliegue.

    uv run --no-project --with pytest --with httpx --with websockets --with playwright \\
        python -m pytest pruebas/humo

Las comprobaciones del servidor (réplicas, autoescalador, worker y Redis) entran
por SSH y solo leen estados; nunca imprimen variables ni secretos.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import ssl
import subprocess
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

DOMINIOS = [
    ("proctoring-upao.me", "api.proctoring-upao.me"),
    ("proctoring-upao.app", "api.proctoring-upao.app"),
    ("web.86-48-18-81.sslip.io", "api.86-48-18-81.sslip.io"),
]
SUPABASE = "https://uzuysjmymvtpoxfrdxnm.supabase.co"
SSH = ["ssh", "-n", "-o", "BatchMode=yes", "-i", os.path.expanduser("~/.ssh/contabo_proctoring"), "ubuntu@86.48.18.81"]


def ssh(cmd: str) -> str:
    return subprocess.run([*SSH, cmd], capture_output=True, text=True, timeout=60, check=False).stdout


@pytest.fixture(scope="module")
def clave_publicable() -> str:
    """La clave publicable de Supabase va horneada en la web (es pública por diseño)."""
    html = httpx.get(f"https://{DOMINIOS[0][0]}/", timeout=20).text
    js = next(x for x in html.split('"') if x.startswith("/assets/index-") and x.endswith(".js"))
    cuerpo = httpx.get(f"https://{DOMINIOS[0][0]}{js}", timeout=30).text
    import re

    m = re.search(r"sb_publishable_[A-Za-z0-9_-]+", cuerpo) or re.search(r"eyJhbGciOi[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", cuerpo)
    assert m, "no se encontró la clave publicable en el bundle"
    return m.group(0)


# ------------------------------------------------------------------ web


@pytest.mark.parametrize(("web", "api"), DOMINIOS)
def test_hu01_web_responde(web: str, api: str, record_property: Any) -> None:
    """HU-01 | Web | Cada dominio sirve la web (200, HTML de la aplicación) en menos de 3 s."""
    r = httpx.get(f"https://{web}/", timeout=20)
    record_property(f"medida_{web}_ms", round(r.elapsed.total_seconds() * 1000))
    assert r.status_code == 200 and '<div id="root">' in r.text
    assert r.elapsed.total_seconds() < 3


@pytest.mark.parametrize(("web", "api"), DOMINIOS[:2])
def test_hu02_assets(web: str, api: str) -> None:
    """HU-02 | Web | Los JS y CSS del índice cargan con su tipo MIME correcto y caché larga."""
    html = httpx.get(f"https://{web}/", timeout=20).text
    assets = [x for x in html.split('"') if x.startswith("/assets/")]
    assert assets
    for a in assets:
        r = httpx.get(f"https://{web}{a}", timeout=30)
        assert r.status_code == 200, a
        tipo = r.headers["content-type"]
        assert ("javascript" in tipo) if a.endswith(".js") else ("css" in tipo) if a.endswith(".css") else True
        assert "max-age=31536000" in r.headers.get("cache-control", "")


@pytest.mark.parametrize(("web", "api"), DOMINIOS[:2])
def test_hu03_ruta_spa(web: str, api: str) -> None:
    """HU-03 | Web | Una ruta interna (/login) devuelve la aplicación, y un archivo oculto (/.env) devuelve 404."""
    assert httpx.get(f"https://{web}/login", timeout=20).status_code == 200
    assert httpx.get(f"https://{web}/.env", timeout=20).status_code == 404


# ------------------------------------------------------------------ API


@pytest.mark.parametrize(("web", "api"), DOMINIOS)
def test_hu04_api_salud(web: str, api: str, record_property: Any) -> None:
    """HU-04 | API | /health responde ok, en producción y con la autenticación activada."""
    r = httpx.get(f"https://{api}/health", timeout=20)
    record_property(f"medida_{api}_ms", round(r.elapsed.total_seconds() * 1000))
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["env"] == "production" and r.json()["auth"] == "enabled"


@pytest.mark.parametrize(("web", "api"), DOMINIOS)
def test_hu05_cors(web: str, api: str) -> None:
    """HU-05 | API | El preflight de CORS autoriza a la web de su dominio."""
    r = httpx.options(
        f"https://{api}/api/v1/events",
        headers={"Origin": f"https://{web}", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"},
        timeout=20,
    )
    assert r.headers.get("access-control-allow-origin") == f"https://{web}"


@pytest.mark.parametrize(("web", "api"), DOMINIOS[:2])
def test_hu06_protegido_sin_token(web: str, api: str) -> None:
    """HU-06 | API | Un endpoint protegido sin token responde 401 (la autenticación está puesta)."""
    assert httpx.get(f"https://{api}/api/v1/sessions", timeout=20).status_code == 401


# ------------------------------------------------------------------ TLS y cabeceras


@pytest.mark.parametrize("host", [h for par in DOMINIOS for h in par])
def test_hu07_certificado(host: str, record_property: Any) -> None:
    """HU-07 | TLS | El certificado es válido para el dominio y le quedan más de 14 días."""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=15) as s, ctx.wrap_socket(s, server_hostname=host) as t:
        cert = t.getpeercert()
        version = t.version()
    vence = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)
    dias = (vence - datetime.now(UTC)).days
    record_property(f"medida_{host}_dias", dias)
    assert dias > 14 and version in ("TLSv1.2", "TLSv1.3")


@pytest.mark.parametrize(("web", "api"), DOMINIOS[:2])
def test_hu08_http_a_https_y_hsts(web: str, api: str) -> None:
    """HU-08 | TLS | HTTP redirige a HTTPS y la respuesta trae HSTS de un año y nosniff."""
    r = httpx.get(f"http://{web}/", timeout=20, follow_redirects=False)
    assert r.status_code in (301, 308) and r.headers["location"].startswith("https://")
    h = httpx.get(f"https://{web}/", timeout=20).headers
    assert "max-age=31536000" in h.get("strict-transport-security", "")
    assert h.get("x-content-type-options") == "nosniff"
    assert "frame-ancestors 'none'" in h.get("content-security-policy", "")


# ------------------------------------------------------------------ Supabase


def test_hu09_supabase_auth(clave_publicable: str) -> None:
    """HU-09 | Supabase | Auth responde (el proyecto no está pausado)."""
    r = httpx.get(f"{SUPABASE}/auth/v1/health", headers={"apikey": clave_publicable}, timeout=20)
    assert r.status_code == 200, r.text[:200]


def test_hu10_supabase_rest_rls(clave_publicable: str) -> None:
    """HU-10 | Supabase | La base responde y, sin sesión, RLS no deja leer ningún evento."""
    r = httpx.get(f"{SUPABASE}/rest/v1/events?select=id&limit=1", headers={"apikey": clave_publicable}, timeout=20)
    assert r.status_code in (200, 401) and (r.status_code == 401 or r.json() == [])


def test_hu11_supabase_realtime(clave_publicable: str) -> None:
    """HU-11 | Supabase | Realtime acepta una conexión WebSocket y la unión a un canal."""
    import websockets

    async def unir() -> str:
        url = f"wss://uzuysjmymvtpoxfrdxnm.supabase.co/realtime/v1/websocket?apikey={clave_publicable}&vsn=1.0.0"
        async with websockets.connect(url, open_timeout=20) as ws:
            await ws.send(json.dumps({"topic": "realtime:humo", "event": "phx_join", "payload": {"config": {}}, "ref": "1"}))
            m = json.loads(await asyncio.wait_for(ws.recv(), 15))
            return (m.get("payload") or {}).get("status", "")

    assert asyncio.run(unir()) == "ok"


# ------------------------------------------------------------------ servidor


def test_hu12_replicas() -> None:
    """HU-12 | Servidor | Todos los servicios de Swarm tienen corriendo las réplicas que piden."""
    filas = [l.split() for l in ssh("docker service ls --format '{{.Name}} {{.Replicas}}'").splitlines() if l.strip()]
    assert filas
    for nombre, rep in filas:
        corriendo, piden = rep.split("/")[:2]
        assert corriendo == piden.split()[0] and int(corriendo) > 0, f"{nombre}: {rep}"


def test_hu13_autoescalador() -> None:
    """HU-13 | Servidor | El autoescalador está activo, habilitado al arranque y midiendo (última medición de hace menos de 1 min)."""
    salida = ssh("systemctl is-active proctoring-autoescalado; systemctl is-enabled proctoring-autoescalado; tail -1 /home/ubuntu/autoescalado/produccion.csv").splitlines()
    assert salida[:2] == ["active", "enabled"]
    hora = datetime.fromisoformat(salida[2].split(",")[0])
    assert (datetime.now(UTC) - hora).total_seconds() < 60


def test_hu14_worker_ia_y_redis() -> None:
    """HU-14 | Servidor | Cada worker de IA responde su salud, que incluye la conexión a Redis (503 si la pierde)."""
    salida = ssh(
        "for c in $(docker ps -q -f name=ai-worker-rrcohr); do docker exec $c python -c "
        "\"import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=5).status)\"; done"
    ).split()
    assert salida and all(s == "200" for s in salida), salida


def test_hu15_recursos() -> None:
    """HU-15 | Servidor | El disco tiene más de 20 % libre y la memoria disponible pasa de 2 GB."""
    disco = int(ssh("df --output=pcent / | tail -1").strip().rstrip("%"))
    mem = int(ssh("free -m | awk '/Mem:/{print $7}'").strip())
    assert disco < 80 and mem > 2048, (disco, mem)


def test_hu16_puertos_cerrados() -> None:
    """HU-16 | Red | Desde fuera, el panel de Dokploy (3000), Redis (6379) y la API directa (8000) no responden."""
    for puerto in (3000, 6379, 8000, 5432):
        with socket.socket() as s:
            s.settimeout(4)
            assert s.connect_ex(("86.48.18.81", puerto)) != 0, f"puerto {puerto} abierto"


# ------------------------------------------------------------------ distribución y navegador


def test_hu17_instalador_publicado() -> None:
    """HU-17 | Distribución | La última versión publicada de la app de escritorio es la 1.1.4 y su instalador se puede descargar."""
    rel = httpx.get("https://api.github.com/repos/RolloGordo/proctoring/releases/latest", timeout=20).json()
    assert rel["tag_name"] == "v1.1.4"
    exe = next(a for a in rel["assets"] if a["name"].endswith(".exe"))
    r = httpx.head(exe["browser_download_url"], timeout=20, follow_redirects=True)
    assert r.status_code == 200 and int(r.headers.get("content-length", 0)) > 50_000_000


def test_hu18_navegador_real(record_property: Any) -> None:
    """HU-18 | Navegador | Chrome abre el login de proctoring-upao.me sin errores de consola, con crossOriginIsolated (lo exige el detector de voz) y la API de su dominio."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome")
        p = b.new_page()
        errores: list[str] = []
        p.on("console", lambda m: m.type == "error" and errores.append(m.text))
        llamadas: list[str] = []
        p.on("request", lambda r: "/api/v1/" in r.url or "/health" in r.url and llamadas.append(r.url))
        p.goto("https://proctoring-upao.me/login", wait_until="networkidle")
        assert p.locator('input[type="email"]').is_visible()
        aislado = p.evaluate("crossOriginIsolated")
        api = p.evaluate("fetch('https://api.proctoring-upao.me/health').then(r => r.status)")
        ruta = os.environ.get("CAPTURAS")
        if ruta:
            p.screenshot(path=os.path.join(ruta, "hu18-login-me.png"))
            record_property("evidencia", os.path.join(ruta, "hu18-login-me.png"))
        b.close()
    assert aislado is True and api == 200
    assert not errores, errores
