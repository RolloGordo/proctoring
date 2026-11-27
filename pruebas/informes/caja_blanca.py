"""Informe de pruebas de caja blanca.

    python pruebas/informes/caja_blanca.py <carpeta de resultados> <pdf>

Lee: caja-blanca.json (casos), cb-cov.json (cobertura por función), radon-cc.json
(complejidad) y mutmut.json (resumen de mutación).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_informe import agrupar, cargar, fecha, tabla_casos  # noqa: E402
from plantilla import e, kpis, pdf, tabla  # noqa: E402

R = Path(sys.argv[1])
datos = cargar(R / "caja-blanca.json")
g = agrupar(datos["casos"])
ejec = len(datos["casos"])
ejec_ok = sum(1 for c in datos["casos"] if c["resultado"] == "passed")
pasan = sum(1 for x in g.values() if not x["fallas"])

# Complejidad ciclomática de todo el backend.
radon = json.loads((R / "radon-cc.json").read_text(encoding="utf-8"))
funciones = [
    (b["complexity"], b["rank"], f.replace("\\", "/").split("proctoring_api/")[-1], b["name"])
    for f, bs in radon.items()
    for b in bs
    if b.get("type") != "class"
]
rangos = Counter(r for _, r, _, _ in funciones)
media = sum(c for c, *_ in funciones) / len(funciones)

# Cobertura por función crítica.
cov = json.loads((R / "cb-cov.json").read_text(encoding="utf-8"))
OBJETIVO = {
    "severity.py": ["default_severity"],
    "risk.py": ["risk_level", "assess_risk"],
    "event.py": ["one_per_episode", "ProctoringEvent.episode_id"],
    "question_bank.py": ["draw_questions"],
    "grading.py": ["ExamScore.on_scale", "normalize_text", "grade_answer", "score_exam", "_is_correct"],
    "rate_limit.py": ["VentanaDeslizante.admite"],
}
cc_por_nombre = {
    (Path(f.replace("\\", "/")).name, (b["classname"] + "." if b.get("classname") else "") + b["name"]): b["complexity"]
    for f, bs in radon.items()
    for b in bs
    if b.get("type") != "class"
}
filas_cov = []
for f, v in cov["files"].items():
    base = f.replace("\\", "/").split("/")[-1]
    for fn in OBJETIVO.get(base, []):
        s = v.get("functions", {}).get(fn, {}).get("summary")
        if not s:
            continue
        faltan = v["functions"][fn].get("missing_lines") or []
        filas_cov.append(
            (
                f"<code>{e(base)}</code>",
                f"<code>{e(fn)}</code>",
                cc_por_nombre.get((base, fn), "—"),
                f"{s['percent_covered']:.0f} %",
                f"{s.get('covered_branches', 0)}/{s.get('num_branches', 0)}",
                ", ".join(map(str, faltan)) or "—",
            )
        )

mut = json.loads((R / "mutmut.json").read_text(encoding="utf-8")) if (R / "mutmut.json").exists() else None


def seccion_mutacion() -> str:
    if not mut:
        return "<p>No se pudo completar la corrida de mutación.</p>"
    filas = [
        (f"<code>{e(a)}</code>", d["total"], d["killed"], d["survived"], d.get("otros", 0), f"{100 * d['killed'] / max(d['total'] - d.get('otros', 0), 1):.1f} %")
        for a, d in mut["por_archivo"].items()
    ]
    t = mut["total"]
    sobrevivientes = "".join(f"<li><code>{e(s['mutante'])}</code>: {s['explicacion']}</li>" for s in mut.get("sobrevivientes_explicados", []))
    return (
        "<p>Una prueba de mutación cambia el código a propósito (un <code>&gt;=</code> por <code>&gt;</code>, un <code>25</code> por <code>26</code>, un <code>and</code> por <code>or</code>…) "
        "y vuelve a correr las pruebas. Si alguna falla, el mutante quedó <b>eliminado</b>: las pruebas protegen esa línea. Si todas pasan, <b>sobrevivió</b>: "
        "ese cambio de comportamiento pasaría inadvertido. Es la medida más exigente de la calidad de una batería, mucho más que la cobertura.</p>"
        + kpis([("mutantes generados", str(t["total"])), ("eliminados", str(t["killed"])), ("sobrevivientes", str(t["survived"])), ("puntaje de mutación", f"{100 * t['killed'] / max(t['total'] - t.get('otros', 0), 1):.1f} %")])
        + tabla(["Módulo", "Mutantes", "Eliminados", "Sobreviven", "Sin cobertura / tiempo", "Puntaje"], filas, (1, 2, 3, 4, 5))
        + (f"<h3>Qué sobrevivió y por qué</h3><ul>{sobrevivientes}</ul>" if sobrevivientes else "")
        + (
            f"<p><b>Iteración:</b> la primera corrida dejó {mut['primera_corrida']['survived']} sobrevivientes ({100 * mut['primera_corrida']['killed'] / mut['primera_corrida']['total']:.1f} %). "
            "Cinco eran huecos reales y se cerraron con los casos CB-34 a CB-37 (pool de 1, desempate con posiciones repetidas, tildes que no son de la ñ, corrección por pregunta). "
            f"La segunda corrida, la de esta tabla, deja {t['survived']}.</p>"
        )
        + f"<p>Herramienta: mutmut {e(mut['version'])} en Linux, sobre las pruebas unitarias del dominio más las de caja blanca de este informe. Se mutaron los cuatro módulos que deciden sobre una persona: severidad, riesgo, calificación y sorteo de preguntas.</p>"
    )


peores = sorted(funciones, reverse=True)[:10]

inf = {
    "titulo": "Informe de pruebas de caja blanca",
    "subtitulo": "Pruebas diseñadas mirando el código: complejidad ciclomática, un caso por camino independiente de las reglas críticas, cobertura de ramas y pruebas de mutación.",
    "veredicto": (
        "medio" if ejec_ok < ejec else "ok",
        f"<b>{len(g)} casos de caja blanca ({ejec} ejecuciones): {ejec_ok} pasan.</b> Cubren el 100 % de las ramas alcanzables de las reglas que deciden sobre una persona. "
        "El análisis del código encontró un defecto que ninguna prueba de comportamiento había visto: una rama muerta en el límite de peticiones.",
    ),
    "ficha": [
        ("Proyecto", "Sistema Proctoring · API principal (rama develop)"),
        ("Fecha de ejecución", fecha(datos["inicio"])),
        ("Ejecutado por", "Silva Vega, Héctor (con asistencia de Claude Code)"),
        ("Herramientas", "pytest 9 + coverage.py (ramas, por función), radon (complejidad ciclomática), mutmut 3.3 (mutación, en Linux)"),
        ("Alcance", f"{len(funciones)} funciones del backend para la complejidad; 12 funciones críticas para caminos, ramas y mutación"),
    ],
    "secciones": [
        (
            "1. Objetivo y método",
            "<p>La caja negra pregunta «¿hace lo que dice la especificación?». La caja blanca pregunta «<b>¿se ejecutó y se comprobó cada camino del código?</b>». Método:</p><ol>"
            "<li><b>Complejidad ciclomática</b> V(G) = decisiones + 1 de cada función, para saber cuántos caminos independientes tiene y dónde está el riesgo.</li>"
            "<li><b>Caminos básicos</b>: un caso por camino de las funciones críticas, con cada umbral probado en su valor exacto y en el anterior.</li>"
            "<li><b>Cobertura de condiciones y bucles</b>: cada sub-condición de un <code>and</code> por separado; cada bucle con 0, 1 y muchas vueltas.</li>"
            "<li><b>Cobertura de ramas</b> por función, para ver qué quedó sin recorrer y por qué.</li>"
            "<li><b>Pruebas de mutación</b>, para medir si las pruebas detectan cambios reales en el código.</li></ol>"
            "<p>Funciones elegidas por lo que deciden sobre una persona: la severidad de cada señal, el riesgo, qué informes cuentan como un episodio, qué preguntas recibe cada estudiante, cómo se califica y el límite de peticiones.</p>",
        ),
        (
            "2. Complejidad ciclomática del backend",
            kpis([("funciones analizadas", str(len(funciones))), ("complejidad media", f"{media:.1f}".replace(".", ",")), ("rango A (1–5)", f"{100 * rangos['A'] / len(funciones):.0f} %"), ("rango D o F (> 20)", str(rangos["D"] + rangos["F"]))])
            + tabla(["Rango (radon)", "V(G)", "Funciones", "Lectura"], [
                ("A", "1–5", rangos["A"], "simple, bajo riesgo"),
                ("B", "6–10", rangos["B"], "bien estructurada"),
                ("C", "11–20", rangos["C"], "compleja: necesita pruebas por camino"),
                ("D", "21–30", rangos["D"], "muy compleja: candidata a dividir"),
                ("F", "> 40", rangos["F"], "difícil de probar por completo"),
            ], (2,))
            + "<h3>Las diez funciones más complejas</h3>"
            + tabla(["V(G)", "Rango", "Archivo", "Función"], [(c, r, f"<code>{e(f)}</code>", f"<code>{e(n)}</code>") for c, r, f, n in peores], (0,))
            + "<p>La más compleja, con diferencia, es <code>_parse_item</code> del importador QTI (V(G) = 80): un solo método decide cada tipo de pregunta QTI. "
            "Se recomienda dividirlo por tipo de interacción. <code>default_severity</code> (17) y <code>_is_correct</code> (16) son complejas por diseño (una rama por tipo) y por eso se probaron camino por camino.</p>",
        ),
        ("3. Casos por camino", tabla_casos(g)),
        (
            "4. Cobertura de ramas de las funciones críticas",
            tabla(["Archivo", "Función", "V(G)", "Líneas", "Ramas", "Líneas sin ejecutar"], filas_cov, (2, 3, 4))
            + "<p>Las tres ramas que quedan sin recorrer se revisaron una por una:</p><ul>"
            "<li><code>default_severity</code>: la salida implícita del <code>match</code> cuando ningún caso coincide. Es <b>inalcanzable</b>: el enum está completo (lo prueba CB-02) y mypy lo verifica.</li>"
            "<li><code>_is_correct</code>, línea 163 (<code>return False</code> final): solo se llegaría con un tipo de pregunta sin regla; el único (desarrollo) se desvía antes. Inalcanzable hoy; está bien como defensa.</li>"
            "<li><code>VentanaDeslizante.admite</code>, línea 115: <b>no es inalcanzable por diseño sino por un error</b> (hallazgo CB-33).</li></ul>",
        ),
        ("5. Pruebas de mutación", seccion_mutacion()),
        (
            "6. Hallazgos",
            "<h3>CB-33 · El límite de peticiones en memoria nunca libera las claves (código muerto) · severidad baja</h3>"
            "<p>En <code>adapters/inbound/http/rate_limit.py</code>, <code>VentanaDeslizante.admite</code> quiere borrar las claves que se quedan vacías «para que el diccionario no crezca con cada IP», "
            "pero el <code>if not marcas: del …</code> está <b>después</b> de <code>marcas.append(ahora)</code>: la lista nunca está vacía en ese punto y la rama no se ejecuta jamás. "
            "La prueba lo demuestra: tras 500 personas distintas y pasada la ventana, siguen las 501 claves. "
            "<b>Impacto:</b> en producción el límite se cuenta en Redis (<code>RATE_LIMIT_BACKEND=redis</code>) y esta clase solo se usa como respaldo si Redis cae o con una sola réplica; ahí la memoria crece con cada persona o IP distinta mientras el proceso viva. "
            "<b>Corrección:</b> comprobar si quedó vacía justo después de descartar las marcas vencidas y antes de añadir la nueva (o barrer las claves vencidas periódicamente). Responsable: Héctor.</p>"
            "<h3>Recomendaciones</h3><ul><li>Dividir <code>_parse_item</code> (V(G) 80) y <code>ExamSession.with_changes</code> (24).</li>"
            "<li>Añadir a la CI una corrida de mutación sobre <code>domain/</code> en los PR a <code>main</code>, con un umbral mínimo.</li></ul>",
        ),
        (
            "7. Conclusión y cómo reproducir",
            "<p>Las reglas que deciden sobre una persona están probadas camino por camino, con sus umbrales exactos, y sus ramas alcanzables están cubiertas al 100 %. "
            "El valor propio de la caja blanca se vio en CB-33: un error que no cambia ninguna respuesta de la API y que solo aparece leyendo el código.</p>"
            "<pre>cd services/api\nuv run pytest ../../pruebas/caja_blanca --cov=proctoring_api.domain --cov-branch\nuv run --with radon radon cc src/proctoring_api -s -a\nuv run --with mutmut mutmut run      # en Linux, con [tool.mutmut] en pyproject</pre>",
        ),
    ],
}

print(pdf(inf, Path(sys.argv[2])))
