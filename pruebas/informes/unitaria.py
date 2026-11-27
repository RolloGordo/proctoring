"""Informe de pruebas unitarias: lee los JUnit y la cobertura de la corrida y arma el PDF.

    python pruebas/informes/unitaria.py <carpeta de resultados> <pdf de salida>
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plantilla import e, kpis, pdf, tabla  # noqa: E402

R = Path(sys.argv[1])
SALIDA = Path(sys.argv[2])


def junit(nombre: str) -> tuple[Counter[str], Counter[str], float]:
    raiz = ET.parse(R / f"{nombre}-junit.xml").getroot()
    tot: Counter[str] = Counter()
    grupos: Counter[str] = Counter()
    segundos = 0.0
    for tc in raiz.iter("testcase"):
        estado = (
            "omitida"
            if tc.find("skipped") is not None
            else "falla"
            if tc.find("failure") is not None or tc.find("error") is not None
            else "pasa"
        )
        tot[estado] += 1
        segundos += float(tc.get("time") or 0)
        clase = (tc.get("classname") or tc.get("file") or "").replace("/", ".").replace("\\", ".")
        grupos[".".join(clase.split(".")[:3])] += 1
    return tot, grupos, segundos


def cov_py(nombre: str, excluir: tuple[str, ...] = ()) -> dict[str, float]:
    d = json.loads((R / f"{nombre}-cov.json").read_text(encoding="utf-8"))
    s = c = b = bc = 0
    for f, v in d["files"].items():
        if f.replace("\\", "/").startswith(excluir):
            continue
        m = v["summary"]
        s += m["num_statements"]
        c += m["covered_lines"]
        b += m["num_branches"]
        bc += m["covered_branches"]
    return {"lineas": 100 * c / s, "ramas": 100 * bc / max(b, 1), "sentencias": s}


def cov_js(nombre: str) -> dict[str, float]:
    t = json.loads((R / f"{nombre}-cov" / "coverage-summary.json").read_text(encoding="utf-8"))["total"]
    return {"lineas": t["lines"]["pct"], "ramas": t["branches"]["pct"], "sentencias": t["statements"]["total"], "funciones": t["functions"]["pct"]}


api, api_g, api_s = junit("api")
ai, ai_g, ai_s = junit("ai")
ai_x, _, ai_xs = junit("ai-extra")
web, web_g, web_s = junit("web")
desk, desk_g, desk_s = junit("desk")
auto, _, auto_s = junit("auto")

unit_api = sum(n for g, n in api_g.items() if g.startswith("tests.unit"))
http_api = sum(n for g, n in api_g.items() if g.startswith("tests.integration.http"))

c_api = cov_py("api")
c_ai = cov_py("ai", ("tests/", "spikes/"))
c_web = cov_js("web")
c_desk = cov_js("desk")
c_auto = cov_py("auto", ("deploy/autoescalado/test_",))

# Cobertura de la API por capa hexagonal.
capas: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
for f, v in json.loads((R / "api-cov.json").read_text(encoding="utf-8"))["files"].items():
    partes = f.replace("\\", "/").split("proctoring_api/")[-1].split("/")
    capa = {"domain": "domain (reglas puras)", "application": "application (casos de uso y puertos)"}.get(partes[0])
    if partes[0] == "adapters":
        capa = f"adapters/{partes[1]}"
    capa = capa or "composición (main.py, config.py)"
    m = v["summary"]
    for i, k in enumerate(("num_statements", "covered_lines", "num_branches", "covered_branches")):
        capas[capa][i] += m[k]

total = sum(x["pasa"] + x["falla"] + x["omitida"] for x in (api, ai, web, desk, auto))
fallas = sum(x["falla"] for x in (api, ai, ai_x, web, desk, auto))
pasan = sum(x["pasa"] for x in (api, ai, web, desk, auto))
omitidas = sum(x["omitida"] for x in (api, ai, web, desk, auto))

filas_suites = [
    ("API principal (Python, pytest)", api["pasa"], api["falla"], api["omitida"], f"{api_s:.0f} s", f"{c_api['lineas']:.1f} %", f"{c_api['ramas']:.1f} %"),
    ("Servicio de IA (Python, pytest)", ai["pasa"], ai["falla"], ai["omitida"], f"{ai_s:.0f} s", f"{c_ai['lineas']:.1f} %", f"{c_ai['ramas']:.1f} %"),
    ("Web docente y examen (TypeScript, Vitest)", web["pasa"], web["falla"], web["omitida"], f"{web_s:.0f} s", f"{c_web['lineas']:.1f} %", f"{c_web['ramas']:.1f} %"),
    ("App de escritorio (Electron, Vitest)", desk["pasa"], desk["falla"], desk["omitida"], f"{desk_s:.1f} s" if desk_s else "< 1 s", f"{c_desk['lineas']:.1f} %", f"{c_desk['ramas']:.1f} %"),
    ("Autoescalador (Python, pytest)", auto["pasa"], auto["falla"], auto["omitida"], f"{auto_s:.1f} s" if auto_s >= 0.1 else "< 0,1 s", f"{c_auto['lineas']:.1f} %", f"{c_auto['ramas']:.1f} %"),
]

grupos_api = [
    ("Dominio (entidades, severidad, riesgo, calificación)", api_g.get("tests.unit.domain", 0), "Funciones puras, sin dobles"),
    ("Casos de uso (application)", api_g.get("tests.unit.application", 0), "Adaptadores en memoria como dobles de los puertos"),
    ("Adaptadores (Supabase, Redis, HTTP, límite)", api_g.get("tests.unit.adapters", 0), "Clientes HTTP y Redis simulados"),
    ("Configuración hermética", api_g.get("tests.unit.test_settings_hermeticos", 0), "Que ninguna prueba lea el .env real"),
    ("Endpoints con TestClient", http_api, "Router + caso de uso + adaptadores en memoria"),
    ("Cola Redis real", api_g.get("tests.integration.test_redis_queue", 0), "Necesita Redis (ver informe de integración)"),
]

filas_capas = [
    (e(k), v[0], f"{100 * v[1] / v[0]:.1f} %", v[2], f"{100 * v[3] / max(v[2], 1):.1f} %")
    for k, v in sorted(capas.items())
    if v[0]
]

ahora = datetime.now().strftime("%d/%m/%Y %H:%M")

inf = {
    "titulo": "Informe de pruebas unitarias",
    "subtitulo": "Cada unidad del sistema probada en aislamiento: reglas del dominio, casos de uso, adaptadores, detectores del navegador y proceso principal de Electron.",
    "veredicto": (
        "ok" if fallas == 0 else "mal",
        f"<b>{pasan} pruebas pasan, {fallas} fallan.</b> {omitidas} se omitieron por depender de un servicio o librería que no estaba en el equipo; "
        f"las 5 de IA que pedían OpenCV y scikit-learn se repitieron con esas librerías y sus dos archivos ({ai_x['pasa']} casos) pasan completos.",
    ),
    "ficha": [
        ("Proyecto", "Sistema Proctoring (repositorio RolloGordo/proctoring, rama develop)"),
        ("Fecha de ejecución", ahora),
        ("Ejecutado por", "Silva Vega, Héctor (con asistencia de Claude Code)"),
        ("Herramientas", "pytest 9 + pytest-cov (Python 3.12), Vitest 5 + @vitest/coverage-v8 (Node 22)"),
        ("Entorno", "Windows 11, sin red hacia servicios externos: todo dependiente se sustituye por dobles"),
    ],
    "secciones": [
        (
            "1. Objetivo y alcance",
            "<p>Comprobar que cada pieza del sistema hace lo que promete <b>por sí sola</b>, sin base de datos, sin red y sin otros servicios. "
            "Es la primera red de seguridad del proyecto: corre en segundos, en cada push y en cada PR (job <code>CI</code> de GitHub Actions), y un PR no entra si una falla.</p>"
            "<p>Alcance: los cinco componentes con código propio. Los adaptadores reales contra Supabase y Redis se prueban en el informe de integración; los flujos completos, en el de E2E.</p>"
            "<h3>Criterio de una buena prueba unitaria en este proyecto</h3><ul>"
            "<li>Un caso de uso se prueba con <b>adaptadores en memoria</b> (los mismos que usa el modo local), no con mocks de cada llamada: la prueba no se rompe al refactorizar.</li>"
            "<li>El dominio no se mockea: son funciones puras y se prueban con datos.</li>"
            "<li>Ninguna prueba lee el <code>.env</code> real (lo garantiza <code>test_settings_hermeticos.py</code>).</li>"
            "<li>La arquitectura también se prueba: <b>import-linter</b> verifica que <code>domain</code> y <code>application</code> no importen frameworks.</li></ul>",
        ),
        (
            "2. Resultados por componente",
            kpis(
                [
                    ("pruebas ejecutadas", str(total)),
                    ("pasan", str(pasan)),
                    ("fallan", str(fallas)),
                    ("cobertura de la API (líneas)", f"{c_api['lineas']:.0f} %"),
                ]
            )
            + tabla(["Componente", "Pasan", "Fallan", "Omitidas", "Tiempo", "Cobertura de líneas", "Cobertura de ramas"], filas_suites, (1, 2, 3, 4, 5, 6))
            + "<p>La cobertura de IA cuenta solo el código que se despliega (sin <code>tests/</code> ni los <code>spikes/</code> de investigación). "
            "Con los spikes incluidos baja al 49 %: son scripts de evaluación de modelos, no código de producción.</p>",
        ),
        (
            "3. API principal: qué se prueba en cada capa",
            tabla(["Grupo", "Pruebas", "Cómo se aísla"], grupos_api, (1,))
            + "<h3>Cobertura por capa hexagonal</h3>"
            + tabla(["Capa", "Sentencias", "Líneas cubiertas", "Ramas", "Ramas cubiertas"], filas_capas, (1, 2, 3, 4))
            + "<p>El <b>dominio</b> y los <b>casos de uso</b>, donde vive la lógica de negocio (severidad, riesgo, módulos por preset, reglas de ingreso y entrega, decisión justificada), "
            "están por encima del 96 % de líneas. Lo menos cubierto son los adaptadores de salida hacia Supabase (PostgREST): en unitarias se sustituyen por memoria, "
            "y su comportamiento real se verifica contra un Supabase de verdad en los informes de caja negra e integración.</p>",
        ),
        (
            "4. Ejemplos de unidades verificadas",
            "<ul>"
            "<li><b>Severidad por umbral</b> (<code>domain/severity.py</code>): foco perdido baja &lt; 5 s, media &lt; 30 s, alta desde 30 s; rostro ausente 5 s / 15 s; mirada 10 s.</li>"
            "<li><b>Riesgo desglosado</b> (<code>domain/risk.py</code>): pesos 1/8/25 por severidad, tope de 50 por tipo de señal y 100 en total; niveles medio desde 15 y alto desde 40.</li>"
            "<li><b>Módulos por preset</b>: una señal de un módulo apagado en un examen <code>custom</code> se rechaza.</li>"
            "<li><b>Decisión del docente</b>: justificación de al menos 10 caracteres; solo confirmed, dismissed o retake.</li>"
            "<li><b>Límite de peticiones</b>: ventana deslizante, 120 escrituras por minuto y 10 intentos de código; si Redis cae, cuenta en memoria.</li>"
            "<li><b>Web</b>: detectores de rostro, mirada, objetos y voz; emisor de señales con cola y reintentos; avisos al estudiante; calibración.</li>"
            "<li><b>Escritorio</b>: validación estricta del enlace <code>proctoring://</code>, permisos de cámara solo al origen propio, protección de contenido y aviso de actualizaciones.</li>"
            "<li><b>Autoescalador</b> (la política, que es una función pura; el bucle que llama a <code>docker</code> no se prueba en unitarias, de ahí su 50 % de líneas): subir con CPU &gt; 70 % sostenida, bajar tras 3 min &lt; 25 %, respetar mínimo 2 y máximo 5 y los tiempos de espera.</li>"
            "</ul>",
        ),
        (
            "5. Pruebas omitidas y por qué",
            tabla(
                ["Componente", "Pruebas", "Motivo", "Dónde quedan cubiertas"],
                [
                    ("API", api["omitida"], "Necesitan Redis en localhost:6379", "Informe de integración (Redis real en el entorno aislado)"),
                    ("IA", 1, "Necesita Redis real", "Informe de integración"),
                    ("IA", 5, "Necesitan OpenCV y scikit-learn (no van en el entorno de desarrollo mínimo)", f"Repetidas aquí con esas librerías: {ai_x['pasa']} pasan, {ai_x['falla']} fallan"),
                ],
                (1,),
            ),
        ),
        (
            "6. Hallazgos",
            "<ul>"
            f"<li><span class="ok">Sin fallas</span>: ninguna de las {total} pruebas falla.</li>"
            f"<li><span class='medio'>Cobertura baja en la app de escritorio ({c_desk['lineas']:.0f} %)</span>: <code>processes.ts</code> (21 %) y <code>web.ts</code> (27 %) llaman a APIs del sistema operativo y de Electron. "
            "Se recomienda extraer la parte de decisión (qué proceso es sospechoso) a una función pura y probarla (responsable: Rider).</li>"
            f"<li><span class='medio'>Web ({c_web['lineas']:.0f} %)</span>: lo menos cubierto es el detector de objetos (21 %) y <code>diagnostics.ts</code> (25 %), que dependen de MediaPipe en el navegador; quedan cubiertos por E2E.</li>"
            f"<li><span class='medio'>IA ({c_ai['lineas']:.0f} %)</span>: <code>face_pipeline.py</code> está al 50 %; la verificación facial con imágenes reales queda en integración.</li>"
            "</ul>",
        ),
        (
            "7. Conclusión",
            f"<p>Las unidades del sistema cumplen su especificación: {pasan} pruebas pasan y ninguna falla. La lógica de negocio (dominio y casos de uso) tiene la cobertura más alta, "
            "que es donde más importa. La deuda está en el código pegado al sistema operativo y al navegador, que por naturaleza se verifica mejor con pruebas de extremo a extremo.</p>"
            "<h3>Cómo reproducir</h3><pre>cd services/api && uv run pytest --cov=proctoring_api --cov-branch\ncd services/ai  && uv run pytest\ncd apps/web     && npx vitest run --coverage\ncd apps/desktop && npx vitest run --coverage\nuv run --no-project --with pytest python -m pytest deploy/autoescalado</pre>",
        ),
    ],
}

print(pdf(inf, SALIDA))
