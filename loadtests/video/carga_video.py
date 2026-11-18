"""Carga con video: navegadores reales con una cámara grabada (pedido del 14/11/2026).

Locust mide la API, pero no lo que pasa cuando de verdad hay video: los
detectores corren en el navegador de cada estudiante (MediaPipe y el VAD) y lo
que llega al servidor son las señales, las capturas y, con el módulo
`live_monitoring`, los fotogramas que el docente ve en vivo por Supabase
Realtime. Para medir eso hacen falta navegadores de verdad viendo un video.

Cómo se arma:

- **Una grabación con anomalías** (`--video`, `.y4m`): alguien frente a la
  cámara que sale del cuadro, mira a un lado, deja entrar a otra persona, saca
  un celular. Chromium la usa como cámara (`--use-file-for-fake-video-capture`)
  y la repite en bucle. Sin `--video` usa la cámara de prueba de Chromium (sin
  rostro), que solo produce «rostro ausente». Con `--audio` (`.wav`) también
  hay voz.
- **N estudiantes**, cada uno en su contexto de Chromium: inicia sesión en la
  web, se matricula, el docente lo admite y entra a rendir. Desde ahí la
  supervisión es la de cualquier estudiante: nada está simulado.
- **Un docente** con la pestaña Actividad abierta, que es la que monta las
  cámaras en vivo y por tanto hace que los estudiantes transmitan.

Al final se mide, del lado del servidor, qué señales llegaron y cuánto tardó
cada alerta desde que terminó la detección, y del lado del navegador, cuánto
tardó cada `POST /events` y cuántos fotogramas por segundo vio el docente.

Corre contra el entorno de carga aislado (`docker-compose.carga.yml` y Supabase
local), nunca contra producción: las cuentas y contraseñas son las de
`preparar.py`.

    uv run --with playwright python video/carga_video.py --estudiantes 10 --minutos 4 \\
        --video video/anomalias.y4m --audio video/voz.wav
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from playwright.async_api import Browser, Page, async_playwright

AQUI = Path(__file__).resolve().parent
ESCENARIO = AQUI.parent / ".datos" / "escenario.json"
sys.path.insert(0, str(AQUI.parent))
from preparar import CONTRASENA  # noqa: E402

WEB = "http://localhost:5173"
API = "http://localhost:8080/api/v1"

#: Los módulos de cámara y voz, y la transmisión en vivo al docente.
MODULOS: dict[str, dict[str, Any]] = {
    "gaze": {},
    "extra_person": {},
    "objects": {},
    "external_voices": {},
    "live_monitoring": {},
}

#: La web solo comprueba que exista `window.api` para dejar rendir fuera de
#: Electron. El servidor no se fía de eso: matrícula y admisión se exigen igual.
STUB_ESCRITORIO = "window.api = { setAuthSession: async () => {} };"


#: La API del entorno de carga firma con el nombre interno de Docker, que el
#: navegador no alcanza. Solo pasa en este entorno: en producción es HTTPS.
KONG_INTERNO = "http://supabase_kong_proctoring:8000"
KONG_LOCAL = "http://localhost:54321"


async def reescribir_url_firmada(route: Any) -> None:
    respuesta = await route.fetch()
    cuerpo = (await respuesta.text()).replace(KONG_INTERNO, KONG_LOCAL)
    await route.fulfill(response=respuesta, body=cuerpo)


def ahora_iso() -> str:
    return datetime.now(UTC).isoformat()


async def iniciar_sesion(page: Page, correo: str) -> None:
    await page.goto(f"{WEB}/login")
    await page.locator('input[type="email"]').fill(correo)
    await page.locator('input[type="password"]').fill(CONTRASENA)
    await page.get_by_role("button", name="Entrar").click()
    await page.wait_for_url(lambda url: "/login" not in url, timeout=30_000)


class Estudiante:
    def __init__(self, n: int, examen: dict[str, Any], persona: dict[str, Any]) -> None:
        self.n = n
        self.sid = examen["id"]
        self.codigo = examen["codigo"]
        self.yo = persona
        self.posts: list[tuple[float, int]] = []  # (ms, estado)
        self.errores: list[str] = []
        self.listo = False

    async def correr(self, browser: Browser, docente: httpx.AsyncClient, hasta: float) -> None:
        contexto = await browser.new_context(
            permissions=["camera", "microphone"], viewport={"width": 1280, "height": 800}
        )
        await contexto.add_init_script(STUB_ESCRITORIO)
        page = await contexto.new_page()
        page.on("console", lambda m: m.type == "error" and self.errores.append(m.text[:200]))

        enviados: dict[Any, float] = {}

        def al_pedir(peticion: Any) -> None:
            if peticion.url.endswith("/api/v1/events") and peticion.method == "POST":
                enviados[peticion] = time.monotonic()

        def al_responder(respuesta: Any) -> None:
            inicio = enviados.pop(respuesta.request, None)
            if inicio is not None:
                self.posts.append(((time.monotonic() - inicio) * 1000, respuesta.status))

        page.on("request", al_pedir)
        page.on("response", al_responder)
        await page.route("**/api/v1/evidence/upload-url", reescribir_url_firmada)
        try:
            await iniciar_sesion(page, self.yo["email"])
            h = {"Authorization": f"Bearer {self.yo['token']}"}
            async with httpx.AsyncClient(base_url=API, headers=h, timeout=30) as yo:
                (await yo.post("/sessions/join", json={"access_code": self.codigo})).raise_for_status()
                r = await yo.post(f"/exam/{self.sid}/enroll", json={"accepts_supervision": True})
                if r.status_code not in (200, 201, 400):
                    r.raise_for_status()
            (
                await docente.post(
                    f"/sessions/{self.sid}/participants/{self.yo['id']}/identity",
                    json={"approve": True},
                )
            ).raise_for_status()
            await page.goto(f"{WEB}/examen/{self.sid}/rendir")
            await page.get_by_text("Pregunta 1 de").first.wait_for(timeout=60_000)
            self.listo = True
            while time.time() < hasta:
                await asyncio.sleep(5)
        except Exception as fallo:  # noqa: BLE001 - se informa, no se detiene la prueba
            self.errores.append(f"flujo: {type(fallo).__name__}: {str(fallo)[:200]}")
        finally:
            await contexto.close()


async def docente_mirando(
    browser: Browser, examen: dict[str, Any], hasta: float, fps: list[float]
) -> None:
    """El docente en Actividad: monta las cámaras y lee los fps que recibe."""
    contexto = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await contexto.new_page()
    try:
        await iniciar_sesion(page, examen["docente_email"])
        await page.goto(f"{WEB}/sesiones/{examen['id']}?vista=actividad")
        while time.time() < hasta:
            await asyncio.sleep(10)
            texto = await page.locator("body").inner_text()
            # CamaraEnVivo escribe «… · N FPS recibidos» bajo cada cámara.
            for valor in re.findall(r"(\d+(?:[.,]\d+)?) FPS recibidos", texto, re.IGNORECASE):
                fps.append(float(valor.replace(",", ".")))
        await page.screenshot(path=str(AQUI.parent / "resultados" / "video-docente.png"), full_page=True)
    finally:
        await contexto.close()


def percentil(valores: list[float], p: float) -> float:
    if not valores:
        return float("nan")
    orden = sorted(valores)
    return orden[min(len(orden) - 1, int(p * len(orden)))]


async def main() -> int:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    a.add_argument("--estudiantes", type=int, default=10)
    a.add_argument("--minutos", type=float, default=4)
    a.add_argument("--video", type=Path, help=".y4m con la grabación (sin él: cámara de prueba)")
    a.add_argument("--audio", type=Path, help=".wav con voz")
    a.add_argument("--entrada-por-segundo", type=float, default=1.0)
    a.add_argument("--salida", type=Path, default=AQUI.parent / "resultados" / "video.json")
    args = a.parse_args()

    examen = json.loads(ESCENARIO.read_text(encoding="utf-8"))["examenes"][0]
    personas = examen["estudiantes"][: args.estudiantes]
    hd = {"Authorization": f"Bearer {examen['docente_token']}"}

    async with httpx.AsyncClient(base_url=API, headers=hd, timeout=30) as docente:
        r = await docente.patch(
            f"/sessions/{examen['id']}", json={"preset": "custom", "modules": MODULOS}
        )
        r.raise_for_status()

        banderas = [
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            "--autoplay-policy=no-user-gesture-required",
        ]
        if args.video:
            banderas.append(f"--use-file-for-fake-video-capture={args.video.resolve()}")
        if args.audio:
            banderas.append(f"--use-file-for-fake-audio-capture={args.audio.resolve()}")

        inicio = time.time()
        llegada = len(personas) / args.entrada_por_segundo
        hasta = inicio + llegada + args.minutos * 60
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, args=banderas)
            estudiantes = [Estudiante(i, examen, p) for i, p in enumerate(personas)]
            fps: list[float] = []
            tareas = [asyncio.create_task(docente_mirando(browser, examen, hasta, fps))]
            for e in estudiantes:
                tareas.append(asyncio.create_task(e.correr(browser, docente, hasta)))
                await asyncio.sleep(1 / args.entrada_por_segundo)
            await asyncio.gather(*tareas, return_exceptions=True)
            await browser.close()

        eventos = (await docente.get(f"/sessions/{examen['id']}/events")).json()
        alertas = (await docente.get(f"/sessions/{examen['id']}/alerts")).json()

    por_tipo: dict[str, int] = {}
    for ev in eventos:
        por_tipo[ev["event_type"]] = por_tipo.get(ev["event_type"], 0) + 1
    fin_de = {
        ev["id"]: datetime.fromisoformat(ev["started_at"]).timestamp() + ev["duration_ms"] / 1000
        for ev in eventos
    }
    # Desde que el detector cerró la señal hasta que la alerta quedó guardada:
    # incluye el envío, la cola de la app y la API. Realtime la empuja al docente
    # en cuanto se inserta.
    demoras = [
        (datetime.fromisoformat(al["created_at"]).timestamp() - fin_de[al["event_id"]]) * 1000
        for al in alertas
        if al["event_id"] in fin_de
    ]
    posts = [ms for e in estudiantes for ms, _ in e.posts]
    estados = [st for e in estudiantes for _, st in e.posts]
    resumen = {
        "fecha": ahora_iso(),
        "estudiantes": len(estudiantes),
        "entraron": sum(e.listo for e in estudiantes),
        "minutos": args.minutos,
        "video": str(args.video) if args.video else "cámara de prueba de Chromium",
        "audio": str(args.audio) if args.audio else None,
        "senales_por_tipo": por_tipo,
        "senales": len(eventos),
        "alertas": len(alertas),
        "post_events": {
            "n": len(posts),
            "errores": sum(1 for s in estados if s >= 400),
            "p50_ms": percentil(posts, 0.5),
            "p95_ms": percentil(posts, 0.95),
        },
        "deteccion_a_alerta_ms": {
            "n": len(demoras),
            "p50": percentil(demoras, 0.5),
            "p95": percentil(demoras, 0.95),
            "max": max(demoras) if demoras else None,
        },
        "fps_docente": {
            "muestras": len(fps),
            "media": statistics.fmean(fps) if fps else None,
            "min": min(fps) if fps else None,
        },
        "errores_navegador": sorted({x for e in estudiantes for x in e.errores})[:20],
    }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    return 0 if resumen["entraron"] == len(estudiantes) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
