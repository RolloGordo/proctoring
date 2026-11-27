"""Informe de pruebas exploratorias con agentes de IA.

    python pruebas/informes/agentes.py <carpeta con agente-*/hallazgos.json> <verificacion.json> <pdf>

`verificacion.json` es la reproducción independiente de cada hallazgo por quien
coordina la prueba: {"<id>": {"estado": "confirmado|no reproducido|ya conocido|no es defecto", "nota": "..."}}.
Un hallazgo entra al informe con lo que dijo el agente **y** con lo que dio su
reproducción: un agente puede equivocarse, y el informe no lo esconde.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plantilla import e, imagen, kpis, pdf, tabla  # noqa: E402

BASE = Path(sys.argv[1])
VERIF: dict[str, dict[str, str]] = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

PERFILES = [
    ("agente-docente", "Docente nuevo", "Usa la plataforma por primera vez para preparar y vigilar un examen: busca errores funcionales, mensajes confusos y problemas de usabilidad y accesibilidad."),
    ("agente-tramposo", "Estudiante que intenta hacer trampa", "Intenta burlar la supervisión y las reglas del examen desde el navegador: conseguir respuestas, apagar las señales, rendir sin ser admitido."),
    ("agente-atacante", "Atacante con cuenta de estudiante", "Busca vulnerabilidades en la API, la base (RLS), Storage, Realtime y los tokens, con peticiones directas."),
]
SEV_ORDEN = {"crítica": 0, "alta": 1, "media": 2, "baja": 3}


def cargar(carpeta: str) -> dict[str, Any] | None:
    p = BASE / carpeta / "hallazgos.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


datos = {c: cargar(c) for c, _, _ in PERFILES}
todos: list[tuple[str, dict[str, Any]]] = [(c, h) for c, d in datos.items() if d for h in d.get("hallazgos", [])]
confirmados = [(c, h) for c, h in todos if VERIF.get(h["id"], {}).get("estado") == "confirmado"]
pruebas_hechas = sum(len(d.get("intentos", d.get("pruebas", d.get("flujos_explorados", [])))) for d in datos.values() if d)


def estado_v(hid: str) -> str:
    v = VERIF.get(hid, {}).get("estado", "sin verificar")
    clase = {"confirmado": "mal", "no reproducido": "medio", "ya conocido": "medio", "no es defecto": "ok"}.get(v, "medio")
    return f'<span class="{clase}">{e(v)}</span>'


def detalle(h: dict[str, Any], carpeta: str) -> str:
    pasos = "".join(f"<li>{e(p)}</li>" for p in h.get("pasos", []))
    extra = ""
    for k, t in (("impacto", "Impacto"), ("recomendacion", "Recomendación"), ("cwe", "CWE")):
        if h.get(k):
            extra += f"<p><b>{t}:</b> {e(h[k])}</p>"
    nota = VERIF.get(h["id"], {}).get("nota", "")
    imgs = ""
    for ruta in h.get("evidencia", [])[:2]:
        p = Path(ruta)
        if not p.is_absolute():
            p = BASE / carpeta / p
        if p.exists() and p.suffix.lower() == ".png":
            imgs += imagen(p, f"{h['id']}: evidencia del agente")
    return (
        f"<h3>{e(h['id'])} · {e(h['titulo'])} · severidad {e(h.get('severidad', '—'))}</h3>"
        f"<p><b>Reproducción independiente:</b> {estado_v(h['id'])}{(' — ' + e(nota)) if nota else ''}</p>"
        f"<ol>{pasos}</ol><p><b>Esperado:</b> {e(h.get('esperado', ''))}</p><p><b>Observado:</b> {e(h.get('observado', ''))}</p>{extra}{imgs}"
    )


secciones_perfil = []
for carpeta, nombre, mision in PERFILES:
    d = datos[carpeta]
    if not d:
        secciones_perfil.append((f"Agente: {nombre}", "<p>El agente no entregó resultados.</p>"))
        continue
    cuerpo = f"<p><b>Misión:</b> {e(mision)}</p><p><b>Duración:</b> {e(d.get('minutos', '—'))} minutos.</p>"
    if d.get("flujos_explorados"):
        cuerpo += "<p><b>Flujos explorados:</b> " + e(", ".join(d["flujos_explorados"])) + "</p>"
    lista = d.get("intentos") or d.get("pruebas")
    if lista:
        cuerpo += "<h3>Todo lo que intentó</h3>" + tabla(
            ["ID", "Área / intento", "Resultado", "Detalle"],
            [
                (e(x.get("id", "")), e(x.get("intento") or f"{x.get('area', '')}: {x.get('prueba', '')}"), e(x.get("resultado", "")), e(str(x.get("detalle", ""))[:300]))
                for x in lista
            ],
        )
    hs = sorted(d.get("hallazgos", []), key=lambda h: SEV_ORDEN.get(h.get("severidad", "baja"), 9))
    cuerpo += "<h3>Hallazgos</h3>" + ("".join(detalle(h, carpeta) for h in hs) if hs else "<p>Ninguno.</p>")
    if d.get("lo_que_funciono_bien"):
        cuerpo += "<h3>Lo que funcionó bien</h3><ul>" + "".join(f"<li>{e(x)}</li>" for x in d["lo_que_funciono_bien"]) + "</ul>"
    secciones_perfil.append((f"Agente: {nombre}", cuerpo))

resumen_filas = [
    (e(h["id"]), e(h["titulo"]), e(h.get("severidad", "—")), estado_v(h["id"]))
    for c, h in sorted(todos, key=lambda x: SEV_ORDEN.get(x[1].get("severidad", "baja"), 9))
]

inf = {
    "titulo": "Informe de pruebas exploratorias con agentes de IA",
    "subtitulo": "Tres agentes de IA autónomos, cada uno con un perfil y sin guion fijo, usaron el sistema real y reportaron lo que encontraron. Cada hallazgo se reprodujo de forma independiente antes de entrar a este informe.",
    "veredicto": (
        "mal" if any(h.get("severidad") in ("crítica", "alta") for _, h in confirmados) else "medio" if confirmados else "ok",
        f"<b>{len(todos)} hallazgos reportados por los agentes, {len(confirmados)} confirmados al reproducirlos.</b> Entre los tres hicieron {pruebas_hechas} intentos o recorridos documentados.",
    ),
    "ficha": [
        ("Sistema", "Entorno aislado en el VPS: web, 2 réplicas de la API, Redis, workers de IA y Supabase local, por túnel SSH"),
        ("Fecha", "27/11/2026"),
        ("Coordinó", "Silva Vega, Héctor (con asistencia de Claude Code, que lanzó y supervisó a los agentes)"),
        ("Agentes", "3 agentes de IA (Claude) en paralelo, cada uno con su navegador o cliente HTTP, sus cuentas de prueba y su carpeta de trabajo"),
        ("Límites dados", "solo el entorno aislado (nunca producción), sin tocar el repositorio, sin denegación de servicio, unos 30 minutos cada uno"),
    ],
    "secciones": [
        (
            "1. Qué es una prueba con agentes y por qué se hizo",
            "<p>Las otras baterías comprueban lo que alguien <b>pensó</b> probar. Una prueba exploratoria busca lo que nadie pensó: alguien usa el sistema con un objetivo y va decidiendo qué hacer según lo que ve. "
            "Aquí ese alguien es un agente de IA con un perfil. El agente escribe y ejecuta sus propios scripts (Playwright para el navegador, httpx para la API), mira sus capturas, "
            "decide el siguiente paso y documenta lo que encuentra.</p>"
            "<p>Como un agente puede equivocarse, <b>ningún hallazgo se da por bueno sin reproducirlo</b>: cada uno se repitió por separado y su estado está al lado (confirmado, no reproducido, ya conocido o no es defecto). "
            "A cada agente se le dio la lista de defectos ya encontrados por las otras baterías, para que buscara otros.</p>"
            + tabla(["Agente", "Perfil"], [(e(n), e(m)) for _, n, m in PERFILES]),
        ),
        (
            "2. Resumen de hallazgos",
            kpis([("reportados", str(len(todos))), ("confirmados", str(len(confirmados))), ("altos o críticos confirmados", str(sum(1 for _, h in confirmados if h.get("severidad") in ("crítica", "alta")))), ("intentos documentados", str(pruebas_hechas))])
            + (tabla(["ID", "Hallazgo", "Severidad del agente", "Reproducción"], resumen_filas) if resumen_filas else "<p>Ningún agente reportó hallazgos.</p>"),
        ),
        *[(f"{i + 3}. {t}", c) for i, (t, c) in enumerate(secciones_perfil)],
        (
            f"{len(secciones_perfil) + 3}. Conclusión",
            "<p>Las pruebas con agentes complementan a las demás: no reemplazan una batería repetible, pero encuentran caminos que nadie escribió. "
            "Los hallazgos confirmados se suman a la lista de defectos del proyecto con su responsable; los no reproducidos quedan documentados como tales.</p>",
        ),
    ],
}

print(pdf(inf, Path(sys.argv[3])))
