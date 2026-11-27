"""Plantilla común de los informes de pruebas (HTML → PDF con Chrome sin ventana).

Cada informe es un diccionario con portada, indicadores y secciones de HTML ya
armado. `pdf()` lo imprime en A4 con la misma tipografía y estructura para todos,
para que los ocho informes se lean como una sola serie.
"""

from __future__ import annotations

import html
import shutil
import subprocess
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

CHROME = next(
    (
        p
        for p in (
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            shutil.which("chromium") or "",
            shutil.which("google-chrome") or "",
        )
        if p and Path(p).exists()
    ),
    "",
)

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; color: #17212b; font-size: 10.5pt; line-height: 1.5; margin: 0; }
.portada { height: 255mm; display: flex; flex-direction: column; justify-content: space-between; page-break-after: always; }
.portada .arriba { border-top: 6px solid #1f5f8b; padding-top: 14mm; }
.portada .serie { font-size: 10pt; letter-spacing: .08em; text-transform: uppercase; color: #1f5f8b; font-weight: 600; }
.portada h1 { font-size: 30pt; line-height: 1.1; margin: 6mm 0 4mm; }
.portada .sub { font-size: 13pt; color: #44515f; max-width: 150mm; }
.portada table { border-collapse: collapse; font-size: 10pt; }
.portada td { padding: 3px 14px 3px 0; vertical-align: top; }
.portada td:first-child { color: #5a6775; white-space: nowrap; }
.veredicto { margin-top: 10mm; padding: 5mm 6mm; border-radius: 3mm; font-size: 12pt; }
.veredicto.ok { background: #e4f2e6; border-left: 5px solid #2f6b3a; }
.veredicto.medio { background: #fbf1dc; border-left: 5px solid #8a5a00; }
.veredicto.mal { background: #f9e3e3; border-left: 5px solid #9b2c2c; }
h2 { font-size: 15pt; margin: 9mm 0 3mm; color: #12324a; border-bottom: 1.5px solid #cfd8e1; padding-bottom: 1.5mm; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 6mm 0 2mm; page-break-after: avoid; }
p { margin: 0 0 2.5mm; }
ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
li { margin-bottom: 1mm; }
code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 9pt; background: #eef1f5; padding: 0 3px; border-radius: 2px; }
pre { font-family: Consolas, monospace; font-size: 8.5pt; background: #eef1f5; padding: 3mm; border-radius: 2mm; white-space: pre-wrap; page-break-inside: avoid; }
table.t { border-collapse: collapse; width: 100%; font-size: 9pt; margin: 2mm 0 4mm; }
table.t th { background: #e7edf3; text-align: left; padding: 4px 6px; border: 1px solid #cfd8e1; }
table.t td { padding: 3.5px 6px; border: 1px solid #dde3ea; vertical-align: top; }
table.t tr { page-break-inside: avoid; }
td.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.kpis { display: flex; gap: 4mm; flex-wrap: wrap; margin: 3mm 0 5mm; }
.kpi { flex: 1 1 32mm; border: 1px solid #cfd8e1; border-radius: 2.5mm; padding: 3mm 4mm; }
.kpi b { display: block; font-size: 17pt; color: #12324a; font-variant-numeric: tabular-nums; }
.kpi span { font-size: 8.5pt; color: #5a6775; }
.ok { color: #2f6b3a; font-weight: 600; }
.mal { color: #9b2c2c; font-weight: 600; }
.medio { color: #8a5a00; font-weight: 600; }
.nota { background: #eef4f9; border-left: 4px solid #1f5f8b; padding: 3mm 4mm; margin: 3mm 0; page-break-inside: avoid; }
.nota.mal { background: #f9e3e3; border-color: #9b2c2c; color: inherit; font-weight: normal; }
.nota.medio { background: #fbf1dc; border-color: #8a5a00; color: inherit; font-weight: normal; }
img.captura { max-width: 100%; max-height: 105mm; width: auto; display: block; border: 1px solid #cfd8e1; border-radius: 2mm; margin: 2mm 0; page-break-inside: avoid; }
figure { margin: 3mm 0; page-break-inside: avoid; }
figcaption { font-size: 8.5pt; color: #5a6775; }
.pie { font-size: 8pt; color: #6b7785; margin-top: 8mm; border-top: 1px solid #dde3ea; padding-top: 2mm; }
"""


def e(texto: object) -> str:
    return html.escape(str(texto))


def tabla(cabeceras: Sequence[str], filas: Iterable[Sequence[object]], numericas: Iterable[int] = ()) -> str:
    nums = set(numericas)
    cuerpo = "".join(
        "<tr>" + "".join(f'<td class="n">{c}</td>' if i in nums else f"<td>{c}</td>" for i, c in enumerate(f)) + "</tr>"
        for f in filas
    )
    return '<table class="t"><tr>' + "".join(f"<th>{e(c)}</th>" for c in cabeceras) + f"</tr>{cuerpo}</table>"


def kpis(pares: Sequence[tuple[str, str]]) -> str:
    return '<div class="kpis">' + "".join(f'<div class="kpi"><b>{v}</b><span>{e(k)}</span></div>' for k, v in pares) + "</div>"


def imagen(ruta: Path, pie: str) -> str:
    """Captura incrustada (data URI): el PDF no depende de archivos sueltos."""
    import base64

    datos = base64.b64encode(ruta.read_bytes()).decode()
    return f'<figure><img class="captura" src="data:image/png;base64,{datos}"><figcaption>{e(pie)}</figcaption></figure>'


def estado(resultado: str) -> str:
    return {
        "passed": '<span class="ok">Pasa</span>',
        "failed": '<span class="mal">Falla</span>',
        "skipped": '<span class="medio">Omitida</span>',
    }.get(resultado, e(resultado))


def documento(inf: dict[str, Any]) -> str:
    filas = "".join(f"<tr><td>{e(k)}</td><td>{v}</td></tr>" for k, v in inf["ficha"])
    secciones = "".join(f"<h2>{e(t)}</h2>{cuerpo}" for t, cuerpo in inf["secciones"])
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{e(inf['titulo'])}</title><style>{CSS}</style></head><body>
<section class="portada"><div class="arriba"><div class="serie">Sistema Proctoring · Taller Integrador 1 · UPAO</div>
<h1>{e(inf['titulo'])}</h1><div class="sub">{e(inf['subtitulo'])}</div>
<div class="veredicto {inf['veredicto'][0]}">{inf['veredicto'][1]}</div></div>
<table>{filas}</table></section>
{secciones}
<div class="pie">Informe generado por los scripts de <code>pruebas/informes/</code> a partir de los resultados de la corrida. Ninguna cifra se escribió a mano: todas salen de los archivos de resultados de esa ejecución.</div>
</body></html>"""


def pdf(inf: dict[str, Any], destino: Path) -> Path:
    if not CHROME:
        raise RuntimeError("No hay Chrome ni Edge para imprimir el PDF")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        fuente = Path(tmp) / "informe.html"
        fuente.write_text(documento(inf), encoding="utf-8")
        subprocess.run(
            [
                CHROME,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--user-data-dir={Path(tmp) / 'perfil'}",
                "--allow-file-access-from-files",
                f"--print-to-pdf={destino}",
                fuente.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
    return destino
