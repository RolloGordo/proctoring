"""Genera el informe de carga (HTML listo para imprimir a PDF) desde los CSV.

    uv run python informe.py            # escribe resultados/informe-carga.html

Cada cifra sale de `resultados/*_stats.csv` y `*-recursos.csv`: si se repite
una corrida, el informe cambia solo. Los gráficos son SVG estáticos (es un
documento impreso) y cada uno va con su tabla.
"""

from __future__ import annotations

import csv
import html
from collections import defaultdict
from datetime import date
from pathlib import Path

R = Path(__file__).resolve().parent / "resultados"

AZUL, NARANJA = "#2a78d6", "#eb6834"  # validados con validate_palette.js (dataviz)
TINTA, TINTA2, TINTA3, LINEA, ROJO = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#b42318"


# --------------------------------------------------------------------- datos


def _llano(t: str) -> str:
    return "".join(c for c in t if c.isascii() and c != "�")


def stats(nombre: str) -> dict[str, dict[str, str]]:
    with (R / f"{nombre}_stats.csv").open(encoding="utf-8", errors="replace") as f:
        return {_llano(fila["Name"]): fila for fila in csv.DictReader(f)}


def cpu(nombre: str) -> dict[str, tuple[float, float]]:
    ruta = R / f"{nombre}-recursos.csv"
    if not ruta.exists():
        return {}
    suma: dict[tuple[str, str], float] = defaultdict(float)
    with ruta.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            suma[(fila["grupo"], fila["t"])] += float(fila["cpu_pct"])
    g: dict[str, list[float]] = defaultdict(list)
    for (grupo, _), v in suma.items():
        g[grupo].append(v)
    return {k: (sum(v) / len(v), max(v)) for k, v in g.items()}


def p(nombre: str, endpoint: str = "Aggregated", pct: str = "95%") -> float:
    return float(stats(nombre)[_llano(endpoint)][pct])


def total(nombre: str) -> dict[str, float]:
    t = stats(nombre)["Aggregated"]
    n, e = int(t["Request Count"]), int(t["Failure Count"])
    return {"n": n, "errores": e, "tasa": e / max(n, 1), "rps": float(t["Requests/s"])}


def ms(v: float) -> str:
    return f"{v / 1000:.1f} s".replace(".", ",") if v >= 1000 else f"{v:.0f} ms"


ENDPOINTS = [
    ("ingreso: código", "Ingreso con código"),
    ("sala de espera: mi estado", "Sala de espera"),
    ("examen: preguntas", "Descargar preguntas"),
    ("examen: guardar respuestas", "Guardar respuestas"),
    ("examen: señal de supervisión", "Señal de supervisión"),
    ("entrega", "Entrega"),
    ("docente: sala de espera", "Docente: sala"),
]


# ------------------------------------------------------------------ gráficos


def barras_h(
    filas: list[str],
    series: list[tuple[str, str, list[float]]],
    *,
    umbral: float | None = None,
    formato=ms,
    ancho: int = 640,
) -> str:
    """Barras horizontales agrupadas, un solo eje, etiqueta directa al final."""
    alto_barra, hueco, izq, der = 12, 2, 150, 70
    grupo = len(series) * (alto_barra + hueco) + 12
    alto = len(filas) * grupo + 34
    tope = max([v for _, _, vs in series for v in vs] + [umbral or 0]) * 1.05
    x = lambda v: izq + (ancho - izq - der) * v / tope
    out = [f'<svg viewBox="0 0 {ancho} {alto}" class="grafico" role="img">']
    for i, nombre in enumerate(filas):
        y0 = 8 + i * grupo
        out.append(
            f'<text x="{izq - 8}" y="{y0 + grupo / 2 - 2}" text-anchor="end" '
            f'class="cat">{html.escape(nombre)}</text>'
        )
        for j, (_, color, vs) in enumerate(series):
            y = y0 + j * (alto_barra + hueco)
            w = max(x(vs[i]) - izq, 1.5)
            out.append(
                f'<rect x="{izq}" y="{y}" width="{w:.1f}" height="{alto_barra}" rx="2" fill="{color}"/>'
                f'<text x="{izq + w + 4:.1f}" y="{y + alto_barra - 2}" class="val">{formato(vs[i])}</text>'
            )
    base = alto - 22
    out.append(
        f'<line x1="{izq}" y1="6" x2="{izq}" y2="{base}" stroke="{TINTA3}" stroke-width="1"/>'
    )
    if umbral is not None:
        ux = x(umbral)
        out.append(
            f'<line x1="{ux:.1f}" y1="4" x2="{ux:.1f}" y2="{base}" stroke="{ROJO}" '
            f'stroke-width="1.5" stroke-dasharray="4 3"/>'
            f'<text x="{ux:.1f}" y="{base + 14}" text-anchor="middle" class="umbral">'
            f"presupuesto {formato(umbral)}</text>"
        )
    out.append("</svg>")
    return "".join(out)


def leyenda(series: list[tuple[str, str]]) -> str:
    return (
        '<p class="leyenda">'
        + "".join(f'<span><i style="background:{c}"></i>{html.escape(n)}</span>' for n, c in series)
        + "</p>"
    )


def tabla(cabecera: list[str], filas: list[list[str]]) -> str:
    th = "".join(f"<th>{html.escape(c)}</th>" for c in cabecera)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in f) + "</tr>" for f in filas)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


# ------------------------------------------------------------------- informe


def main() -> None:
    red = {r: f"red-mil-{r}r" for r in (1, 2, 4)}
    t = {r: total(n) for r, n in red.items()}
    p95 = {r: p(n) for r, n in red.items()}
    p50 = {r: p(n, pct="50%") for r, n in red.items()}
    render60, render20 = "red-render-60", "red-render-20"

    escalado = barras_h(
        ["1 réplica", "2 réplicas", "4 réplicas"],
        [("p50", AZUL, [p50[r] for r in (1, 2, 4)]), ("p95", NARANJA, [p95[r] for r in (1, 2, 4)])],
        umbral=500,
    )
    tabla_escalado = tabla(
        ["Réplicas", "Peticiones", "Errores", "Peticiones/s", "p50", "p95", "p99"],
        [
            [
                str(r),
                f"{t[r]['n']:,}".replace(",", "."),
                f"{t[r]['errores']:.0f} ({t[r]['tasa']:.2%})",
                f"{t[r]['rps']:.1f}",
                ms(p50[r]),
                ms(p95[r]),
                ms(p(red[r], pct="99%")),
            ]
            for r in (1, 2, 4)
        ],
    )

    antes, despues = "mil-4r", "opt-mil-4r"
    optim = barras_h(
        [e[1] for e in ENDPOINTS],
        [
            ("Antes", AZUL, [p(antes, e[0]) for e in ENDPOINTS]),
            ("Después", NARANJA, [p(despues, e[0]) for e in ENDPOINTS]),
        ],
        umbral=500,
    )

    final = red[4]
    por_endpoint = barras_h(
        [e[1] for e in ENDPOINTS],
        [("p95", NARANJA, [p(final, e[0]) for e in ENDPOINTS])],
        umbral=500,
    )

    componentes = [
        ("api (réplicas)", "API (4 réplicas)"),
        ("postgrest", "PostgREST"),
        ("postgres", "Postgres"),
        ("kong", "Kong (pasarela)"),
    ]
    c4 = cpu(final)
    cpu_svg = barras_h(
        [c[1] for c in componentes],
        [
            ("Media", AZUL, [c4.get(c[0], (0, 0))[0] for c in componentes]),
            ("Máximo", NARANJA, [c4.get(c[0], (0, 0))[1] for c in componentes]),
        ],
        formato=lambda v: f"{v:.0f} %",
    )

    examen60_1cpu = "red-examen60-1r"
    render_svg = barras_h(
        [e[1] for e in ENDPOINTS],
        [
            ("1 CPU", AZUL, [p(examen60_1cpu, e[0]) for e in ENDPOINTS]),
            ("0,1 CPU (Render gratuito)", NARANJA, [p(render60, e[0]) for e in ENDPOINTS]),
        ],
        umbral=500,
    )
    r20, r60 = total(render20), total(render60)

    tabla_modelo = tabla(
        ["Quién", "Qué hace", "Ritmo"],
        [
            [
                "Estudiante",
                "Entra con el código, se matricula y consiente",
                "una vez; todos casi a la vez",
            ],
            [
                "",
                "Sala de espera: pregunta si ya lo admitieron",
                "cada 10 s ±20 % (como <code>SalaDeEspera.tsx</code>)",
            ],
            ["", "Descarga sus preguntas", "al ser admitido"],
            ["", "Guarda respuestas (70 %) o manda una señal de supervisión (25 %)", "cada 8-15 s"],
            ["", "Entrega", "todos en el último minuto: el pico"],
            [
                "Docente",
                "Refresca la sala, admite a quien espera, mira alertas",
                "cada 5 s; admite 5 por vuelta",
            ],
        ],
    )
    tabla_opciones = tabla(
        ["Opción", "CPU / memoria", "Varias réplicas", "Se duerme", "Requisito / riesgo"],
        [
            [
                "<b>Render gratuito</b> (actual)",
                "0,1 CPU · 512 MB",
                "No",
                "Sí, a los 15 min (30-60 s en despertar)",
                "Medido: no sostiene un examen de 60.",
            ],
            [
                "<b>Oracle Cloud Always Free</b>",
                "VM ARM de 2 a 4 núcleos y 12-24 GB (según el cupo vigente)",
                "Sí: nginx + réplicas + Redis en la VM, la pila probada",
                "No",
                (
                    "Pide tarjeta para verificar identidad (no cobra lo Always Free). Puede reclamar VMs ociosas; "
                    "a veces no hay capacidad ARM en la región. Hay que administrar el servidor (TLS, parches, firewall)."
                ),
            ],
            [
                "<b>Google Cloud Run</b>",
                "Por petición; escala solo",
                "Sí, automático",
                "A cero (arranque de segundos)",
                (
                    "Exige cuenta de facturación con tarjeta y cobra lo que pase de la cuota: rompe la regla de "
                    "cero pagos si algo se descontrola."
                ),
            ],
            [
                "<b>Hugging Face Spaces</b>",
                "2 CPU · 16 GB",
                "No",
                "Sí, a las 48 h",
                "La documentación actual pide plan de pago para Spaces con Docker.",
            ],
        ],
    )

    hoy = date.today().strftime("%d/%m/%Y")
    cuerpo = PLANTILLA.format(
        hoy=hoy,
        tabla_modelo=tabla_modelo,
        tabla_opciones=tabla_opciones,
        p95_1=ms(p95[1]),
        p95_4=ms(p95[4]),
        p50_1=ms(p50[1]),
        p50_4=ms(p50[4]),
        err_1=f"{t[1]['tasa']:.2%}",
        err_4=f"{t[4]['tasa']:.2%}",
        rps_1=f"{t[1]['rps']:.0f}",
        rps_4=f"{t[4]['rps']:.0f}",
        mejora=f"{p95[1] / p95[4]:.0f}",
        render60_p95=ms(p(render60)),
        render60_resp=ms(p(render60, "examen: guardar respuestas")),
        render60_ingreso=ms(p(render60, "ingreso: código")),
        render60_entrega=ms(p(render60, "entrega")),
        render20_p95=ms(p(render20)),
        render20_resp=ms(p(render20, "examen: guardar respuestas")),
        render20_ingreso=ms(p(render20, "ingreso: código")),
        r20_err=f"{r20['tasa']:.2%}",
        r60_err=f"{r60['tasa']:.2%}",
        f_resp=ms(p(final, "examen: guardar respuestas")),
        f_senal=ms(p(final, "examen: señal de supervisión")),
        f_entrega=ms(p(final, "entrega")),
        f_ingreso=ms(p(final, "ingreso: código")),
        f_sala=ms(p(final, "sala de espera: mi estado")),
        api_cpu_1=f"{cpu(red[1]).get('api (réplicas)', (0, 0))[0]:.0f}",
        pg_cpu_1=f"{cpu(red[1]).get('postgres', (0, 0))[0]:.0f}",
        escalado=escalado,
        tabla_escalado=tabla_escalado,
        leyenda_p=leyenda([("p50 (mediana)", AZUL), ("p95", NARANJA)]),
        optim=optim,
        leyenda_ad=leyenda([("Antes de optimizar", AZUL), ("Después", NARANJA)]),
        por_endpoint=por_endpoint,
        tabla_endpoint=tabla(
            ["Endpoint", "Peticiones", "p50", "p95", "p99"],
            [
                [
                    e[1],
                    stats(final)[_llano(e[0])]["Request Count"],
                    ms(p(final, e[0], "50%")),
                    ms(p(final, e[0])),
                    ms(p(final, e[0], "99%")),
                ]
                for e in ENDPOINTS
            ],
        ),
        cpu_svg=cpu_svg,
        leyenda_cpu=leyenda([("CPU media", AZUL), ("CPU máxima", NARANJA)]),
        render_svg=render_svg,
        leyenda_r=leyenda([("1 CPU", AZUL), ("0,1 CPU (Render gratuito)", NARANJA)]),
        tabla_render=tabla(
            ["Escenario", "Peticiones", "Errores", "p50", "p95", "Guardar respuestas p95"],
            [
                [
                    n,
                    f"{total(c)['n']:,}".replace(",", "."),
                    f"{total(c)['tasa']:.2%}",
                    ms(p(c, pct="50%")),
                    ms(p(c)),
                    ms(p(c, "examen: guardar respuestas")),
                ]
                for n, c in [
                    ("60 estudiantes · 1 CPU", examen60_1cpu),
                    ("60 estudiantes · 0,1 CPU", render60),
                    ("20 estudiantes · 0,1 CPU", render20),
                ]
            ],
        ),
    )
    destino = R / "informe-carga.html"
    destino.write_text(cuerpo, encoding="utf-8")
    print(f"Escrito {destino}")


PLANTILLA = (Path(__file__).resolve().parent / "plantilla_informe.html").read_text(encoding="utf-8")

if __name__ == "__main__":
    main()
