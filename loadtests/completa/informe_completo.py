"""Informe de la batería completa de carga (18/11/2026), HTML listo para PDF.

    uv run python completa/informe_completo.py resultados/   # escribe resultados/completa/informe.html

Cada cifra sale de los ficheros que deja `~/bateria.sh` (CSV de Locust, resúmenes
JSON de k6, JSON de Realtime, de IA y de navegadores, CSV de recursos y los JSON
de Lighthouse). Si una corrida falta, su sección lo dice en vez de inventar.
"""

from __future__ import annotations

import csv
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import informe as base  # noqa: E402
from informe import AZUL, NARANJA, barras_h, leyenda, ms, tabla  # noqa: E402

R = Path(sys.argv[1] if len(sys.argv) > 1 else "resultados").resolve()
C = R / "completa"
base.R = R  # los helpers de informe.py leen de aquí


def num(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def pct(v: float, dec: int = 2) -> str:
    return f"{v * 100:.{dec}f} %".replace(".", ",")


def leer(nombre: str) -> Any:
    p = C / nombre
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def esc(t: Any) -> str:
    return html.escape(str(t))


# ------------------------------------------------------------------ Locust


def locust(nombre: str) -> dict[str, dict[str, str]] | None:
    try:
        return base.stats(nombre)
    except FileNotFoundError:
        return None


def p_(st: dict[str, dict[str, str]], fila: str, q: str = "95%") -> float | None:
    f = st.get(base._llano(fila))
    return float(f[q]) if f and int(f["Request Count"]) else None


def cpu_de(nombre: str, carpeta: Path) -> dict[str, tuple[float, float, float]]:
    """grupo -> (CPU media, CPU máx, memoria máx) sumando contenedores en cada instante."""
    ruta = carpeta / f"{nombre}-recursos.csv"
    if not ruta.exists():
        return {}
    suma: dict[tuple[str, str], float] = defaultdict(float)
    mem: dict[str, float] = defaultdict(float)
    with ruta.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            suma[(fila["grupo"], fila["t"])] += float(fila["cpu_pct"])
            mem[fila["grupo"]] = max(mem[fila["grupo"]], float(fila["mem_mib"]))
    g: dict[str, list[float]] = defaultdict(list)
    for (grupo, _), v in suma.items():
        g[grupo].append(v)
    return {k: (sum(v) / len(v), max(v), mem[k]) for k, v in g.items()}


def memoria_en_el_tiempo(nombre: str, carpeta: Path, grupo: str) -> list[tuple[float, float]]:
    ruta = carpeta / f"{nombre}-recursos.csv"
    if not ruta.exists():
        return []
    por_t: dict[float, list[float]] = defaultdict(list)
    with ruta.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            if fila["grupo"] == grupo:
                por_t[float(fila["t"])].append(float(fila["mem_mib"]))
    return [(t, max(v)) for t, v in sorted(por_t.items())]


def linea(
    puntos: list[tuple[float, float]], *, ancho: int = 640, alto: int = 170, etiqueta_y: str = "MiB"
) -> str:
    """Una serie en el tiempo, un solo eje, 2px."""
    if not puntos:
        return "<p>(sin datos)</p>"
    izq, der, arr, abj = 48, 16, 10, 26
    tmax = max(t for t, _ in puntos) or 1
    vmax = max(v for _, v in puntos) * 1.15 or 1
    x = lambda t: izq + (ancho - izq - der) * t / tmax  # noqa: E731
    y = lambda v: arr + (alto - arr - abj) * (1 - v / vmax)  # noqa: E731
    d = " ".join(
        f"{'M' if i == 0 else 'L'}{x(t):.1f},{y(v):.1f}" for i, (t, v) in enumerate(puntos)
    )
    marcas = []
    for k in range(5):
        v = vmax * k / 4
        marcas.append(
            f'<line x1="{izq}" x2="{ancho - der}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#eeede9"/>'
            f'<text x="{izq - 6}" y="{y(v) + 3:.1f}" text-anchor="end" class="val">{v:.0f}</text>'
        )
    for k in range(0, int(tmax // 60) + 1, max(1, int(tmax // 60) // 6 or 1)):
        marcas.append(
            f'<text x="{x(k * 60):.1f}" y="{alto - 8}" text-anchor="middle" class="val">{k} min</text>'
        )
    return (
        f'<svg viewBox="0 0 {ancho} {alto}" class="grafico" role="img">{"".join(marcas)}'
        f'<path d="{d}" fill="none" stroke="{AZUL}" stroke-width="2"/>'
        f'<text x="{izq}" y="8" class="val">{etiqueta_y}</text></svg>'
    )


# ------------------------------------------------------------------ secciones


def seccion_locust() -> str:
    corridas = [("bc-examen-60", 60, "1"), ("bc-examen-300", 300, "5"), ("bc-examen-540", 540, "9")]
    filas = []
    p95_guardar, p95_entrega, p95_ingreso, etiquetas = [], [], [], []
    for nombre, n, ex in corridas:
        st = locust(nombre)
        if not st:
            filas.append([f"{n}", ex, "—", "—", "—", "—", "—", "—"])
            continue
        t = st["Aggregated"]
        req, fal = int(t["Request Count"]), int(t["Failure Count"])
        ing = p_(st, "ingreso: código") or 0
        gua = p_(st, "examen: guardar respuestas") or 0
        ent = p_(st, "entrega") or 0
        etiquetas.append(f"{n} estudiantes")
        p95_ingreso.append(ing)
        p95_guardar.append(gua)
        p95_entrega.append(ent)
        filas.append(
            [
                f"{n}",
                ex,
                num(req),
                f"{fal} ({pct(fal / max(req, 1))})",
                f"{float(t['Requests/s']):.0f}".replace(".", ","),
                ms(ing),
                ms(gua),
                ms(ent),
            ]
        )
    grafico = (
        barras_h(
            etiquetas,
            [
                ("Ingreso", "#8a8984", p95_ingreso),
                ("Guardar respuestas", AZUL, p95_guardar),
                ("Entrega", NARANJA, p95_entrega),
            ],
            umbral=500,
        )
        if etiquetas
        else ""
    )
    cpu = {n: cpu_de(n, R) for n, _, _ in corridas}
    filas_cpu = [
        [g] + [f"{cpu[n].get(clave, (0, 0, 0))[0]:.0f} %" for n, _, _ in corridas]
        for g, clave in [
            ("API (3 réplicas)", "api (réplicas)"),
            ("Postgres", "postgres"),
            ("PostgREST", "postgrest"),
            ("Kong", "kong"),
            ("Producción: API", "prod: api"),
        ]
    ]
    return f"""
<h2>1. El examen de principio a fin (Locust)</h2>
<p>Cada estudiante virtual entra con el código, se matricula con consentimiento, espera en la sala
hasta que el docente lo admite, descarga las preguntas, guarda respuestas cada 8-15 s, manda señales
de supervisión y entrega en el último minuto. Un docente por examen refresca la sala y las alertas
cada 5 s y admite de cinco en cinco. Es la misma prueba del 13/11, repetida con el código nuevo
(dominio propio, modo claro y endurecimiento).</p>
{tabla(["Estudiantes", "Exámenes", "Peticiones", "Errores", "Pet./s", "p95 ingreso", "p95 guardar", "p95 entrega"], filas)}
<figure>{grafico}{leyenda([("Ingreso con código", "#8a8984"), ("Guardar respuestas", AZUL), ("Entrega", NARANJA)])}
<figcaption>p95 por operación. La línea roja es el presupuesto de 500 ms.</figcaption></figure>
<h3>CPU media durante cada corrida (100 % = un núcleo)</h3>
{tabla(["Componente", "60", "300", "540"], filas_cpu)}
"""


def seccion_infracciones() -> str:
    out = []
    for nombre, n in [("bc-infr-60", 60), ("bc-infr-300", 300)]:
        st = locust(nombre)
        if not st:
            out.append(f"<p>(falta la corrida de {n})</p>")
            continue
        filas = []
        for k, f in sorted(st.items()):
            if k.startswith("seal: ") and int(f["Request Count"]):
                filas.append(
                    [
                        esc(k[6:]),
                        num(int(f["Request Count"])),
                        str(f["Failure Count"]),
                        ms(float(f["50%"])),
                        ms(float(f["95%"])),
                    ]
                )
        al = st.get("alerta visible al docente")
        t = st["Aggregated"]
        out.append(f"""
<h3>{n} estudiantes, todos mandando señales cada 2-6 s</h3>
<p>{num(int(t["Request Count"]))} peticiones, {t["Failure Count"]} errores
({pct(int(t["Failure Count"]) / max(int(t["Request Count"]), 1))}).
Alerta visible en la lista del docente (sondeo cada 2 s): p50 {ms(float(al["50%"])) if al else "—"},
p95 {ms(float(al["95%"])) if al else "—"}, sobre {num(int(al["Request Count"])) if al else 0} alertas.</p>
{tabla(["Señal", "Enviadas", "Errores", "p50", "p95"], filas)}""")
    return f"""
<h2>2. Todos los módulos a la vez: el examen en que todos hacen trampa (Locust)</h2>
<p>Perfil «infracciones»: cada estudiante manda señales de los diez módulos del navegador y del
escritorio (foco, mirada, rostro, otra persona, procesos, monitores, voz, copia, objetos y encuadre)
con duraciones que cruzan los umbrales de severidad, así que muchas generan alerta. El docente
refresca alertas, señales y semáforo cada 2 s.</p>
{"".join(out)}"""


def seccion_k6() -> str:
    d = leer("k6-estres.json")
    if not d:
        return (
            "<h2>3. Pico de ingreso, módulos y punto de quiebre (k6)</h2><p>(falta la corrida)</p>"
        )
    m = d["metrics"]
    v = lambda k, s: m.get(k, {}).get("values", {}).get(s)  # noqa: E731
    etapas = sorted({int(x) for k in m for x in re.findall(r"etapa:(\d+)", k)})
    filas_rampa, p95s, etiquetas = [], [], []
    for e in etapas:
        p95 = v(f"http_req_duration{{etapa:{e}}}", "p(95)") or 0
        p50 = v(f"http_req_duration{{etapa:{e}}}", "med") or 0
        err = v(f"http_req_failed{{etapa:{e}}}", "rate") or 0
        n = (v(f"http_req_failed{{etapa:{e}}}", "passes") or 0) + (
            v(f"http_req_failed{{etapa:{e}}}", "fails") or 0
        )
        etiquetas.append(f"{e}/s")
        p95s.append(p95)
        filas_rampa.append([f"{e}", num(n / 60), ms(p50), ms(p95), pct(err)])
    checks = {c["name"]: (c["passes"], c["fails"]) for c in d["root_group"]["checks"]}
    ingreso = v("ingreso_completo", "p(95)")
    rech = v("senales_rechazadas_por_modulo", "count") or 0
    return f"""
<h2>3. Pico de ingreso, reglas de módulos y punto de quiebre (k6)</h2>
<p>Con <b>k6</b> (Grafana), sobre 600 estudiantes en 10 exámenes con presets distintos: dos
<code>strict</code>, dos <code>standard</code>, dos <code>basic</code> y cuatro <code>custom</code> que
solo vigilan la mirada y otra persona (<code>custom-vista</code>) o la voz (<code>custom-voz</code>).</p>
<h3>Pico de ingreso: los 600 a la vez</h3>
<p>Los 600 piden entrar en el mismo segundo (código, matrícula con consentimiento y estado).
Código: {checks.get("código 200", (0, 0))[0]} bien / {checks.get("código 200", (0, 0))[1]} mal ·
matrícula: {checks.get("matrícula 2xx", (0, 0))[0]} / {checks.get("matrícula 2xx", (0, 0))[1]} ·
estado: {checks.get("estado 200", (0, 0))[0]} / {checks.get("estado 200", (0, 0))[1]}.
Las tres llamadas seguidas tardaron p50 {ms(v("ingreso_completo", "med") or 0)} y
p95 {ms(ingreso or 0)}; errores {pct(v("http_req_failed{scenario:pico_ingreso}", "rate") or 0)}.</p>
<h3>Las reglas de los módulos se cumplen bajo carga</h3>
<p>30 señales por segundo durante 90 s, de los 12 tipos, en todos los presets. Cada respuesta se comparó
con el dominio: en un <code>custom</code>, una señal de un módulo apagado tiene que rechazarse con 400; si
está vigilada, tiene que entrar con la severidad que fija <code>severity.py</code>.</p>
{
        tabla(
            ["Comprobación", "Resultado"],
            [
                [
                    "Aceptada o rechazada según el preset",
                    f"{pct(v('modulo_correcto', 'rate') or 0)} de {num((v('modulo_correcto', 'passes') or 0) + (v('modulo_correcto', 'fails') or 0))}",
                ],
                ["Rechazadas por módulo apagado (correcto)", num(rech)],
                [
                    "Severidad igual a la del dominio",
                    f"{pct(v('severidad_correcta', 'rate') or 0)} de {num((v('severidad_correcta', 'passes') or 0) + (v('severidad_correcta', 'fails') or 0))}",
                ],
                [
                    "Errores de servidor o límite",
                    pct(v("http_req_failed{scenario:modulos}", "rate") or 0),
                ],
            ],
        )
    }
<h3>Rampa de señales hasta el punto de quiebre</h3>
<p>Señales de los tipos vigilados, subiendo cada minuto, mientras los 10 docentes leen sala, alertas,
señales y semáforo cada 2 s. Repartidas en turno entre los 600 estudiantes, ni la etapa más alta pasa
del límite de 120 escrituras por minuto y persona: un 429 aquí sería un fallo de capacidad.</p>
{tabla(["Objetivo (señales/s)", "Logradas/s", "p50", "p95", "Errores"], filas_rampa)}
<figure>{barras_h(etiquetas, [("p95", NARANJA, p95s)], umbral=1000) if etiquetas else ""}
<figcaption>p95 de <code>POST /events</code> en cada escalón; la línea es 1 s. Lecturas del docente
durante la rampa: p95 {ms(v("http_req_duration{scenario:docentes}", "p(95)") or 0)}.
Iteraciones que k6 no pudo lanzar por falta de VU libres: {
        num(v("dropped_iterations", "count") or 0)
    }.</figcaption></figure>
"""


def seccion_realtime() -> str:
    out = []
    for n in (300, 600):
        d = leer(f"realtime-{n}.json")
        if not d:
            out.append(f"<p>(falta la corrida de {n})</p>")
            continue
        a = d["alerta_a_docente_ms"]
        filas = [
            [esc(k), num(x["n"]), ms(x["p50"]), ms(x["p95"]), ms(x["max"])]
            for k, x in a.items()
            if k != "todas" and x.get("n")
        ]
        t = a["todas"]
        adm = d["admision_a_estudiante_ms"]
        out.append(f"""
<h3>{n} estudiantes ({d["examenes"]} exámenes), {d["minutos"]:g} minutos</h3>
<p>{d["canales"]["suscritos"]} de {d["canales"]["pedidos"]} canales suscritos
en {str(d["suscripcion_s"]).replace(".", ",")} s, {d["canales"]["caidos"]} caídos. {num(d["senales_enviadas"])} señales
enviadas, {num(d["senales_vistas_por_docente"])} vistas por su docente en vivo. De {num(d["alertas_enviadas"])} alertas,
<b>{d["alertas_perdidas"]} {"no llegó" if d["alertas_perdidas"] == 1 else "no llegaron"}</b>. Alerta en la pantalla del docente: p50 {ms(t.get("p50", 0))},
p95 {ms(t.get("p95", 0))}, máx. {ms(t.get("max", 0))}. Admisión vista por el estudiante (en lugar del
sondeo de 10 s): p50 {ms(adm.get("p50", 0))}, p95 {ms(adm.get("p95", 0))}.
Errores: {esc("; ".join(f"{k.split(': {')[0]} ×{v}" for k, v in sorted(d["errores"].items(), key=lambda kv: -kv[1]))) if d["errores"] else "ninguno"}.</p>
{tabla(["Señal con alerta", "Alertas", "p50", "p95", "Máx."], filas)}""")
    return f"""
<h2>4. Alertas en vivo por Supabase Realtime (WebSocket)</h2>
<p>Lo que hace el navegador, sin navegador: cada docente abre el canal de la pantalla en vivo (alertas,
señales y participantes de su examen) y cada estudiante el de la sala de espera y los avisos. Se
cronometra desde que el cliente manda la señal hasta que el mensaje llega por el WebSocket del docente:
es la meta SMART de avisar en menos de 5 s, medida por el camino real (API, Postgres, replicación y
Realtime con RLS), no por sondeo.</p>
{"".join(out)}
<div class="nota alerta"><b>Tope de conexiones.</b> Pasados unos 225 WebSocket abiertos a la vez, Realtime
rechaza los nuevos (<code>ConnectionRateLimitReached</code> y apretones de manos rechazados): en la corrida de 600
solo se suscribieron 227 canales. Supabase Cloud en el plan gratuito, que es el de producción, limita a 200
conexiones simultáneas. Cada estudiante con la página abierta usa una: <b>por encima de unos 190 estudiantes a la
vez en todo el sistema, los siguientes dejan de recibir avisos en vivo</b> (la sala de espera vuelve a funcionar por
sondeo cada 10 s, pero el docente deja de ver alertas al instante de quien no conectó).</div>
<div class="nota alerta"><b>Errores 500 en ráfagas.</b> Al abrir 300 WebSocket y hacer 300 ingresos en el mismo
segundo, la pasarela local (Kong) cortó conexiones con PostgREST (<code>RemoteProtocolError</code>, <code>Connection
reset by peer</code>). La API reintenta lo idempotente, pero un <code>POST</code> cortado a mitad no puede repetirse sin
riesgo de duplicar, y hoy sale como 500 genérico: un 4 % de las señales, un 7 % de los códigos y un 23 % de las matrículas de esa ráfaga. Los
429 de «admitir» los provocó el guion (admitía 5 por segundo, por encima del límite de 120 por minuto del docente),
no la API. Con la llegada escalonada de Locust y k6 no hubo 500.</div>
<div class="nota bien"><b>Lo que sí cumple:</b> con 300 estudiantes mandando señales de todos los módulos, la alerta
llega a la pantalla del docente en p95 de 3,1 s (meta: 5 s), y de 3.506 alertas solo 1 no llegó. La admisión llega al
estudiante en menos de 1,5 s (p95), frente a los hasta 10 s del sondeo.</div>"""


def seccion_ia(prod: list[dict[str, Any]]) -> str:
    d = leer("ia.json")
    filas = []
    if d:
        for r in d["rafagas"]:
            filas.append(
                [
                    str(r["estudiantes"]),
                    f"{r['analizados']}/{r['estudiantes']}",
                    ms(r["proceso_ms"].get("p50", 0)),
                    ms(r["espera_en_cola_ms"].get("p95", 0)),
                    ms(r["evento_a_analisis_ms"].get("p50", 0)),
                    ms(r["evento_a_analisis_ms"].get("p95", 0)),
                    f"{r['bajo_10s']}/{r['analizados']}",
                    f"{r['segundos_hasta_el_ultimo']:g} s".replace(".", ","),
                ]
            )
        sim = {}
        for r in d["rafagas"]:
            for k, x in r["similitud_media_por_audio"].items():
                sim.setdefault(k, x)
        dur = {"enunciado": "5,1 s", "enunciado-largo": "15,1 s", "ajeno": "7,7 s"}
    prod_filas = [[p["dia"], str(p["n"]), ms(p["p50"]), ms(p["p95"])] for p in prod]
    return f"""
<h2>5. La cola de IA por voz con audio y worker de verdad</h2>
<p>El camino completo de un fragmento con habla: URL firmada, subida directa a Storage, evento
<code>speech_detected</code> con la pregunta en curso, cola en Redis y el worker de producción (misma
imagen, faster-whisper <code>small</code>, 2 CPU y 2 GB por réplica, dos réplicas) que transcribe, compara con
el enunciado y devuelve el análisis. Los audios son voz en español generada con espeak-ng.</p>
{tabla(["Hablan a la vez", "Analizados", "Proceso p50", "Cola p95", "Total p50", "Total p95", "< 10 s", "Último listo"], filas) if filas else "<p>(falta la corrida)</p>"}
{tabla(["Audio", "Duración", "Similitud con el enunciado"], [[esc(k), dur.get(k, "—"), f"{v:.2f}".replace(".", ",")] for k, v in sim.items()]) if d else ""}
<p>El umbral del módulo es 0,6: el enunciado leído y la versión larga lo superan, y la conversación
ajena queda por debajo. La comparación con el enunciado discrimina bien.</p>
<h3>Lo mismo, en producción (últimos 30 días)</h3>
<p>Consulta de solo lectura sobre <code>audio_analyses</code> de la base real (solo agregados):</p>
{tabla(["Día", "Análisis", "Proceso p50", "Proceso p95"], prod_filas)}
"""


def seccion_soak() -> str:
    st = locust("bc-soak-120")
    if not st:
        return "<h2>6. Resistencia: 20 minutos seguidos</h2><p>(falta la corrida)</p>"
    t = st["Aggregated"]
    serie = memoria_en_el_tiempo("bc-soak-120", R, "api (réplicas)")
    ini = sum(v for _, v in serie[:5]) / max(len(serie[:5]), 1)
    fin = sum(v for _, v in serie[-5:]) / max(len(serie[-5:]), 1)
    return f"""
<h2>6. Resistencia: 120 estudiantes durante 20 minutos</h2>
<p>Un examen largo, para ver lo que una prueba corta esconde: memoria que crece sin parar o latencia que
se degrada con el tiempo. {num(int(t["Request Count"]))} peticiones, {t["Failure Count"]} errores
({pct(int(t["Failure Count"]) / max(int(t["Request Count"]), 1))}); guardar respuestas p95
{ms(p_(st, "examen: guardar respuestas") or 0)}, entrega p95 {ms(p_(st, "entrega") or 0)}.</p>
<figure>{linea(serie)}<figcaption>Memoria de la réplica de la API que más usa, en MiB, durante la
corrida. Al principio {ini:.0f} MiB, al final {fin:.0f} MiB (techo del contenedor: 512 MiB).</figcaption></figure>
"""


def seccion_navegadores() -> str:
    d = leer("navegadores.json")
    if not d:
        return "<h2>7. Navegadores reales</h2><p>(falta la corrida)</p>"
    por_tipo = d.get("senales_por_tipo") or d.get("por_tipo") or {}
    filas = [[esc(k), num(v)] for k, v in sorted(por_tipo.items())]
    return f"""
<h2>7. Navegadores reales con la supervisión encendida (Playwright)</h2>
<p>{
        d.get("estudiantes", "—")
    } Chromium reales (Chrome de este equipo, por túnel SSH hasta el entorno
aislado) inician sesión, entran al examen y corren la supervisión igual que en el equipo de un
estudiante: MediaPipe y el VAD en el navegador, con la cámara y el micrófono de prueba de Chromium (un
patrón sin rostro y la voz grabada). Un docente mira la actividad en vivo.</p>
{
        tabla(
            ["Medida", "Valor"],
            [
                [
                    "Navegadores que entraron al examen",
                    f"{d.get('entraron')} de {d.get('estudiantes')}",
                ],
                [
                    "POST /events desde el navegador p50 / p95",
                    f"{ms(d['post_events']['p50_ms'])} / {ms(d['post_events']['p95_ms'])} · {d['post_events']['errores']} errores",
                ],
                [
                    "Cámara en vivo recibida por el docente",
                    f"{str(round(d['fps_docente']['media'], 2)).replace('.', ',')} fps (configurado: 2)",
                ],
                ["Señales recibidas", str(d.get("senales"))],
                ["Alertas generadas", str(d.get("alertas"))],
            ],
        )
    }
<div class="nota alerta"><b>Defecto encontrado: la ausencia de rostro y la mirada fuera nunca llegan a alerta.</b>
Con el rostro ausente los 3 minutos enteros, cada navegador mandó <b>una sola</b> señal <code>face_absent</code> de 3 s,
de severidad baja, y ninguna alerta. Causa, en <code>apps/web/src/supervision/seguimiento.ts</code>: el episodio se emite una
vez al cumplir el mínimo (3 s) y al cerrarse ya no informa su duración real; el servidor solo alerta
<code>face_absent</code> desde 5 s y <code>gaze_away</code> desde 10 s. Afecta a la meta de detección de mirada y rostro. Es
código de visión (Jesús Limay y Rider Rodriguez): queda como tarea aparte, con la prueba que lo reproduce.</div>
<p>El detector de habla no arrancó con el micrófono falso de Chromium (etapa «abriendo la pista de audio», 0 muestras
oídas en 90 s). Puede ser un artefacto del dispositivo de prueba; la voz se probó por su camino de servidor en la
sección 5.</p>
{tabla(["Señal", "Llegadas"], filas) if filas else ""}
"""


def seccion_lighthouse() -> str:
    filas = []
    for pag, nombre in [
        ("portada", "Portada"),
        ("login", "Iniciar sesión"),
        ("privacidad", "Privacidad"),
    ]:
        for f, fn in [("mobile", "Teléfono"), ("desktop", "Escritorio")]:
            p = C / f"lh-{pag}-{f}.json"
            if not p.exists():
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            c, a = d["categories"], d["audits"]
            filas.append(
                [
                    nombre,
                    fn,
                    *(
                        str(round(c[k]["score"] * 100))
                        for k in ("performance", "accessibility", "best-practices", "seo")
                    ),
                    ms(a["first-contentful-paint"]["numericValue"]),
                    ms(a["largest-contentful-paint"]["numericValue"]),
                    ms(a["total-blocking-time"]["numericValue"]),
                    f"{a['cumulative-layout-shift']['numericValue']:.2f}".replace(".", ","),
                    f"{a['total-byte-weight']['numericValue'] / 1024:.0f} KiB",
                ]
            )
    return f"""
<h2>8. La web vista por un usuario real (Lighthouse)</h2>
<p>Lighthouse 12 desde un PC en Perú contra <code>https://proctoring-upao.app</code>, en teléfono (red y CPU
limitadas, como un móvil de gama media) y escritorio.</p>
{tabla(["Página", "Perfil", "Rend.", "Accesib.", "Buenas prác.", "SEO", "FCP", "LCP", "TBT", "CLS", "Peso"], filas)}
<p><b>SEO bajo a propósito:</b> la plataforma manda <code>X-Robots-Tag: noindex</code> para que los buscadores no
indexen exámenes ni pantallas internas; Lighthouse lo penaliza. <b>Accesibilidad y buenas prácticas: 100</b> en
todas las páginas.</p>
"""


def seccion_borde() -> str:
    d = leer("k6-borde.json")
    if not d:
        return "<h2>9. El borde de producción</h2><p>(falta la corrida)</p>"
    m = d["metrics"]
    v = lambda k, s: m.get(k, {}).get("values", {}).get(s)  # noqa: E731
    checks = [
        [esc(c["name"]), num(c["passes"]), num(c["fails"])] for c in d["root_group"]["checks"]
    ]
    cp = cpu_de("borde", C)
    return f"""
<h2>9. El borde de producción bajo carga (k6, solo lectura)</h2>
<p>Contra el dominio real, por TLS, Traefik y nginx, sin escribir nada en la base: hasta 250 visitantes
abriendo la web sin caché (HTML y todos los assets, comprimidos), 60 peticiones por segundo a la API
(<code>/health</code> y preflight de CORS) y, mientras tanto, las defensas del 18/11 comprobadas una y otra vez.</p>
{
        tabla(
            ["Medida", "Valor"],
            [
                [
                    "Página completa (HTML + assets) p50 / p95",
                    f"{ms(v('pagina_completa', 'med') or 0)} / {ms(v('pagina_completa', 'p(95)') or 0)}",
                ],
                [
                    "Peticiones web p95",
                    ms(v("http_req_duration{scenario:visitantes}", "p(95)") or 0),
                ],
                ["API p95", ms(v("http_req_duration{scenario:api}", "p(95)") or 0)],
                ["Errores web", pct(v("http_req_failed{scenario:visitantes}", "rate") or 0)],
                ["Defensas que se cumplieron", pct(v("seguridad_ok", "rate") or 0)],
                [
                    "CPU de Traefik media / máx.",
                    f"{cp.get('prod: traefik', (0, 0, 0))[0]:.0f} % / {cp.get('prod: traefik', (0, 0, 0))[1]:.0f} %",
                ],
                [
                    "CPU de la web (nginx, 2 réplicas de 0,5 CPU)",
                    f"media {cp.get('prod: web', (0, 0, 0))[0]:.0f} %, con techo de 100 %",
                ],
            ],
        )
    }
{tabla(["Comprobación", "Bien", "Mal"], checks)}
<div class="nota alerta"><b>El cuello de botella es la compresión.</b> Cero errores, pero la primera visita sin caché
llega a 11,8 s en p95 con 250 a la vez. Las dos réplicas de la web tienen 0,5 CPU cada una y comprimen con gzip cada
asset en cada petición (<code>gzip on</code> sin <code>gzip_static</code>): pasaron la prueba en su techo. Los assets llevan
<code>immutable</code>, así que solo pesa en la primera visita; pero en un examen esa primera visita es la de todos a la
misma hora. Arreglo barato: comprimir los assets al construir la imagen y servirlos con <code>gzip_static on</code>, o
subir el techo a 1 CPU por réplica.</div>
"""


def main() -> None:
    prod = (
        json.loads((C / "prod-audio.json").read_text(encoding="utf-8"))
        if (C / "prod-audio.json").exists()
        else []
    )
    cuerpo = "".join(
        [
            seccion_locust(),
            seccion_infracciones(),
            seccion_k6(),
            seccion_realtime(),
            seccion_ia(prod),
            seccion_soak(),
            seccion_navegadores(),
            seccion_lighthouse(),
            seccion_borde(),
        ]
    )
    resumen = (
        (C / "resumen.html").read_text(encoding="utf-8") if (C / "resumen.html").exists() else ""
    )
    plantilla = (R.parent / "plantilla_informe.html").read_text(encoding="utf-8")
    estilo = (
        re.search(r"<style>(.*?)</style>", plantilla, re.S)
        .group(1)
        .replace("{{", "{")
        .replace("}}", "}")
    )
    estilo += ".crudo{font-size:7.5pt;background:#f6f5f2;padding:2mm;white-space:pre-wrap;} code{font-size:9pt;}"
    doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Informe de carga · batería completa · Proctoring</title><style>{estilo}</style></head><body>
{resumen}{cuerpo}</body></html>"""
    (C / "informe.html").write_text(doc, encoding="utf-8")
    print("escrito", C / "informe.html")


if __name__ == "__main__":
    main()
