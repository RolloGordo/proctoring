"""Informe de pruebas de caja negra.

    python pruebas/informes/caja_negra.py <caja-negra.json> <pdf de salida>
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_informe import agrupar, cargar, fecha, tabla_casos  # noqa: E402
from plantilla import kpis, pdf, tabla  # noqa: E402

datos = cargar(Path(sys.argv[1]))
casos = datos["casos"]
g = agrupar(casos)
pasan = sum(1 for c in casos if c["resultado"] == "passed")
fallan = len(casos) - pasan
tecnicas = Counter(x["tecnica"] for x in g.values())
variantes_por_tecnica = Counter(c["tecnica"] for c in casos)
NOMBRES = {
    "PE": "Particiones de equivalencia",
    "VL": "Valores límite",
    "TD": "Tabla de decisión",
    "TE": "Transición de estados",
    "AE": "Adivinación de errores",
}

BLOQUES = [
    ("SPEC-001 Autenticación y roles", "CN-01", "CN-08"),
    ("SPEC-002 Sesiones: creación y límites", "CN-09", "CN-13"),
    ("SPEC-002 Ingreso con código y consentimiento", "CN-14", "CN-19"),
    ("SPEC-004 Rendición (estados del estudiante)", "CN-20", "CN-24"),
    ("Preguntas: límites", "CN-25", "CN-26"),
    ("SPEC-006/007/008 Señales: módulos, severidad y contrato", "CN-27", "CN-32"),
    ("SPEC-009 Riesgo, alertas y decisión", "CN-33", "CN-38"),
    ("Robustez general", "CN-39", "CN-43"),
]


def en_bloque(ini: str, fin: str):  # type: ignore[no-untyped-def]
    from collections import OrderedDict

    return OrderedDict((k, v) for k, v in g.items() if ini <= k <= fin)


detalle = "".join(f"<h3>{t}</h3>" + tabla_casos(en_bloque(a, b)) for t, a, b in BLOQUES)

inf = {
    "titulo": "Informe de pruebas de caja negra",
    "subtitulo": "La API probada desde fuera, contra su especificación: qué entra, qué sale y qué se rechaza, sin mirar cómo está hecha por dentro.",
    "veredicto": (
        "ok" if fallan == 0 else "mal",
        f"<b>{len(g)} casos de prueba ({len(casos)} con sus variantes): {pasan} pasan y {fallan} fallan.</b> "
        "Seis expectativas iniciales no coincidieron con la API; al revisarlas, ninguna era un defecto (ver sección 5).",
    ),
    "ficha": [
        ("Proyecto", "Sistema Proctoring (repositorio RolloGordo/proctoring, rama develop)"),
        ("Fecha de ejecución", f"{fecha(datos['inicio'])} (duración {datos['fin'] - datos['inicio']:.0f} s)"),
        ("Ejecutado por", "Silva Vega, Héctor (con asistencia de Claude Code)"),
        ("Objeto de prueba", "API principal v0.1.0 (FastAPI), la misma imagen que corre en producción"),
        ("Entorno", "Aislado en el VPS: Supabase local con las 23 migraciones, 2 réplicas de la API detrás de nginx, Redis, ENV=production y autenticación activada"),
        ("Herramientas", "pytest 9 + httpx; cuentas reales en Auth local con tokens ES256 firmados como los de Supabase"),
    ],
    "secciones": [
        (
            "1. Objetivo y alcance",
            "<p>Verificar que la API se comporta como dicen sus especificaciones (<code>specs/SPEC-001…009</code>), su contrato publicado (OpenAPI) y las reglas del producto (<code>CLAUDE.md</code>), "
            "tratándola como una caja cerrada: cada caso manda una petición HTTP real y compara la respuesta con lo esperado. No se usa ningún doble: hay base de datos, autenticación, "
            "límite de peticiones en Redis y balanceador, como en producción.</p>"
            "<p>Las pruebas crean sus propias cuentas y exámenes en el entorno aislado. <b>Nunca se tocó la base de producción.</b></p>",
        ),
        (
            "2. Técnicas aplicadas",
            tabla(
                ["Técnica", "Qué se busca", "Casos", "Variantes"],
                [
                    (NOMBRES[k], {
                        "PE": "Un representante por clase válida e inválida (rol, preset, tipo de decisión, formato del evento)",
                        "VL": "El límite, uno por debajo y uno por encima (longitudes, duraciones, puntajes, umbrales de severidad, intentos)",
                        "TD": "Combinaciones de condiciones (módulo encendido/apagado × tipo de señal; consentimiento)",
                        "TE": "Paso entre estados del estudiante (inscrito, en espera, admitido, entregado) y del examen (vigente, terminado, cancelado)",
                        "AE": "Entradas que suelen romper una API: JSON roto, UUID mal formado, inyección SQL, HTML, suplantación",
                    }[k], tecnicas[k], variantes_por_tecnica[k])
                    for k in ("PE", "VL", "TD", "TE", "AE")
                ],
                (2, 3),
            ),
        ),
        (
            "3. Resultados",
            kpis([("casos de prueba", str(len(g))), ("ejecuciones con variantes", str(len(casos))), ("pasan", str(pasan)), ("fallan", str(fallan))])
            + "<p>Los valores límite que se comprobaron, todos con su vecino inválido:</p><ul>"
            "<li>Título 1 a 200 caracteres · duración 1 a 600 min · tolerancia 0 a 120 min · intentos 1 a 10.</li>"
            "<li>Código de acceso 4 a 16 caracteres · 10 intentos de código por minuto (el 11.º recibe 429).</li>"
            "<li>1 a 50 preguntas por petición · puntaje 0 a 100 · 1 a 200 respuestas por lote.</li>"
            "<li>Severidad: pérdida de foco 4.999/5.000 ms y 29.999/30.000 ms; rostro ausente 4.999/5.000 y 14.999/15.000 ms; mirada 9.999/10.000 ms.</li>"
            "<li>Justificación de la decisión: 9 caracteres se rechaza, 10 se acepta, 2.000 se acepta, 2.001 se rechaza.</li></ul>",
        ),
        ("4. Detalle por requisito", detalle),
        (
            "5. Expectativas que no coincidieron (y por qué no eran defectos)",
            "<p>En la primera corrida 6 de 102 ejecuciones fallaron. Se revisó cada respuesta real antes de tocar la prueba:</p>"
            + tabla(
                ["Caso", "Se esperaba", "La API respondió", "Conclusión"],
                [
                    ("CN-14 (×2), CN-19", "404 para un código que no existe", "400 con «No hay ningún examen con ese código. Revísalo con tu docente.»", "Contrato válido: el mensaje es claro y la SPEC no fija el código. Se ajustó la prueba."),
                    ("CN-33", "Desglose por señal en el resumen del examen", "El resumen trae puntaje, nivel y señal principal; el desglose está en el caso del estudiante", "Cumple SPEC-009 CA-1 en <code>/students/{id}/case</code>: se comprueba que el total es la suma de lo que aporta cada señal."),
                    ("CN-40", "404 para un examen inexistente", "403, igual que para uno ajeno", "Decisión de seguridad: no revela si un examen existe. Se prueba que ambas respuestas son idénticas."),
                    ("CN-41", "404 o 422 a una inyección SQL", "400 «no existe»", "Correcto: se trató como texto; nunca hubo 500 ni se devolvió un examen."),
                ],
            ),
        ),
        (
            "6. Hallazgos",
            "<ul>"
            "<li><span class='ok'>Autenticación y roles</span>: sin token, token basura, <code>alg: none</code> o vencido dan 401 con mensaje; un estudiante no entra a rutas del docente (403); un docente no ve exámenes ajenos.</li>"
            "<li><span class='ok'>Nunca anula solo</span>: con 20 señales altas seguidas no aparece ninguna decisión y el estudiante puede entregar (SPEC-009 CA-5).</li>"
            "<li><span class='ok'>Eventos inmutables</span>: PUT y DELETE sobre <code>/events</code> responden 405 (SPEC-009 CA-6).</li>"
            "<li><span class='ok'>Módulos apagados</span>: en un examen personalizado, las señales de módulos no elegidos se rechazan con 400 y las elegidas se aceptan.</li>"
            "<li><span class='ok'>Preguntas sin clave</span>: el estudiante nunca recibe <code>is_correct</code> ni la respuesta numérica correcta.</li>"
            "<li><span class='ok'>Robustez</span>: ningún caso de entrada maliciosa o mal formada produjo un 500.</li>"
            "<li><span class='medio'>Observación</span>: un código inexistente devuelve 400 y no 404. No es un error, pero conviene documentarlo en el contrato para quien integre.</li>"
            "</ul>",
        ),
        (
            "7. Conclusión y cómo reproducir",
            f"<p>La API cumple su especificación en los {len(g)} casos diseñados. Las reglas que más importan al producto (roles, nunca anular, inmutabilidad, módulos, umbrales de severidad, justificación) se verificaron en sus límites exactos.</p>"
            "<pre># con el entorno aislado arriba (loadtests/README.md)\ncd pruebas\nRESULTADOS=caja-negra.json uv run --project ../loadtests --with pytest python -m pytest caja_negra</pre>",
        ),
    ],
}

print(pdf(inf, Path(sys.argv[2])))
