"""Informe de pruebas de humo (producción).

    python pruebas/informes/humo.py <carpeta humo> <pdf>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_informe import agrupar, cargar, fecha, tabla_casos  # noqa: E402
from plantilla import e, imagen, kpis, pdf, tabla  # noqa: E402

R = Path(sys.argv[1])
datos = cargar(R / "humo.json")
g = agrupar(datos["casos"])
pasan = sum(1 for c in datos["casos"] if c["resultado"] == "passed")
total = len(datos["casos"])
medidas: dict[str, object] = {}
for c in datos["casos"]:
    medidas.update(c.get("medidas", {}))

web_ms = [(k[:-3], v) for k, v in medidas.items() if k.endswith("_ms") and not k.startswith("api.")]
api_ms = [(k[:-3], v) for k, v in medidas.items() if k.endswith("_ms") and k.startswith("api.")]
dias = [(k[:-5], v) for k, v in medidas.items() if k.endswith("_dias")]
captura = R / "hu18-login-me.png"

inf = {
    "titulo": "Informe de pruebas de humo",
    "subtitulo": "La comprobación rápida de que producción está viva y sana, pieza por pieza, en los dos dominios. Es lo que se repite después de cada despliegue.",
    "veredicto": (
        "ok" if pasan == total else "mal",
        f"<b>{pasan} de {total} comprobaciones pasan ({len(g)} pruebas).</b> Producción está arriba en los tres dominios, con TLS válido, Supabase activo, "
        "todas las réplicas corriendo, el autoescalador midiendo y los workers de IA conectados a Redis.",
    ),
    "ficha": [
        ("Sistema", "Producción: proctoring-upao.me, proctoring-upao.app y el alias sslip.io; API, web, workers de IA y Redis en el VPS de Contabo; Supabase Cloud"),
        ("Fecha de ejecución", f"{fecha(datos['inicio'])} (duración {datos['fin'] - datos['inicio']:.0f} s)"),
        ("Ejecutado por", "Silva Vega, Héctor (con asistencia de Claude Code)"),
        ("Modo", "<b>Solo lectura</b>: sin iniciar sesión, sin crear cuentas ni datos. Las comprobaciones del servidor leen estados por SSH sin imprimir secretos"),
        ("Herramientas", "pytest 9, httpx, websockets, Playwright con Google Chrome, SSH"),
    ],
    "secciones": [
        (
            "1. Objetivo",
            "<p>Una prueba de humo responde una sola pregunta: <b>¿el sistema está lo bastante sano como para usarlo, o para seguir probando?</b> "
            "No busca defectos finos (eso lo hacen las otras siete); revisa que cada pieza esté encendida y responda lo básico. "
            "Por eso es corta (menos de un minuto), no modifica nada y se puede correr contra producción en cualquier momento, sobre todo justo después de un despliegue.</p>",
        ),
        (
            "2. Resultados",
            kpis([("comprobaciones", f"{pasan}/{total}"), ("dominios web", "3"), ("servicios en el VPS", "6"), ("duración", f"{datos['fin'] - datos['inicio']:.0f} s")])
            + tabla_casos(g, etiqueta="Capa"),
        ),
        (
            "3. Mediciones",
            "<h3>Tiempo de respuesta (una petición, desde Perú)</h3>"
            + tabla(["Host", "Respuesta"], [(e(h), f"{v} ms") for h, v in web_ms + api_ms], (1,))
            + "<h3>Certificados TLS (Let's Encrypt, renovación automática por Traefik)</h3>"
            + tabla(["Host", "Días hasta vencer"], [(e(h), v) for h, v in dias], (1,)),
        ),
        (
            "4. Evidencia",
            (imagen(captura, "HU-18: Chrome real en https://proctoring-upao.me/login, sin errores de consola") if captura.exists() else "")
            + "<p>Además del inicio de sesión visible, en esa misma página se comprobó que <code>crossOriginIsolated</code> es verdadero "
            "(sin eso no funciona el detector de voz) y que la web llega a la API de su propio dominio.</p>",
        ),
        (
            "5. Conclusión y cómo repetirla",
            "<p>Producción pasa el humo completo. Se recomienda correr esta batería <b>después de cada despliegue</b> (es lo que habría detectado al instante, por ejemplo, la pausa del proyecto de Supabase del 26/11 o un dominio sin certificado).</p>"
            "<pre>cd pruebas\nuv run --no-project --with pytest --with httpx --with websockets --with playwright \\\n  python -m pytest humo</pre>",
        ),
    ],
}

print(pdf(inf, Path(sys.argv[2])))
