"""Informe de pruebas de extremo a extremo (web y app de escritorio).

    python pruebas/informes/e2e.py <e2e-web.json> <capturas web> <e2e-escritorio.json> <capturas escritorio> <pdf>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_informe import agrupar, cargar, fecha, galeria, tabla_casos  # noqa: E402
from plantilla import e, imagen, kpis, pdf, tabla  # noqa: E402

web = cargar(Path(sys.argv[1]))
cap_web = Path(sys.argv[2])
esc = cargar(Path(sys.argv[3]))
cap_esc = Path(sys.argv[4])

gw, ge = agrupar(web["casos"]), agrupar(esc["casos"])
todos = list(gw.values()) + list(ge.values())
pasan = sum(1 for x in todos if not x["fallas"])
fallan = len(todos) - pasan
detalle_esc = {c["id"]: c["detalle"] for c in esc["casos"]}


def falla_img(carpeta: Path, patron: str, pie: str) -> str:
    rutas = sorted(carpeta.glob(patron))
    return imagen(rutas[0], pie) if rutas else ""


inf = {
    "titulo": "Informe de pruebas de extremo a extremo (E2E)",
    "subtitulo": "El producto completo usado como lo usan las personas: un docente y un estudiante en navegadores reales, y la app de escritorio real con sus detectores del sistema operativo.",
    "veredicto": (
        "medio" if fallan else "ok",
        f"<b>{len(todos)} escenarios: {pasan} pasan y {fallan} fallan.</b> Las {fallan} fallas son defectos reales de la interfaz, "
        "no del flujo crítico: el examen se crea, se rinde, se supervisa, se entrega y se decide de principio a fin.",
    ),
    "ficha": [
        ("Proyecto", "Sistema Proctoring (rama develop; app de escritorio 1.1.4)"),
        ("Fecha de ejecución", f"Web: {fecha(web['inicio'])} · Escritorio: {fecha(esc['inicio'])}"),
        ("Ejecutado por", "Silva Vega, Héctor (con asistencia de Claude Code)"),
        ("Herramientas", "Playwright 1.55 (Chromium sin ventana para la web; <code>_electron</code> para la app de escritorio), pytest 9"),
        ("Entorno", "Aislado en el VPS: web (nginx), 2 réplicas de la API, Redis y Supabase local. La app de escritorio corrió en Windows 11 apuntada a ese entorno por un túnel SSH"),
        ("Cámara y micrófono", "Los de prueba de Chromium (<code>--use-fake-device-for-media-stream</code>): nunca la cámara del equipo"),
    ],
    "secciones": [
        (
            "1. Objetivo y alcance",
            "<p>Comprobar que las piezas, que por separado ya pasan sus pruebas unitarias y de caja negra, funcionan <b>juntas</b> para una persona: "
            "interfaz, API, base de datos, autenticación, tiempo real y la app de escritorio. Se automatizan dos recorridos:</p><ol>"
            "<li><b>Web</b>: un docente y un estudiante, cada uno en su navegador, recorren el ciclo completo de un examen por la interfaz.</li>"
            "<li><b>Escritorio</b>: la app Electron real, con su proceso principal, su preload y sus detectores (foco, atajos, procesos), que el navegador no tiene.</li></ol>"
            "<h3>Lo que queda fuera, y por qué</h3><ul>"
            "<li><b>Encuadre y verificación facial</b>: piden un rostro real frente a la cámara. El estudiante entra por la <b>admisión manual del docente</b>, "
            "que es el camino que el producto prevé cuando la cámara no reconoce a alguien. El motor facial se prueba en las unitarias de IA.</li>"
            "<li><b>Monitores adicionales y voz</b>: no se pueden simular de forma fiable en una máquina sin pantallas extra ni audio. Quedan cubiertos por las pruebas unitarias e integración.</li></ul>",
        ),
        (
            "2. Resultados",
            kpis([("escenarios", str(len(todos))), ("pasan", str(pasan)), ("fallan", str(fallan)), ("web / escritorio", f"{len(gw)} / {len(ge)}")])
            + "<h3>2.1 Recorrido web (docente y estudiante)</h3>"
            + tabla_casos(gw, etiqueta="Área")
            + "<h3>2.2 App de escritorio (Electron)</h3>"
            + tabla_casos(ge, etiqueta="Área")
            + "<h3>Mediciones del recorrido de escritorio</h3>"
            + tabla(
                ["Escenario", "Lo que se midió"],
                [(e(k), e(v)) for k, v in detalle_esc.items() if v and k not in ("ED-06a",)],
            ),
        ),
        (
            "3. Defectos encontrados",
            "<h3>D-01 · El resumen del editor no se actualiza al añadir preguntas (E2E-03b)</h3>"
            "<p><b>Dónde:</b> editor del examen, pestaña Contenido (<code>apps/web/src/pages/EditorExamen.tsx</code>). <b>Severidad:</b> baja. <b>Responsable:</b> Rider (interfaz web).</p>"
            "<p><b>Qué pasa:</b> tras añadir dos preguntas a mano, la lista muestra «2 preguntas», están guardadas en el servidor, pero el resumen de arriba sigue en "
            "«0 preguntas en el examen · 0 puntos» hasta recargar. <b>Causa:</b> el resumen se recalcula cuando cambia <code>versionContenido</code>, y añadir una pregunta manual no lo incrementa "
            "(sí lo hace importar QTI). <b>Riesgo:</b> el docente puede creer que el examen está vacío o que la pregunta no se guardó.</p>"
            + falla_img(cap_web, "FALLO-test_e2e03b*", "D-01: lista con 2 preguntas y resumen en 0, antes de recargar")
            + "<h3>D-02 · Abrir la sala directamente muestra «No encontramos ese examen» (ED-06a)</h3>"
            "<p><b>Dónde:</b> sala de espera (<code>apps/web/src/pages/SalaDeEspera.tsx</code>), y por tanto el enlace <code>proctoring://examen/&lt;id&gt;</code> de la app de escritorio. "
            "<b>Severidad:</b> media. <b>Responsable:</b> Rider.</p>"
            "<p><b>Qué pasa:</b> un estudiante matriculado y admitido, con la sesión iniciada en la app, abre la sala de su examen por la dirección directa y ve «No encontramos ese examen. Vuelve a escribir tu código». "
            "<b>Causa:</b> la sala solo conoce el examen por el estado de la pantalla del código o por <code>sessionStorage</code>, que una ventana nueva no tiene; no lo pide a la API (<code>/exam/{id}/me</code>). "
            "<b>Riesgo:</b> el enlace de la app de escritorio no lleva al examen; el estudiante tiene que volver a escribir el código (se recupera, pero confunde en el peor momento).</p>"
            + falla_img(cap_esc, "ed06a*", "D-02: la sala abierta por su dirección, con el estudiante ya admitido"),
        ),
        (
            "4. Hallazgos positivos",
            "<ul>"
            "<li><span class='ok'>Ciclo completo</span>: crear examen y preguntas por la interfaz, entrar con código (acepta minúsculas y espacios), consentir, ser admitido, rendir, entregar y decidir.</li>"
            "<li><span class='ok'>Tiempo real</span>: la pantalla del estudiante cambia sola cuando el docente lo admite, sin recargar.</li>"
            "<li><span class='ok'>Consentimiento</span>: «Aceptar y continuar» no se habilita sin marcarlo.</li>"
            "<li><span class='ok'>Supervisión</span>: sin rostro frente a la cámara, el estudiante ve el aviso, el examen sigue y el servidor registra <code>face_absent</code>.</li>"
            "<li><span class='ok'>Escritorio</span>: contextIsolation, sandbox, sin Node en la página, protección de contenido y navegación bloqueada; foco, copia y procesos llegan al servidor como señales.</li>"
            "<li><span class='ok'>Entrega</span>: pide confirmación antes de entregar y después impide volver a responder.</li>"
            "</ul>",
        ),
        ("5. Evidencia: recorrido web", galeria(gw, cap_web)),
        ("6. Evidencia: app de escritorio", galeria(ge, cap_esc)),
        (
            "7. Conclusión y cómo reproducir",
            "<p>El flujo crítico del producto funciona de extremo a extremo en la web y en la app de escritorio. Los dos defectos son de la interfaz y tienen causa identificada; se recomienda corregirlos antes del próximo examen real, empezando por D-02, que afecta al enlace de la app.</p>"
            "<pre># web (en el VPS, con el entorno aislado arriba)\ncd pruebas && CAPTURAS=capturas RESULTADOS=e2e-web.json \\\n  uv run --project ../loadtests --with playwright --with pytest python -m pytest e2e/test_e2e_web.py\n"
            "# escritorio (Windows, túnel a :5173, :8080 y :54321)\nnode pruebas/e2e/escritorio.mjs escenario.json e2e-escritorio.json capturas</pre>",
        ),
    ],
}

print(pdf(inf, Path(sys.argv[5])))
