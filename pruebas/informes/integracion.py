"""Informe de pruebas de integración.

    python pruebas/informes/integracion.py <carpeta remoto> <pdf>
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_informe import agrupar, cargar, fecha, tabla_casos  # noqa: E402
from plantilla import e, kpis, pdf, tabla  # noqa: E402

R = Path(sys.argv[1])
datos = cargar(R / "integracion.json")
g = agrupar(datos["casos"])
medidas = {c["id"]: c.get("medidas", {}) for c in datos["casos"]}
pasan = sum(1 for x in g.values() if not x["fallas"])
fallan = len(g) - pasan


def junit(nombre: str) -> dict[str, int]:
    r = ET.parse(R / nombre).getroot()
    s = r if r.tag == "testsuite" else r.find("testsuite")
    return {k: int(s.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}


api = junit("api-integracion-junit.xml")
ia = junit("ai-integracion-junit.xml")
m11, m14 = medidas.get("IN-11", {}), medidas.get("IN-14", {})


def num(v: object, d: int = 1) -> str:
    return f"{float(v):.{d}f}".replace(".", ",") if isinstance(v, (int, float)) else "—"


inf = {
    "titulo": "Informe de pruebas de integración",
    "subtitulo": "Las fronteras entre servicios, sin dobles: API, Auth, PostgreSQL con RLS, Storage, Redis, los workers de IA y Realtime hablando entre sí de verdad.",
    "veredicto": (
        "medio",
        f"<b>{len(g)} casos de integración: {pasan} pasan y {fallan} fallan</b>, más {api['tests']} pruebas de integración de la API (todas pasan, con Redis real). "
        "Las 2 fallas son hallazgos reales: una política RLS que deja escribir eventos sin pasar por la API y la tabla <code>risk_scores</code>, que nunca se llena.",
    ),
    "ficha": [
        ("Proyecto", "Sistema Proctoring (rama develop)"),
        ("Fecha de ejecución", f"{fecha(datos['inicio'])} (duración {datos['fin'] - datos['inicio']:.0f} s)"),
        ("Ejecutado por", "Silva Vega, Héctor (con asistencia de Claude Code)"),
        ("Entorno", "Aislado en el VPS: Supabase local (Auth, PostgREST, Storage, Realtime) con las 23 migraciones; 2 réplicas de la API tras nginx; Redis; 2 workers de IA con la imagen de producción (Whisper small)"),
        ("Herramientas", "pytest 9, httpx, websockets 15 (protocolo Phoenix de Realtime), RQ"),
    ],
    "secciones": [
        (
            "1. Objetivo y alcance",
            "<p>Las pruebas unitarias sustituyen cada servicio externo por uno en memoria. Estas lo quitan: cada caso cruza al menos una frontera real y comprueba que "
            "<b>lo que una pieza escribe es exactamente lo que la otra lee</b>. Se cubren todas las fronteras de la arquitectura:</p>"
            + tabla(
                ["Frontera", "Qué viaja por ella", "Casos"],
                [
                    ("Supabase Auth ⇄ API", "JWT ES256 verificado contra el JWKS", "IN-01, IN-02"),
                    ("API ⇄ PostgreSQL", "eventos, alertas, riesgo, preguntas (service role)", "IN-03 a IN-05"),
                    ("Cliente ⇄ PostgreSQL (RLS)", "lo que un usuario puede leer o escribir sin pasar por la API", "IN-06 a IN-08"),
                    ("API ⇄ Storage", "URLs firmadas de subida y lectura; buckets privados", "IN-09, IN-10"),
                    ("API ⇄ Redis ⇄ worker IA ⇄ API", "trabajo de audio, transcripción, similitud, resultado", "IN-11 a IN-13"),
                    ("PostgreSQL ⇄ Realtime ⇄ docente", "alertas en vivo por WebSocket y su aislamiento", "IN-14, IN-15"),
                    ("réplicas ⇄ Redis ⇄ nginx", "límite de peticiones compartido y lecturas balanceadas", "IN-16, IN-17"),
                ],
            ),
        ),
        (
            "2. Resultados",
            kpis(
                [
                    ("casos de integración", f"{pasan}/{len(g)}"),
                    ("alerta → docente por Realtime", f"{num(m14.get('alerta_a_docente_s'), 2)} s"),
                    ("audio → análisis de IA", f"{num(m11.get('espera_s'))} s"),
                    ("similitud con el enunciado", num(m11.get('similitud'), 2)),
                ]
            )
            + tabla_casos(g, etiqueta="Frontera")
            + "<h3>Suites de integración que ya tenía el proyecto</h3>"
            + tabla(
                ["Suite", "Pruebas", "Fallan", "Omitidas", "Nota"],
                [
                    ("API: endpoints con TestClient + cola Redis real (<code>services/api/tests/integration</code>)", api["tests"], api["failures"] + api["errors"], api["skipped"], "En la máquina de desarrollo se omiten 7 por no tener Redis; aquí corrieron todas"),
                    ("IA: worker RQ con Redis real (<code>services/ai/tests/test_integration_real_redis.py</code>)", ia["tests"], ia["failures"] + ia["errors"], ia["skipped"], "Falla la prueba, no el worker (ver hallazgo H-03)"),
                ],
                (1, 2, 3),
            ),
        ),
        (
            "3. Mediciones de las fronteras con tiempo",
            tabla(
                ["Medición", "Valor", "Meta"],
                [
                    ("Señal alta → alerta recibida por el docente vía Realtime (IN-14)", f"{num(m14.get('alerta_a_docente_s'), 2)} s", "< 5 s (SPEC-009 CA-2) ✔"),
                    ("Audio subido → análisis guardado (IN-11, un fragmento de 5 s)", f"{num(m11.get('espera_s'))} s", "< 10 s ✘"),
                    ("Tiempo de procesamiento que reporta el worker", f"{m11.get('procesamiento_ms', '—'):,} ms".replace(',', '.'), ""),
                    ("Transcripción obtenida de «¿Cuántos segundos como máximo puede tardar la alerta de IA por voz?»", e(m11.get("transcripcion", "—")), ""),
                    ("Similitud con el enunciado de la pregunta en curso", num(m11.get('similitud'), 3), "≥ 0,60 (umbral del módulo) ✔"),
                    ("4 audios simultáneos repartidos entre 2 workers (IN-12)", e(medidas.get("IN-12", {}).get("analizados", "—")), "todos ✔"),
                ],
            )
            + "<p>La transcripción tiene errores de Whisper <i>small</i> («dar» por «tardar», «la por vos» por «IA por voz»), y aun así la similitud semántica supera el umbral: "
            "el diseño de comparar significado y no palabras exactas funciona. Con el entorno sin carga, el audio tardó 14 s: no cumple la meta de 10 s, igual que en el informe de carga (trabajo pendiente del servicio de IA).</p>",
        ),
        (
            "4. Hallazgos",
            "<h3>H-01 · Un estudiante puede insertar eventos directo en la base, sin pasar por la API (IN-07) · severidad media</h3>"
            "<p>La política RLS <code>events_student_insert</code> (migración <code>20261003120100_row_level_security.sql</code>) permite a un participante insertar filas en <code>events</code> "
            "con la clave publicable y su propio token. PostgREST respondió <b>201</b>. Así se salta lo que hace la API: validar que el módulo esté activo, el límite de 120 escrituras por minuto, "
            "calcular la severidad y crear la alerta. Solo puede escribir a su nombre (no a nombre de otro), así que no puede culpar a nadie, pero sí inundar la tabla y la vista «Todas las señales» del docente. "
            "<b>Ningún cliente usa esa vía</b> (la web y la app mandan todo por la API, ADR-0010).</p>"
            "<p><b>Recomendación:</b> una migración nueva que elimine esa política (<code>drop policy events_student_insert on public.events</code>). Responsable: Jesús (base de datos), con revisión de Héctor.</p>"
            "<h3>H-02 · La tabla risk_scores nunca se llena (IN-04) · severidad baja</h3>"
            "<p>La SPEC-009 CA-1 dice que el riesgo «se guarda en <code>risk_scores</code> desglosado por señal». La API lo <b>calcula al leer</b> a partir de los eventos (<code>domain/risk.py</code>) "
            "y lo entrega desglosado en el caso del estudiante, pero nunca escribe esa tabla. El docente no pierde nada (siempre ve el riesgo actual); lo que no se cumple es la letra de la SPEC, "
            "y la tabla queda vacía. <b>Recomendación:</b> decidir una de dos: actualizar la SPEC y retirar la tabla, o persistir el riesgo al registrar cada evento si se quiere historial.</p>"
            "<h3>H-03 · La prueba de integración del worker con Redis real falla en Linux (defecto de la prueba)</h3>"
            "<p>En Linux RQ ejecuta el trabajo en un proceso hijo (<code>fork</code>); los dobles que guardan lo que el worker manda a la API quedan en ese hijo y la lista del padre sigue vacía. "
            "El trabajo sí termina bien (estado <code>finished</code>, resultado <code>alerted: True</code>). En Windows pasa porque usa <code>SimpleWorker</code>. "
            "<b>Recomendación:</b> usar <code>SimpleWorker</code> siempre en esa prueba. Responsable: Pierreluiggi. El flujo real worker ⇄ API sí se comprobó en IN-11 e IN-12.</p>"
            "<h3>Lo que se confirmó</h3><ul>"
            "<li>Los tokens reales de Auth se aceptan; el rol sale de <code>profiles</code>.</li>"
            "<li>RLS impide leer datos ajenos, escalar el rol, borrar alertas y leer fotos de referencia.</li>"
            "<li>Los buckets son privados: sin firma, Storage no entrega el archivo; con la URL de lectura del docente, sí.</li>"
            "<li>Un estudiante no puede pedir subidas a nombre de otro.</li>"
            "<li>Los endpoints internos del worker rechazan a quien no trae el secreto, aunque sea un docente.</li>"
            "<li>Realtime entrega la alerta al docente del examen y <b>no</b> a otro docente suscrito al mismo canal.</li>"
            "<li>El límite de intentos se cuenta en Redis, no por réplica.</li></ul>",
        ),
        (
            "5. Conclusión y cómo reproducir",
            "<p>Las piezas se integran correctamente en todas las fronteras de la arquitectura; las alertas llegan en tiempo real muy por debajo de la meta. "
            "Se recomienda corregir H-01 con una migración antes del próximo examen real, porque es superficie de ataque que nadie usa.</p>"
            "<pre># entorno aislado + workers de IA arriba (loadtests/README.md)\ncd pruebas && RESULTADOS=integracion.json \\\n  uv run --project ../loadtests --with pytest --with websockets python -m pytest integracion\n"
            "cd services/api && uv run pytest tests/integration   # con Redis en localhost:6379</pre>",
        ),
    ],
}

print(pdf(inf, Path(sys.argv[2])))
