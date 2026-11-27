"""Pruebas de extremo a extremo (E2E) en un navegador real (27/11/2026).

Un docente y un estudiante, cada uno en su Chromium, recorren el producto por la
interfaz como lo haría una persona: inician sesión, el docente arma el examen en el
editor, el estudiante entra con el código y acepta la supervisión, el docente lo
admite, el estudiante rinde y entrega, y el docente revisa el caso y decide.

Corre contra el entorno aislado (web en :5173, API en :8080, Supabase local), con
la cámara de prueba de Chromium. Las pruebas van **en orden** y comparten estado:
cada una es un paso del mismo examen. Cada paso deja una captura en `CAPTURAS`.

Lo que un navegador no puede hacer queda fuera, y se dice: la comprobación del
encuadre y la verificación facial necesitan un rostro real frente a la cámara, así
que el estudiante pasa por la admisión manual del docente (el camino que el producto
prevé cuando la cámara no lo reconoce) y entra directo a rendir. La pérdida de foco,
los monitores y los procesos los detecta Electron: van en `test_e2e_escritorio.py`.
"""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from playwright.sync_api import Browser, BrowserContext, Page, expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from comun import V1, cliente, persona  # noqa: E402
from preparar import CONTRASENA  # noqa: E402

WEB = os.environ.get("WEB_URL", "http://localhost:5173")
CAPTURAS = Path(os.environ.get("CAPTURAS", "capturas-e2e"))
CAPTURAS.mkdir(parents=True, exist_ok=True)
STUB_ESCRITORIO = "window.api = { setAuthSession: async () => {} };"
KONG_INTERNO = "http://supabase_kong_proctoring:8000"
KONG_LOCAL = "http://localhost:54321"

estado: dict[str, Any] = {}


def captura(page: Page, nombre: str, record: Any) -> None:
    ruta = CAPTURAS / f"{nombre}.png"
    page.screenshot(path=str(ruta), full_page=False)
    record("evidencia", str(ruta))


@pytest.fixture(scope="module")
def navegador() -> Browser:
    with sync_playwright() as pw:
        b = pw.chromium.launch(
            args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]
        )
        yield b
        b.close()


def _reescribir(route: Any) -> None:
    # Solo en este entorno: la URL firmada sale con el nombre interno de Docker.
    r = route.fetch()
    route.fulfill(response=r, body=r.text().replace(KONG_INTERNO, KONG_LOCAL))


@pytest.fixture(scope="module")
def docente_pg(navegador: Browser) -> Page:
    estado["docente"] = persona("teacher", "Docente E2E")
    ctx: BrowserContext = navegador.new_context(viewport={"width": 1366, "height": 860}, locale="es-PE")
    page = ctx.new_page()
    page.set_default_timeout(20_000)
    return page


@pytest.fixture(scope="module")
def alumno_pg(navegador: Browser) -> Page:
    estado["alumno"] = persona("student", "Estudiante E2E")
    ctx = navegador.new_context(
        viewport={"width": 1366, "height": 860}, permissions=["camera", "microphone"], locale="es-PE"
    )
    ctx.add_init_script(STUB_ESCRITORIO)
    page = ctx.new_page()
    page.set_default_timeout(20_000)
    page.route("**/api/v1/evidence/upload-url", _reescribir)
    estado["errores_consola"] = []
    page.on("console", lambda m: m.type == "error" and estado["errores_consola"].append(m.text[:200]))
    return page


def iniciar_sesion(page: Page, email: str) -> None:
    page.goto(f"{WEB}/login")
    page.locator('input[type="email"]').fill(email)
    page.locator('input[type="password"]').fill(CONTRASENA)
    page.get_by_role("button", name="Entrar").click()
    page.wait_for_url(lambda u: "/login" not in u, timeout=30_000)


# --------------------------------------------------------------------------- docente


def test_e2e01_docente_inicia_sesion(docente_pg: Page, record_property: Any) -> None:
    """E2E-01 | Autenticación | El docente inicia sesión con correo y contraseña y llega a su panel."""
    iniciar_sesion(docente_pg, estado["docente"].email)
    expect(docente_pg).to_have_url(re.compile(r"/docente$"))
    expect(docente_pg.get_by_role("heading", name="Panel", level=1)).to_be_visible()
    expect(docente_pg.get_by_role("navigation", name="Menú del docente")).to_be_visible()
    captura(docente_pg, "e2e01-panel-docente", record_property)


def test_e2e02_docente_crea_examen(docente_pg: Page, record_property: Any) -> None:
    """E2E-02 | Gestión de exámenes | El docente crea un examen desde el formulario y recibe un código de acceso."""
    p = docente_pg
    p.get_by_role("link", name="Crear examen").first.click()
    p.get_by_label("Título del examen (obligatorio)").fill("Examen E2E de Arquitectura")
    ahora = datetime.now()
    p.get_by_label("Fecha de inicio (obligatorio)").fill(ahora.strftime("%Y-%m-%d"))
    p.get_by_label("Hora de inicio (obligatorio)").fill(ahora.strftime("%H:%M"))
    p.get_by_label("Duración (minutos, obligatorio)").fill("60")
    p.get_by_label("Tolerancia de ingreso (minutos)").fill("30")
    p.get_by_label(re.compile("^Nivel de supervisión")).select_option(label="Estándar")
    p.get_by_role("button", name="Crear examen y añadir preguntas").click()
    p.wait_for_url(re.compile(r"/sesiones/[0-9a-f-]{36}/editar"))
    estado["sid"] = re.search(r"/sesiones/([0-9a-f-]{36})", p.url).group(1)  # type: ignore[union-attr]
    codigo = p.get_by_text(re.compile(r"^[A-Z0-9]{6}$")).first.inner_text().strip()
    assert re.fullmatch(r"[A-Z0-9]{6}", codigo)
    estado["codigo"] = codigo
    captura(p, "e2e02-examen-creado", record_property)


def test_e2e03_docente_agrega_preguntas(docente_pg: Page, record_property: Any) -> None:
    """E2E-03 | Gestión de exámenes | El docente escribe dos preguntas de opción múltiple en el editor y quedan guardadas."""
    p = docente_pg
    preguntas = [
        ("¿Qué capa de la arquitectura hexagonal no importa frameworks?", ["Dominio", "Adaptadores"]),
        ("¿Qué servicio desacopla el análisis de audio de la API?", ["Redis", "Vercel"]),
    ]
    for enunciado, (correcta, otra) in preguntas:
        p.get_by_role("textbox", name="Enunciado", exact=True).fill(enunciado)
        p.get_by_role("textbox", name="Opción 1", exact=True).fill(correcta)
        p.get_by_role("textbox", name="Opción 2", exact=True).fill(otra)
        p.get_by_role("button", name="Añadir pregunta").click()
        expect(p.get_by_text(enunciado).first).to_be_visible()
        # El formulario se vacía cuando el servidor confirma: hasta entonces no se escribe la siguiente.
        expect(p.get_by_role("textbox", name="Enunciado", exact=True)).to_have_value("")
    expect(p.get_by_text(re.compile(r"2 preguntas · mostrando"))).to_be_visible()
    with cliente() as c:
        r = c.get(f"/sessions/{estado['sid']}/questions", headers=estado["docente"].h)
    assert r.status_code == 200 and len(r.json()) == 2
    # Se mira, antes de recargar, qué dice el resumen de arriba (lo comprueba E2E-03b).
    estado["resumen_sin_recargar"] = p.locator(".editor-resumen-contenido strong").inner_text()
    captura(p, "e2e03-preguntas", record_property)
    p.reload()
    expect(p.get_by_text("2 preguntas en el examen")).to_be_visible()


def test_e2e03b_resumen_se_actualiza(docente_pg: Page, record_property: Any) -> None:
    """E2E-03b | Gestión de exámenes | Al añadir preguntas a mano, el resumen «N preguntas en el examen · puntos» se actualiza sin recargar la página."""
    assert estado["resumen_sin_recargar"] == "2 preguntas en el examen", (
        f"Tras añadir 2 preguntas el resumen decía «{estado['resumen_sin_recargar']}» hasta recargar"
    )


# --------------------------------------------------------------------------- estudiante


def test_e2e04_estudiante_entra_con_codigo(alumno_pg: Page, record_property: Any) -> None:
    """E2E-04 | Ingreso | El estudiante inicia sesión, escribe el código en minúsculas y con espacios, y llega a la sala de espera."""
    p = alumno_pg
    iniciar_sesion(p, estado["alumno"].email)
    expect(p).to_have_url(re.compile(r"/estudiante$"))
    c = estado["codigo"]
    p.get_by_role("textbox", name="Código de acceso").fill(f" {c[:3].lower()} {c[3:].lower()} ")
    p.get_by_role("button", name="Buscar examen").click()
    p.wait_for_url(re.compile(rf"/examen/{estado['sid']}/sala"))
    expect(p.get_by_role("heading", name="Examen E2E de Arquitectura")).to_be_visible()
    expect(p.get_by_role("heading", name="Qué se va a supervisar")).to_be_visible()
    captura(p, "e2e04-sala-de-espera", record_property)


def test_e2e05_consentimiento(alumno_pg: Page, record_property: Any) -> None:
    """E2E-05 | Consentimiento | «Aceptar y continuar» está deshabilitado hasta marcar el consentimiento; al aceptar, queda en espera del docente."""
    p = alumno_pg
    boton = p.get_by_role("button", name="Aceptar y continuar")
    expect(boton).to_be_disabled()
    p.get_by_role("checkbox").check()
    expect(boton).to_be_enabled()
    boton.click()
    expect(p.get_by_text("Ya aceptaste la supervisión")).to_be_visible()
    expect(p.get_by_role("button", name=re.compile("Esperando verificación o admisión"))).to_be_disabled()
    captura(p, "e2e05-consentimiento", record_property)


def test_e2e06_docente_admite_en_vivo(docente_pg: Page, alumno_pg: Page, record_property: Any) -> None:
    """E2E-06 | Sala de espera en vivo | El docente ve al estudiante esperando y lo admite; la pantalla del estudiante cambia sola, sin recargar."""
    d = docente_pg
    d.goto(f"{WEB}/sesiones/{estado['sid']}/participantes")
    fila = d.get_by_role("row", name=re.compile("Estudiante E2E"))
    expect(fila).to_contain_text("Esperando verificación")
    inicio = time.monotonic()
    fila.get_by_role("button", name="Admitir").click()
    expect(fila).to_contain_text("Admitido por ti")
    expect(alumno_pg.get_by_text("Tu docente te admitió")).to_be_visible(timeout=30_000)
    estado["admision_s"] = round(time.monotonic() - inicio, 1)
    captura(d, "e2e06a-docente-admite", record_property)
    captura(alumno_pg, "e2e06b-estudiante-admitido", record_property)


def test_e2e07_rinde_y_guarda(alumno_pg: Page, record_property: Any) -> None:
    """E2E-07 | Rendición | El estudiante ve las preguntas sin la clave, elige respuestas y quedan guardadas en el servidor."""
    p = alumno_pg
    p.goto(f"{WEB}/examen/{estado['sid']}/rendir")
    expect(p.get_by_text(re.compile("Pregunta 1 de 2")).first).to_be_visible(timeout=60_000)
    p.get_by_text("Dominio", exact=True).first.click()
    p.get_by_role("button", name=re.compile("^Siguiente")).first.click()
    expect(p.get_by_text(re.compile("Pregunta 2 de 2")).first).to_be_visible()
    p.get_by_text("Redis", exact=True).first.click()
    captura(p, "e2e07-rindiendo", record_property)
    fin = time.time() + 20
    guardadas: list[Any] = []
    while time.time() < fin:
        with cliente() as c:
            guardadas = c.get(f"/exam/{estado['sid']}/answers", headers=estado["alumno"].h).json()
        if len(guardadas) >= 2:
            break
        time.sleep(1)
    assert len(guardadas) >= 2, guardadas


def test_e2e08_sin_rostro_genera_senal(alumno_pg: Page, record_property: Any) -> None:
    """E2E-08 | Supervisión | Con la cámara sin nadie delante, el estudiante ve «No se detecta tu rostro», el examen sigue, y el servidor registra face_absent."""
    p = alumno_pg
    expect(p.get_by_text("Supervisión activa")).to_be_visible()
    expect(p.get_by_text("No se detecta tu rostro")).to_be_visible(timeout=60_000)
    fin = time.time() + 90
    tipos: set[str] = set()
    while time.time() < fin:
        with cliente() as c:
            tipos = {e["event_type"] for e in c.get(f"/sessions/{estado['sid']}/events", headers=estado["docente"].h).json()}
        if "face_absent" in tipos:
            break
        time.sleep(2)
    estado["tipos"] = tipos
    assert "face_absent" in tipos, tipos
    captura(p, "e2e08-sin-rostro", record_property)
    # El aviso se puede cerrar o se va solo; en los dos casos el examen sigue.
    aviso = p.get_by_role("button", name="Entendido, continuar")
    if aviso.is_visible():
        aviso.click()
    expect(p.get_by_text(re.compile("Pregunta 2 de 2")).first).to_be_visible()


def test_e2e09_docente_ve_alertas(docente_pg: Page, record_property: Any) -> None:
    """E2E-09 | Alertas en vivo | En «Actividad» el docente ve al estudiante con sus señales de rostro ausente, sin recargar."""
    d = docente_pg
    d.goto(f"{WEB}/sesiones/{estado['sid']}?vista=actividad")
    expect(d.get_by_role("heading", name="Alertas", level=2)).to_be_visible()
    expect(d.get_by_text("Estudiante E2E").first).to_be_visible(timeout=60_000)
    captura(d, "e2e09-actividad", record_property)


def test_e2e10_entrega(alumno_pg: Page, record_property: Any) -> None:
    """E2E-10 | Entrega | El estudiante entrega, confirma, y el servidor registra la entrega con nota."""
    p = alumno_pg
    mensajes: list[str] = []

    def aceptar(dialogo: Any) -> None:
        mensajes.append(dialogo.message)
        dialogo.accept()

    p.once("dialog", aceptar)
    p.get_by_role("button", name="Entregar examen").last.click()
    expect(p.get_by_text(re.compile("entregaste|Entregado|Examen entregado", re.I)).first).to_be_visible(timeout=30_000)
    assert mensajes and "entregar" in mensajes[0].lower(), mensajes
    with cliente() as c:
        yo = c.get(f"/exam/{estado['sid']}/me", headers=estado["alumno"].h).json()
    assert yo["submitted_at"]
    captura(p, "e2e10-entregado", record_property)


def test_e2e11_docente_revisa_y_decide(docente_pg: Page, record_property: Any) -> None:
    """E2E-11 | Revisión y decisión | El docente abre el caso con riesgo, línea de tiempo y evidencia, y registra una decisión con justificación."""
    d = docente_pg
    d.goto(f"{WEB}/sesiones/{estado['sid']}/estudiantes/{estado['alumno'].id}")
    expect(d.get_by_role("heading", name="Riesgo")).to_be_visible()
    expect(d.get_by_role("heading", name="Línea de tiempo")).to_be_visible()
    expect(d.get_by_role("heading", name="Tu decisión")).to_be_visible()
    captura(d, "e2e11a-caso", record_property)
    d.get_by_text(re.compile("Desestimar|Descartar", re.I)).first.click()
    d.get_by_role("textbox").last.fill("Revisé la evidencia: fue un intento de copiar sin consecuencias.")
    d.get_by_role("button", name=re.compile("Guardar|Registrar", re.I)).last.click()
    fin = time.time() + 15
    decisiones: list[Any] = []
    while time.time() < fin and not decisiones:
        with cliente() as c:
            decisiones = [x for x in c.get(f"/sessions/{estado['sid']}/decisions", headers=estado["docente"].h).json() if x["student_id"] == estado["alumno"].id]
        time.sleep(1)
    assert decisiones and decisiones[0]["decision"] == "dismissed"
    captura(d, "e2e11b-decision", record_property)


def test_e2e12_estudiante_no_entra_al_panel_docente(alumno_pg: Page, record_property: Any) -> None:
    """E2E-12 | Roles | Un estudiante que escribe /docente en la barra no ve el panel del docente."""
    p = alumno_pg
    p.goto(f"{WEB}/docente")
    p.wait_for_timeout(2500)
    assert "/docente" not in p.url or p.get_by_role("navigation", name="Menú del docente").count() == 0
    captura(p, "e2e12-rol", record_property)


def test_e2e13_tema_oscuro_persiste(docente_pg: Page, record_property: Any) -> None:
    """E2E-13 | Interfaz | El botón de tema cambia a oscuro y la elección se mantiene al recargar."""
    d = docente_pg
    d.goto(f"{WEB}/docente")
    d.get_by_role("button", name="Cambiar a modo oscuro").click()
    d.reload()
    expect(d.get_by_role("button", name="Cambiar a modo claro")).to_be_visible()
    captura(d, "e2e13-oscuro", record_property)
    d.get_by_role("button", name="Cambiar a modo claro").click()


def test_e2e14_cerrar_sesion(docente_pg: Page, record_property: Any) -> None:
    """E2E-14 | Autenticación | Al cerrar sesión vuelve al inicio y las rutas privadas piden iniciar sesión de nuevo."""
    d = docente_pg
    d.get_by_role("button", name="Cerrar sesión").click()
    d.wait_for_timeout(1500)
    d.goto(f"{WEB}/sesiones")
    d.wait_for_url(re.compile(r"/login"), timeout=15_000)
    captura(d, "e2e14-sesion-cerrada", record_property)
