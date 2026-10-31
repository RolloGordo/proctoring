# -*- coding: utf-8 -*-
"""Backlog v8: el plan de la semana 9 a la 15, con lo medido el 28/10.

Tres cosas obligan a reordenar lo que había en el v7:

1. **El instalador pesa 111 MB y el objetivo es 10.** Medido: el ejecutable de
   Electron son 245 MB en disco él solo, y los 55 idiomas de Chromium otros 50
   (9 MB ya comprimidos). Recortando todo lo recortable el instalador baja a
   unos 85 MB, no a 10. Llegar a 10 obliga a dejar de empaquetar Chromium y
   usar el WebView del sistema. Por eso la semana 9 lleva un spike con corte:
   si no se puede, se sigue con Electron adelgazado y se dice en el informe.

2. **Lo que la meta SMART exige y nadie ha medido todavía**: accuracy y FPR por
   módulo. Las tareas existen (TA-037, TA-041) pero dependen de conjuntos
   etiquetados que siguen sin estar (TA-020, TA-029). Suben de prioridad.

3. **Defectos encontrados leyendo el código y la base de producción**, que no
   estaban escritos en ningún sitio: el intento nunca registra cuándo empezó y
   la verificación facial no se ha completado nunca de punta a punta.

Del chat de Gemini que pasó el profesor se toman tres ideas —el cliente sin
Chromium, el latido del cliente y el suavizado de los ángulos de cabeza— y se
descartan las demás por escrito en `docs/adr`, que para eso están.
"""

from __future__ import annotations

import csv
from pathlib import Path

RAIZ = Path(r"C:\Users\Usuario\Desktop\proctoring")
ENTRADA = RAIZ / "docs" / "Backlog_v7_real.csv"
SALIDA = RAIZ / "docs" / "Backlog_v8_real.csv"

HECTOR = "hsilvav2@upao.edu.pe"
RIDER = "rrodriguezr36@upao.edu.pe"
PIERRE = "rzecvallosb1@upao.edu.pe"
JESUS = "jlimayc1@upao.edu.pe"

SEMANAS = {
    "Semana 9": ("2026-10-26", "2026-10-30"),
    "Semana 10": ("2026-11-02", "2026-11-06"),
    "Semana 11": ("2026-11-09", "2026-11-13"),
    "Semana 12": ("2026-11-16", "2026-11-20"),
    "Semana 13": ("2026-11-23", "2026-11-27"),
}

filas = list(csv.DictReader(ENTRADA.open(encoding="utf-8-sig")))
COLUMNAS = list(filas[0].keys())
por_codigo = {f["Código"]: f for f in filas if f["Código"]}


def mover(codigo, semana, responsable=None, nota=None):
    """Cambia una tarea de semana —y de dueño si hace falta— con su fecha."""
    fila = por_codigo[codigo]
    fila["Semana"] = semana
    fila["Fecha Inicio"], fila["Fecha Fin"] = SEMANAS[semana]
    if responsable:
        fila["Responsable"] = responsable
    if nota:
        fila["Notas"] = (fila["Notas"] + " · " if fila["Notas"] else "") + nota


def exigir(codigo, criterio, nota=None):
    """Añade un criterio de aceptación sin borrar los que ya estaban."""
    fila = por_codigo[codigo]
    fila["Criterios de Aceptación"] = fila["Criterios de Aceptación"] + "\n" + criterio
    if nota:
        fila["Notas"] = (fila["Notas"] + " · " if fila["Notas"] else "") + nota


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


# ---------------------------------------------------------------------------
# 0. Épica nueva
#
# El peso del cliente no cabía en ninguna de las seis: no es detección, ni
# resultados, ni calidad. Y va a ser la mitad del trabajo de Rider.
# ---------------------------------------------------------------------------
filas.insert(7, {
    "Tareas": "Peso del cliente, rendimiento y pulido",
    "Orden": "6",
    "Código": "EP-007",
    "Descripción": "",
    "Criterios de Aceptación": "",
    "Estimación": "Agrupador",
    "Horas estimadas": "",
    "Horas reales": "",
    "Responsable": "",
    "N° Sprint": "",
    "Semana": "",
    "Spec": "",
    "Notas": "",
    "Dependencia": "",
    "Épica": "EP-007",
    "Prioridad": "Alta",
    "Status": "Open",
    "Fecha Inicio": "",
    "Fecha Fin": "",
    "Fase": "",
})

# ---------------------------------------------------------------------------
# 1. Semana 9 — lo que decide el resto del proyecto
# ---------------------------------------------------------------------------
nueva(
    "TA-084",
    "Spike: la aplicación de escritorio sin Chromium",
    "Probar Tauri v2 (WebView del sistema) con la web ya desplegada y "
    "responder si puede sustituir a Electron. Tres días como máximo.",
    [
        "Carga la web desplegada en la ruta del examen",
        "getUserMedia entrega cámara y micrófono sin que el estudiante toque nada",
        "crossOriginIsolated es true y el VAD de Silero arranca; si no, se anota "
        "cuánto tarda sin hilos",
        "setContentProtected impide la captura de pantalla, comprobado con una "
        "captura real, no leyendo la documentación",
        "Se listan los monitores conectados y los procesos en ejecución",
        "Peso del instalador medido, no estimado",
        "Documento con sí o no por cada punto y una recomendación",
    ],
    2, RIDER, "Semana 9", "EP-007", "Evaluación",
    status="Doing",
    nota="Corte el viernes 30: si falla cámara, micrófono o protección de "
         "contenido, se abandona y se sigue con TA-085. Evidencia: documento y "
         "capturas en Notion",
)
nueva(
    "TA-085",
    "Adelgazar el instalador actual sin cambiar de tecnología",
    "Quitar del empaquetado lo que la aplicación no usa. Se hace pase lo que "
    "pase con TA-084: es el plan B y también mejora el plan A.",
    [
        "Se empaquetan solo español e inglés en vez de los 55 idiomas",
        "Se quitan las bibliotecas que la aplicación no usa y se comprueba que "
        "sigue funcionando: cámara, micrófono, kiosco y detección",
        "Tamaño antes y después anotados en el repositorio",
    ],
    1, RIDER, "Semana 9", "EP-007", "Paso a Producción",
    status="Doing",
    nota="Medido el 28/10: instalador 111 MB; los idiomas son 9 MB ya "
         "comprimidos. Evidencia: los dos números",
)
nueva(
    "BU-007",
    "El intento no registra nunca cuándo empezó",
    "Participant.start() existe en el dominio y no lo llama ningún caso de "
    "uso: started_at es nulo en los 24 intentos de producción.",
    [
        "Se escribe al comenzar el intento",
        "Prueba unitaria que lo cubre",
        "El docente ve cuánto duró el examen de cada estudiante",
    ],
    1, HECTOR, "Semana 9", "EP-001", "Paso a Producción", spec="SPEC-001",
    status="Doing",
    nota="Encontrado el 28/10 leyendo el código y la base: 24 participantes, "
         "23 entregados, 0 iniciados",
)
nueva(
    "EN-018",
    "Llevar a producción la corrección de similitud y comprobarla",
    "La corrección está en develop desde el 20/10 y sin ella la alerta de "
    "consulta a IA no puede dispararse nunca.",
    [
        "Fusionada en main y desplegada",
        "Un examen nuevo deja similarity no nulo en audio_analyses",
        "La revisión de caso deja de decir «análisis incompleto»",
    ],
    1, HECTOR, "Semana 9", "EP-004", "Paso a Producción", spec="SPEC-008",
    status="Doing",
    nota="Evidencia: consulta a audio_analyses antes y después",
)
nueva(
    "BU-008",
    "La verificación facial no se ha completado nunca de punta a punta",
    "Se guarda la foto de referencia, pero ningún examen ha terminado con el "
    "estudiante verificado por comparación automática.",
    [
        "Un estudiante real queda con verification_status = verified",
        "Queda registrado el tiempo que tardó la comparación",
        "Si falla, el docente ve por qué y puede aprobar a mano",
    ],
    2, JESUS, "Semana 9", "EP-002", "Evaluación", spec="SPEC-003",
    dependencia="TA-021",
    nota="Es la condición para RN-001, que mide el P90 de esa misma comparación",
)
nueva(
    "HU-030",
    "Repaso de la interfaz del estudiante tras los exámenes reales",
    "Juntar en una sola tarea lo que fue saliendo al rendir exámenes de "
    "verdad, en vez de corregirlo de uno en uno.",
    [
        "El selector de micrófono y de cámara se ve siempre antes de empezar, "
        "haya uno o varios dispositivos",
        "Los avisos de supervisión no tapan la pregunta ni los botones",
        "Se ve en todo momento si la supervisión está activa y qué módulos lo están",
        "Ninguna respuesta se pierde al cambiar de pregunta ni al entregar",
        "Probado en Windows 10 y 11",
    ],
    1, RIDER, "Semana 9", "EP-002", "Evaluación", spec="SPEC-002",
    dependencia="TA-069",
    nota="Sale de los exámenes del 18 al 21/10. Evidencia: antes y después",
)

# ---------------------------------------------------------------------------
# 2. Semana 10 — migrar (o endurecer) y cerrar los agujeros de registro
# ---------------------------------------------------------------------------
nueva(
    "TA-089",
    "Cliente ligero, parte 1: ventana, kiosco y protección de contenido",
    "Primera mitad de la migración: la ventana del examen con todo lo que "
    "impide grabarla o salirse de ella.",
    [
        "La ventana abre en modo kiosco y carga la web del examen",
        "La protección de contenido deja la captura en negro",
        "Cámara y micrófono funcionan igual que en la versión de Electron",
        "La detección del navegador —mirada, rostro, voz, objetos— sigue dando "
        "las mismas señales en un examen de prueba",
    ],
    3, RIDER, "Semana 10", "EP-007", "Paso a Producción",
    dependencia="TA-084",
    nota="Solo si TA-084 sale bien. Si sale mal, esta tarea se cambia por el "
         "recorte profundo del empaquetado de Electron",
)
nueva(
    "TA-086",
    "Latido del cliente durante el examen",
    "Cada 15 segundos el cliente dice qué módulos siguen vivos. Es la "
    "respuesta al fallo que más caro nos ha salido: un módulo que se cae en "
    "silencio y un expediente que se lee igual que si no hubiera pasado nada.",
    [
        "El cliente informa de módulos activos, monitores y uso de CPU",
        "El docente ve «supervisión activa» o «sin señal desde las HH:MM»",
        "Queda registrado para la revisión posterior del caso",
    ],
    1, HECTOR, "Semana 10", "EP-003", "Paso a Producción", spec="SPEC-006",
    nota="Idea tomada del chat que pasó el profesor",
)
nueva(
    "TA-090",
    "Cola de señales que sobrevive al cierre de la aplicación",
    "Hoy la cola vive en memoria: si se cae la red y el estudiante entrega y "
    "cierra, las señales que quedaban dentro se pierden sin dejar rastro.",
    [
        "Las señales pendientes se guardan en disco antes de intentar enviarlas",
        "Al volver a abrir, se reenvía lo que quedó pendiente",
        "Prueba que corta la red, cierra y vuelve a abrir",
    ],
    2, HECTOR, "Semana 10", "EP-003", "Paso a Producción", spec="SPEC-006",
    nota="Idea tomada del chat que pasó el profesor, en versión simple",
)

# ---------------------------------------------------------------------------
# 3. Semana 11 — cerrar la migración y bajar los falsos positivos
# ---------------------------------------------------------------------------
nueva(
    "TA-091",
    "Cliente ligero, parte 2: monitores, procesos, foco y atajos",
    "Segunda mitad: todo lo que hoy hace el proceso principal de Electron.",
    [
        "Detecta monitores adicionales y los informa igual que antes",
        "Detecta las aplicaciones de la lista prohibida",
        "Detecta la pérdida de foco de la ventana",
        "Bloquea los atajos de copia y de cambio de ventana",
        "Las mismas señales que la versión de Electron en un examen de prueba, "
        "comparadas una a una",
    ],
    3, RIDER, "Semana 11", "EP-007", "Paso a Producción",
    dependencia="TA-089",
)
nueva(
    "TA-092",
    "Instalador del cliente ligero publicado y medido",
    "Publicar el instalador nuevo y comprobar que el estudiante lo instala sin "
    "pasos nuevos.",
    [
        "Peso del instalador anotado, comparado con los 111 MB de partida",
        "Se instala en un equipo limpio de Windows 10 y en uno de Windows 11",
        "La web ofrece la descarga y el aviso de versión nueva sigue llegando",
    ],
    1, RIDER, "Semana 11", "EP-007", "Paso a Producción",
    dependencia="TA-091",
    nota="Evidencia: el número, y la captura del instalador en un equipo limpio",
)
nueva(
    "TA-093",
    "Suavizado de los ángulos de cabeza antes del umbral",
    "Media móvil sobre yaw y pitch antes de comparar con el umbral, para que "
    "un temblor de cámara o un gesto corto no cuenten como mirada fuera.",
    [
        "El falso positivo se mide con el conjunto de TA-029 antes y después",
        "El FPR baja, o se escribe que no y se descarta el cambio",
    ],
    1, JESUS, "Semana 11", "EP-003", "Modelamiento / Aprendizaje",
    spec="SPEC-005", dependencia="TA-029",
    nota="Idea tomada del chat que pasó el profesor",
)
nueva(
    "DO-032",
    "Decisión de arquitectura: por qué el cliente deja (o no) Electron",
    "Dejar escrito el porqué, con los números medidos y con lo que se "
    "descartó del chat que pasó el profesor y por qué motivo.",
    [
        "ADR en docs/adr con los pesos medidos",
        "Dice qué se descartó: transcripción local, hooks globales de teclado "
        "y ratón, detector en C++ y interfaz nativa, con el motivo de cada uno",
    ],
    1, HECTOR, "Semana 11", "EP-000", "Evaluación",
    dependencia="TA-084",
)

# ---------------------------------------------------------------------------
# 4. Lo que la migración desplaza
#
# Rider no puede migrar el cliente y además hacer esto. Se mueve a la 12, y
# la accesibilidad de la web pasa a Hector, que es quien tiene hueco en la 11.
# ---------------------------------------------------------------------------
DESPLAZADA = "Movida en el v8: la migración del cliente ocupa las semanas 10 y 11"
for codigo in ("TA-033", "TA-039", "TA-040"):
    mover(codigo, "Semana 12", nota=DESPLAZADA)
mover("TA-026", "Semana 10",
      nota="Movida en el v8 para dejarle la semana 9 libre al spike del cliente")
REASIGNADA = ("Reasignada en el v8 porque Rider migra el cliente; "
              "confirmar en la daily")
mover("TA-034", "Semana 11", responsable=HECTOR, nota=REASIGNADA)
mover("TA-032", "Semana 12", responsable=HECTOR,
      nota=REASIGNADA + ". La lista vive en la configuración de la sesión, que "
           "es backend; el cliente solo la lee")
exigir("TA-033",
       "- Sobre la tecnología que quede después de TA-084, no sobre las dos")

# ---------------------------------------------------------------------------
# 5. Lo que ya estaba y necesita un criterio más exigente
#
# Son las tareas de las que depende la meta SMART. Estaban escritas de forma
# que se podían dar por hechas sin que el numero existiera.
# ---------------------------------------------------------------------------
exigir("TA-028",
       "- Queda activo en producción, o se escribe por qué no y qué falta para "
       "activarlo",
       nota="Sin esto la alerta de consulta a IA no puede dispararse nunca: "
            "exige las dos condiciones y la segunda está apagada")
exigir("TA-027", "- El conjunto de validación incluye voz real del equipo, no "
                 "solo fragmentos públicos")
exigir("TA-029",
       "- Incluye casos de mirada fuera, rostro ausente y persona adicional, y "
       "casos negativos que se parezcan a cada uno",
       nota="TA-037 no se puede medir sin esto")
exigir("TA-020",
       "- Incluye ruido de fondo real: otra persona en la habitación, tecleo y "
       "televisión",
       nota="TA-041 no se puede medir sin esto")
exigir("EN-014",
       "- El peso del instalador final queda anotado junto al de partida")

SALIDA.open("w", encoding="utf-8-sig", newline="").close()
with SALIDA.open("w", encoding="utf-8-sig", newline="") as destino:
    escritor = csv.DictWriter(destino, fieldnames=COLUMNAS)
    escritor.writeheader()
    escritor.writerows(filas)

print(f"escrito: {SALIDA.name} con {len(filas)} filas")
