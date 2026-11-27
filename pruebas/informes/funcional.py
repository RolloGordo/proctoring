"""Informe de pruebas funcionales.

    python pruebas/informes/funcional.py <funcional.json> <pdf>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_informe import agrupar, cargar, fecha, tabla_casos  # noqa: E402
from plantilla import kpis, pdf, tabla  # noqa: E402

datos = cargar(Path(sys.argv[1]))
g = agrupar(datos["casos"])
pasan = sum(1 for x in g.values() if not x["fallas"])
fallan = len(g) - pasan
ejec = len(datos["casos"])
ejec_ok = sum(1 for c in datos["casos"] if c["resultado"] == "passed")

inf = {
    "titulo": "Informe de pruebas funcionales",
    "subtitulo": "Cada funcionalidad del sistema comprobada contra su requisito, en el caso normal y de principio a fin: lo que el docente configura es lo que el estudiante recibe.",
    "veredicto": (
        "medio",
        f"<b>{len(g)} funcionalidades probadas: {pasan} cumplen y {fallan} no</b> ({ejec_ok} de {ejec} ejecuciones con variantes). "
        "Las fallas tienen la misma raíz en dos casos: aleatorizar y el pool de preguntas solo funcionan con bancos, no con las preguntas escritas en el editor.",
    ),
    "ficha": [
        ("Proyecto", "Sistema Proctoring (rama develop)"),
        ("Fecha de ejecución", f"{fecha(datos['inicio'])} (duración {datos['fin'] - datos['inicio']:.0f} s)"),
        ("Ejecutado por", "Silva Vega, Héctor (con asistencia de Claude Code)"),
        ("Entorno", "Aislado en el VPS: Supabase local, 2 réplicas de la API, Redis. Cuentas y exámenes creados por la prueba"),
        ("Base de los casos", "Backlog del producto (Notion), SPEC-002/003/004/009 y las opciones que ofrece el formulario del docente"),
        ("Herramientas", "pytest 9 + httpx; archivos QTI 2.1 de muestra de <code>services/api/tests/fixtures/qti</code>"),
    ],
    "secciones": [
        (
            "1. Objetivo y alcance",
            "<p>Las pruebas de caja negra atacan los bordes; las funcionales confirman que <b>cada funcionalidad hace su trabajo completo</b> cuando se usa como se espera. "
            "Se eligieron las que no cubren las otras baterías y que el docente configura en el formulario del examen:</p>"
            + tabla(
                ["Área", "Funcionalidades"],
                [
                    ("Cursos", "crear curso, matricular por correo, curso visible al estudiante con sus exámenes"),
                    ("Preguntas", "bancos asociados al examen, importación QTI 2.1 (6 tipos), vista previa, varias correctas"),
                    ("Calificación", "nota automática sobre 20, tolerancia numérica, puntaje parcial"),
                    ("Configuración del examen", "revisión de la clave tras entregar, código revelado al empezar, aleatorización, pool, intentos, edición y cancelación"),
                    ("Supervisión y decisión", "límite de actividad sospechosa, caso completo del docente, decisión visible al estudiante"),
                ],
            ),
        ),
        (
            "2. Resultados",
            kpis([("funcionalidades", str(len(g))), ("cumplen", str(pasan)), ("no cumplen", str(fallan)), ("ejecuciones", f"{ejec_ok}/{ejec}")])
            + tabla_casos(g, etiqueta="Funcionalidad"),
        ),
        (
            "3. Defectos encontrados",
            "<h3>F-01 · «Preguntas aleatorias» no tiene efecto con preguntas propias (RF-09) · severidad alta</h3>"
            "<p><b>Qué pasa:</b> un examen con 10 preguntas escritas en el editor y <code>shuffle_questions</code> activado (es el <b>valor por defecto</b>) entrega a los 4 estudiantes el mismo orden. "
            "<b>Causa:</b> <code>application/exam_questions.py</code> solo sortea cuando el examen tiene bancos asociados; sin bancos devuelve las preguntas en su orden. "
            "<b>Riesgo:</b> el docente cree que cada estudiante ve otro orden, y es justo una de las medidas contra la copia entre compañeros. "
            "<b>Con bancos funciona</b> (RF-09b). <b>Responsable:</b> Héctor (API). <b>Corrección propuesta:</b> pasar también las preguntas propias por <code>draw_questions</code> con la misma semilla por matrícula, "
            "que ya es determinista y la usa la calificación.</p>"
            "<h3>F-02 · El pool de preguntas no tiene efecto con preguntas propias (RF-10) · severidad media</h3>"
            "<p><b>Qué pasa:</b> con <code>question_pool_size = 3</code> sobre 8 preguntas propias, el estudiante recibe las 8. La misma causa que F-01. Con bancos funciona (RF-10b). "
            "Hasta corregirlo, la API debería rechazar un pool en un examen sin bancos, o el formulario no ofrecerlo, para no prometer algo que no ocurre.</p>"
            "<h3>F-03 · La vista previa de la importación QTI no muestra nada (RF-05b) · severidad baja</h3>"
            "<p><b>Qué pasa:</b> con <code>dry_run=true</code> la respuesta trae <code>imported_count: 0</code> y la lista vacía, aunque el mismo archivo importado de verdad produce 1 pregunta. "
            "<b>Causa:</b> <code>application/use_cases/import_qti.py</code> devuelve <code>imported=()</code> en el modo de prueba, en vez de las preguntas analizadas que su propio docstring promete. "
            "Sí cumple que no guarda nada (RF-05). <b>Responsable:</b> Pierreluiggi (importación QTI).</p>",
        ),
        (
            "4. Lo que se confirmó",
            "<ul>"
            "<li><span class='ok'>Calificación</span>: 20/20 todo bien, 0 todo mal; la numérica acepta su tolerancia (42,4 con ±0,5) y fuera de ella no puntúa (10/20 con la numérica mal); "
            "en varias correctas, solo marcar exactamente las correctas da el puntaje completo.</li>"
            "<li><span class='ok'>Clave tras entregar</span>: solo con las tres condiciones (habilitada, entregó, examen terminado para todos). Antes de que termine, 403: nadie la recibe a los cinco minutos y se la pasa a otro.</li>"
            "<li><span class='ok'>Código al empezar</span>: oculto incluso para el docente antes de la hora.</li>"
            "<li><span class='ok'>QTI 2.1</span>: los seis tipos (opción múltiple, V/F, numérica, numérica con tolerancia, completar, desarrollo) se importan con su enunciado; un XML que no es QTI da 400 con mensaje.</li>"
            "<li><span class='ok'>Límite de actividad</span>: al pasarlo, el docente ve al estudiante «sobre el límite», y el estudiante sigue pudiendo entregar.</li>"
            "<li><span class='ok'>Cursos, intentos, edición, decisión visible</span>: funcionan como se describen.</li></ul>",
        ),
        (
            "5. Conclusión y cómo reproducir",
            "<p>El núcleo funcional (calificar, revisar, supervisar y decidir) cumple. Los defectos están en la configuración del examen: F-01 es el más importante porque viene activado por defecto "
            "y el docente no tiene forma de notar que no se aplica. Se recomienda corregirlo antes del próximo examen real.</p>"
            "<pre>cd pruebas && RESULTADOS=funcional.json uv run --project ../loadtests --with pytest python -m pytest funcional</pre>",
        ),
    ],
}

print(pdf(inf, Path(sys.argv[2])))
