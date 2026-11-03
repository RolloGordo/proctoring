# -*- coding: utf-8 -*-
"""Backlog v9: lo que decidió el profesor en la reunión del 31/10.

Tres decisiones suyas cambian el plan que dejó el v8:

1. **El instalador no tiene que bajar a 10 MB.** Se le explicó que los 100 MB
   son Chromium y que el código propio son kilobytes, y respondió que el Sumadi
   pesa 300 y que «si no llega a 150, está bien». Hoy pesa 102,9 MB. La
   migración a Tauri sobra, y con ella las semanas 10 y 11 de Rider.

2. **El modelo de visión se queda como está.** Jesús preguntó por uno más
   pesado para mejorar la calidad; la respuesta fue «por costo-beneficio está
   en términos aceptables… dejémoslo ahí, no lo cambiemos».

3. **El sprint pasa de funcionalidad a atributos de calidad**, «uno cada uno»,
   con pruebas según la ISO/IEC 25010: usabilidad, eficiencia, escalabilidad,
   disponibilidad y seguridad.

Y una pregunta suya que la grabación corta a medias: «¿cuántos son de los que
están colgando por API?». Medido contra el código: una sola API de pago,
Deepgram, para transcribir. La alternativa propia ya existe en el código de
Pierre (faster-whisper) pero no entra en la imagen de producción.

El rediseño visual es un frente aparte, de Héctor entero.
"""

from __future__ import annotations

import csv
from pathlib import Path

RAIZ = Path(r"C:\Users\Usuario\Desktop\proctoring")
ENTRADA = RAIZ / "docs" / "Backlog_v8_real.csv"
SALIDA = RAIZ / "docs" / "Backlog_v9_real.csv"

HECTOR = "hsilvav2@upao.edu.pe"
RIDER = "rrodriguezr36@upao.edu.pe"
PIERRE = "rzecvallosb1@upao.edu.pe"
JESUS = "jlimayc1@upao.edu.pe"

SEMANAS = {
    "Semana 10": ("2026-11-02", "2026-11-06"),
    "Semana 11": ("2026-11-09", "2026-11-13"),
    "Semana 12": ("2026-11-16", "2026-11-20"),
    "Semana 13": ("2026-11-23", "2026-11-27"),
}

filas = list(csv.DictReader(ENTRADA.open(encoding="utf-8-sig")))
COLUMNAS = list(filas[0].keys())
por_codigo = {f["Código"]: f for f in filas if f["Código"]}


def anotar(fila, nota):
    fila["Notas"] = (fila["Notas"] + " · " if fila["Notas"] else "") + nota


def mover(codigo, semana, responsable=None, nota=None):
    fila = por_codigo[codigo]
    fila["Semana"] = semana
    fila["Fecha Inicio"], fila["Fecha Fin"] = SEMANAS[semana]
    if responsable:
        fila["Responsable"] = responsable
    if nota:
        anotar(fila, nota)


def exigir(codigo, criterio, nota=None):
    fila = por_codigo[codigo]
    fila["Criterios de Aceptación"] = fila["Criterios de Aceptación"] + "\n" + criterio
    if nota:
        anotar(fila, nota)


def cerrar(codigo, estado, nota):
    fila = por_codigo[codigo]
    fila["Status"] = estado
    anotar(fila, nota)


orden = max(int(f["Orden"]) for f in filas if f["Orden"])


def nueva(codigo, titulo, descripcion, criterios, puntos, responsable, semana,
          epica, fase, spec="—", dependencia="", prioridad="Alta",
          status="Open", nota="", sprint="Sprint 2"):
    global orden
    orden += 1
    inicio, fin = SEMANAS[semana]
    filas.append({
        "Tareas": titulo,
        "Orden": str(orden),
        "Código": codigo,
        "Descripción": descripcion,
        "Criterios de Aceptación": "\n".join("- " + c for c in criterios),
        "Estimación": f"{puntos} pt",
        "Horas estimadas": "",
        "Horas reales": "",
        "Responsable": responsable,
        "N° Sprint": sprint,
        "Semana": semana,
        "Spec": spec,
        "Notas": nota,
        "Dependencia": dependencia,
        "Épica": epica,
        "Prioridad": prioridad,
        "Status": status,
        "Fecha Inicio": inicio,
        "Fecha Fin": fin,
        "Fase": fase,
    })


def epica(codigo, titulo, despues_de):
    posicion = next(i for i, f in enumerate(filas) if f["Código"] == despues_de) + 1
    filas.insert(posicion, {
        **{c: "" for c in COLUMNAS},
        "Tareas": titulo,
        "Orden": codigo.split("-")[1].lstrip("0") or "0",
        "Código": codigo,
        "Estimación": "Agrupador",
        "Épica": codigo,
        "Prioridad": "Alta",
        "Status": "Open",
    })


# ---------------------------------------------------------------------------
# 0. Épicas nuevas
# ---------------------------------------------------------------------------
epica("EP-008", "Atributos de calidad (ISO/IEC 25010)", "EP-007")
epica("EP-009", "Rediseño visual", "EP-008")

# ---------------------------------------------------------------------------
# 1. Lo que la reunión dejó sin objeto
# ---------------------------------------------------------------------------
SIN_TAURI = (
    "Cancelada: el profesor aceptó hasta 150 MB en la reunión del 31/10 "
    "(«el Sumadi pesa 300… si no llega a 150, está bien»). Hoy pesa 102,9 MB"
)
for codigo in ("TA-084", "TA-089", "TA-091", "TA-092"):
    cerrar(codigo, "Cancelled", SIN_TAURI)

cerrar("TA-085", "Done",
       "Hecha el 30/10: 111,4 MB → 102,9 MB quitando 52 idiomas de Chromium. "
       "La aplicación empaquetada arranca y detecta. PR #59")

exigir("EN-014", "- No pasa de 150 MB, el límite que aceptó el profesor el 31/10")

# Lo que el v8 movió o reasignó por culpa de la migración vuelve a su sitio:
# Rider queda libre y la usabilidad es suya.
VUELVE = "Vuelve a Rider en el v9: sin migración, la usabilidad es suya"
mover("TA-032", "Semana 10", responsable=RIDER,
      nota=VUELVE + ". Va con el preset Personalizado (HU-031)")
mover("TA-034", "Semana 11", responsable=RIDER, nota=VUELVE)
mover("TA-033", "Semana 11", nota="Sobre Electron, que es la tecnología que queda")
mover("TA-039", "Semana 11", nota="Vuelve a la semana 11: ya no compite con la migración")

# Equilibrio de la semana 10. Héctor tenía diez puntos con el rediseño encima, y
# Rider tres porque quedó libre. La cola persistente vive en el emisor del
# navegador (apps/web/src/supervision), que es código de Rider; el informe en
# PDF puede esperar a la 12.
mover("TA-090", "Semana 10", responsable=RIDER,
      nota="Reasignada en el v9: el emisor es código del navegador, y Rider quedó libre")
mover("HU-017", "Semana 12", nota="Movida en el v9 para hacer sitio al rediseño")
anotar(por_codigo["DO-032"],
       "La decisión ya la tomó el profesor el 31/10: se queda Electron. El ADR "
       "registra por qué, con los pesos medidos")

# ---------------------------------------------------------------------------
# 2. Decisiones del profesor sobre lo que ya estaba
# ---------------------------------------------------------------------------
NO_CAMBIAR_MODELO = (
    "No cambiar el modelo de visión: decisión del profesor el 31/10, «por "
    "costo-beneficio está en términos aceptables… dejémoslo ahí»"
)
for codigo in ("TA-037", "TA-043", "TA-093"):
    if codigo in por_codigo:
        anotar(por_codigo[codigo], NO_CAMBIAR_MODELO)

# ---------------------------------------------------------------------------
# 3. El plan de pruebas que lo ordena todo
# ---------------------------------------------------------------------------
nueva(
    "DO-033",
    "Plan de pruebas por atributo de calidad (ISO/IEC 25010)",
    "Una tabla que todos rellenan: qué atributo, qué característica de la "
    "norma, qué prueba, qué métrica y dónde queda la evidencia.",
    [
        "Un atributo por integrante, como pidió el profesor",
        "Cada fila dice la característica de la ISO/IEC 25010:2023 que cubre, "
        "contrastada con el texto de la norma y no de memoria",
        "Cada prueba tiene una métrica con número y un umbral de aprobado",
    ],
    1, HECTOR, "Semana 10", "EP-008", "Evaluación",
    status="Doing",
    nota="Pedido por el profesor el 31/10: «las pruebas de la 25010»",
)

# ---------------------------------------------------------------------------
# 4. Usabilidad — Rider
#
# «Me pierdo en la secuencia.» Lo que describió el profesor: curso → unidades
# de aprendizaje → cuáles son evaluables → sesiones → banco de preguntas del
# curso → examen.
# ---------------------------------------------------------------------------
nueva(
    "HU-031",
    "El docente elige qué supervisar: preset Personalizado",
    "La cuarta opción que pidió el profesor junto a básico, estándar y "
    "estricto. La base, la API y la etiqueta ya la soportan; la pantalla de "
    "edición la convertía en «estándar» al cargarla.",
    [
        "Aparece como cuarta opción al crear y al editar el examen",
        "Se eligen los módulos uno por uno",
        "Se guarda como 'custom' y sigue siéndolo al volver a abrirlo",
        "El resumen del examen dice qué se vigila",
    ],
    1, RIDER, "Semana 10", "EP-008", "Paso a Producción", spec="SPEC-001",
    nota="Pedido por el profesor el 31/10. Es la mejora más barata de la lista",
)
nueva(
    "HU-032",
    "Recorrido del docente: curso, unidad, sesión, examen",
    "Las pantallas que siguen el orden en que el profesor piensa su curso.",
    [
        "Desde el curso se ven sus unidades y, en cada una, sus sesiones "
        "evaluables",
        "El examen se crea desde la sesión y hereda curso y unidad",
        "El banco del curso se importa sin salir del recorrido",
        "Los exámenes anteriores, que no tienen unidad, siguen abriéndose",
    ],
    2, RIDER, "Semana 11", "EP-008", "Paso a Producción", spec="SPEC-001",
    dependencia="TA-094",
)
nueva(
    "TA-095",
    "Prueba de usabilidad con usuarios reales",
    "Medir el recorrido con personas que no lo han construido.",
    [
        "Tareas cronometradas: crear curso, crear examen, admitir estudiante y "
        "revisar un caso",
        "Tasa de éxito por tarea y dónde se pierde cada persona",
        "Cuestionario SUS con su puntuación",
    ],
    1, RIDER, "Semana 12", "EP-008", "Evaluación", dependencia="HU-032",
    nota="El profesor ofreció a un colega de Ciencias de la Comunicación "
         "(Víctor o Carlos Quiroz) para la parte de interacción",
)

# ---------------------------------------------------------------------------
# 5. Disponibilidad — Jesús, que además lleva el esquema
# ---------------------------------------------------------------------------
nueva(
    "TA-094",
    "Unidades de aprendizaje en el modelo de datos",
    "Hoy un examen cuelga directamente del curso: ninguna migración menciona "
    "unidades. Es lo que hace falta para el recorrido del profesor.",
    [
        "Migración nueva, sin tocar las ya aplicadas",
        "Unidades por curso, con orden y la marca de evaluable",
        "Un examen puede pertenecer a una unidad, sin obligar",
        "RLS: el docente solo ve las unidades de sus cursos",
        "Los exámenes existentes siguen funcionando sin unidad",
    ],
    2, JESUS, "Semana 10", "EP-008", "Preparación de los Datos", spec="SPEC-001",
)
nueva(
    "TA-096",
    "Disponibilidad: qué pasa cuando algo se cae",
    "Tirar a propósito cada pieza y medir qué se pierde y cuánto tarda en "
    "volver.",
    [
        "Arranque en frío de la API y del worker medido",
        "Se cae Redis, se cae el worker, se cae Supabase: qué ve el estudiante "
        "y qué queda en el expediente",
        "Ninguna caída pierde señales en silencio",
        "Tiempo de recuperación de cada caso, anotado",
    ],
    2, JESUS, "Semana 11", "EP-008", "Evaluación",
    dependencia="TA-086, TA-090",
)

# ---------------------------------------------------------------------------
# 6. Eficiencia — Pierre, y la pregunta de las APIs de terceros
# ---------------------------------------------------------------------------
nueva(
    "TA-097",
    "Transcripción sin depender de terceros",
    "Deepgram es la única API de pago del sistema. La alternativa propia ya "
    "está en el código (faster-whisper) pero no entra en la imagen.",
    [
        "Medido faster-whisper en el worker de producción contra el "
        "presupuesto de 10 s",
        "Si cabe: pasa a ser el proveedor por defecto y Deepgram queda de "
        "respaldo",
        "Si no cabe: queda escrito por qué, y el coste por examen de seguir "
        "con Deepgram",
    ],
    2, PIERRE, "Semana 10", "EP-008", "Evaluación", spec="SPEC-008",
    nota="Pregunta del profesor el 31/10: «¿cuántos son de los que están "
         "colgando por API?»",
)
nueva(
    "TA-098",
    "El modelo de similitud disponible en el worker",
    "En producción no está: el plan gratuito no da volúmenes y la imagen no "
    "lleva modelos, así que la similitud no se ha calculado nunca. Desde el "
    "31/10 el análisis ya no se pierde por eso, pero la condición sigue sin "
    "medirse.",
    [
        "Dentro de la imagen o descargado al arrancar, con la decisión escrita",
        "Un examen nuevo deja similarity no nulo en audio_analyses",
        "La comprobación de salud del worker avisa si falta",
    ],
    1, PIERRE, "Semana 10", "EP-004", "Paso a Producción", spec="SPEC-008",
    nota="Visto el 30/10 en los registros de Render. PR #61",
)
nueva(
    "TA-099",
    "Eficiencia del análisis de voz con 1, 30 y 1.000 estudiantes",
    "Lo que preguntó el profesor: no es lo mismo uno que treinta que mil.",
    [
        "Latencia p50 y p90 de la alerta de voz en los tres escenarios",
        "Profundidad de la cola y memoria del worker en cada uno",
        "Dónde se rompe el presupuesto de 10 s, si se rompe",
    ],
    2, PIERRE, "Semana 11", "EP-008", "Evaluación", spec="SPEC-008",
    dependencia="TA-097",
)

# ---------------------------------------------------------------------------
# 7. Escalabilidad y seguridad — Héctor
# ---------------------------------------------------------------------------
nueva(
    "TA-100",
    "Escalabilidad horizontal",
    "Lo que describió el profesor: levantar servicios según la carga.",
    [
        "Varias réplicas del worker y de la API con docker compose",
        "Demostrado que la cola reparte el trabajo entre réplicas",
        "Escrito hasta dónde llega el plan gratuito y qué cambia al salir de él",
    ],
    2, HECTOR, "Semana 11", "EP-008", "Evaluación", dependencia="TA-099",
)
nueva(
    "TA-101",
    "Pruebas de seguridad: inyección, concurrencia y denegación de servicio",
    "«Van a querer vulnerar como sea.» Probarlo, no suponerlo.",
    [
        "Inyección SQL contra cada entrada de la API",
        "Peticiones concurrentes sobre el mismo examen y la misma respuesta",
        "Ráfaga contra el límite de peticiones: se corta y la API sigue viva",
        "TLS y HSTS comprobados contra un intermediario",
    ],
    2, HECTOR, "Semana 11", "EP-008", "Evaluación",
    dependencia="TA-031",
    nota="Pedido por el profesor el 31/10. Parte de la auditoría de octubre",
)

# ---------------------------------------------------------------------------
# 8. Rediseño visual — Héctor, frente propio
# ---------------------------------------------------------------------------
nueva(
    "HU-033",
    "Rediseño de la portada",
    "Dirección de ThoughtLab adaptada: lienzo oscuro, tipografía como "
    "arquitectura y un solo acento, que es el ámbar de la marca.",
    [
        "El rojo no aparece como acento: queda para «alerta alta»",
        "Todo el texto pasa AA de contraste",
        "Sin desplazamiento horizontal en móvil",
        "Nada se carga de un CDN",
        "El resto de pantallas no cambia",
    ],
    2, HECTOR, "Semana 10", "EP-009", "Paso a Producción", status="Doing",
)
nueva(
    "HU-034",
    "Rediseño del acceso",
    "La pantalla de inicio de sesión con el mismo lenguaje que la portada.",
    [
        "Mismos tokens que la portada, encerrados en la parte pública",
        "Los errores de acceso se leen sin depender del color",
    ],
    1, HECTOR, "Semana 10", "EP-009", "Paso a Producción", dependencia="HU-033",
)
nueva(
    "HU-035",
    "Pase de oficio en las pantallas del docente y del estudiante",
    "No el lienzo oscuro: superficie clara y la paleta de severidad. "
    "Escalado tipográfico, huecos, estados vacíos y la tabla que se desborda.",
    [
        "La tabla de señales no se sale ni corta columnas",
        "Alta, media y baja siguen distinguiéndose a simple vista",
        "La pantalla del examen no pierde legibilidad",
    ],
    2, HECTOR, "Semana 12", "EP-009", "Paso a Producción",
    dependencia="HU-032",
)

SALIDA.open("w", encoding="utf-8-sig", newline="").close()
with SALIDA.open("w", encoding="utf-8-sig", newline="") as destino:
    escritor = csv.DictWriter(destino, fieldnames=COLUMNAS)
    escritor.writeheader()
    escritor.writerows(filas)

print(f"escrito: {SALIDA.name} con {len(filas)} filas")
