"""Backlog v6: arregla los sprints mal puestos y replanifica la semana 7.

Principios de esta version:

- Nada se da por funcionando. Cada tarea nueva exige **probarlo contra el
  sistema real**, no contra pruebas automatizadas.
- Lo que no se cerro en la semana 6 pasa a la 7, con nota de que viene de
  atras. Dejarlo en la semana 6 mintiendo de "Doing" esconderia la deuda.
- El despliegue no entra en la semana 7: queda preparado y se publica cuando
  las pruebas de aceptacion esten en verde.
"""

from __future__ import annotations

import csv
from pathlib import Path

RAIZ = Path(r"C:\Users\Usuario\Desktop\proctoring")
ENTRADA = RAIZ / "docs" / "Backlog_v5_real.csv"
SALIDA = RAIZ / "docs" / "Backlog_v6_real.csv"

HECTOR = "hsilvav2@upao.edu.pe"
RIDER = "rrodriguezr36@upao.edu.pe"
PIERRE = "rzecvallosb1@upao.edu.pe"
JESUS = "jlimayc1@upao.edu.pe"

S7_INICIO, S7_FIN = "2026-10-12", "2026-10-16"

filas = list(csv.DictReader(ENTRADA.open(encoding="utf-8-sig")))
COLUMNAS = list(filas[0].keys())
por_codigo = {f["Código"]: f for f in filas}

# ---------------------------------------------------------------------------
# 1. Sprints mal puestos
#
# Tres tareas decian "Sprint 2" con fechas 05/10-09/10 y Semana 6, que es
# Sprint 1. Con eso, cualquier conteo por sprint salia mal.
# ---------------------------------------------------------------------------
for codigo in ("HU-011", "SP-010", "HU-015"):
    assert por_codigo[codigo]["N° Sprint"] == "Sprint 2", codigo
    por_codigo[codigo]["N° Sprint"] = "Sprint 1"

# ---------------------------------------------------------------------------
# 2. Lo que no se cerro en la semana 6 pasa a la 7
# ---------------------------------------------------------------------------
ARRASTRADAS = {
    "DO-004": "Venia de la semana 6: las mediciones siguen sin tomarse.",
    "TA-015": "Venia de la semana 6: los cinco criterios siguen sin marcar.",
    "EN-011": "Venia de la semana 6: falta probarlo en otra maquina.",
    "TA-060": "Venia de la semana 6: no hay ningun Release publicado.",
    "TA-062": "Venia de la semana 6: no hay medicion de similitud ni de voz sintetica.",
}
for codigo, nota in ARRASTRADAS.items():
    fila = por_codigo[codigo]
    fila["Semana"] = "Semana 7"
    fila["N° Sprint"] = "Sprint 1"
    fila["Fecha Inicio"], fila["Fecha Fin"] = S7_INICIO, S7_FIN
    fila["Notas"] = (nota + " " + fila["Notas"]).strip()

# ---------------------------------------------------------------------------
# 3. Las ceremonias y la revision del backlog las lleva el Scrum Master
# ---------------------------------------------------------------------------
por_codigo["DO-007"]["Responsable"] = HECTOR
por_codigo["DO-007"]["Notas"] = (
    "El profesor esperaba seis ceremonias y encontro una. Dos dailies por "
    "semana, grabadas, video en Drive y acuerdos escritos en Notion."
)

# ---------------------------------------------------------------------------
# 4. Tareas nuevas de la semana 7
# ---------------------------------------------------------------------------
orden = max(int(f["Orden"]) for f in filas)


def nueva(
    codigo: str,
    titulo: str,
    descripcion: str,
    criterios: list[str],
    puntos: str,
    responsable: str,
    spec: str,
    epica: str,
    fase: str,
    notas: str = "",
    dependencia: str = "",
    prioridad: str = "Alta",
) -> dict[str, str]:
    global orden
    orden += 1
    return {
        "Tareas": titulo,
        "Orden": str(orden),
        "Código": codigo,
        "Descripción": descripcion,
        "Criterios de Aceptación": "\n".join(f"- {c}" for c in criterios),
        "Estimación": puntos,
        "Horas estimadas": "",
        "Horas reales": "",
        "Responsable": responsable,
        "N° Sprint": "Sprint 1",
        "Semana": "Semana 7",
        "Spec": spec,
        "Notas": notas,
        "Dependencia": dependencia,
        "Épica": epica,
        "Prioridad": prioridad,
        "Status": "Open",
        "Fecha Inicio": S7_INICIO,
        "Fecha Fin": S7_FIN,
        "Fase": fase,
    }


NUEVAS = [
    # ---------------------------------------------------- Pierreluiggi: voz
    nueva(
        "TA-070",
        "Sustituir faster-whisper por la API de Deepgram",
        "Cambiar por dentro measure_audio para que la transcripcion salga de "
        "Deepgram y no de un modelo local. El contrato del worker no cambia: "
        "sigue recibiendo el mismo trabajo y devolviendo los mismos campos.",
        [
            "La transcripcion sale de Deepgram y el worker devuelve los mismos campos de antes",
            "La clave vive en variables de entorno y GitHub Secrets, nunca en el repositorio",
            "faster-whisper sale de pyproject y de requirements, y la imagen adelgaza",
            "model_versions registra que motor se uso, para poder comparar mediciones",
            "Se guarda la medicion anterior con faster-whisper como comparativa",
            "Probado con un audio real subido a Storage, no con un simulacro",
        ],
        "2 pt",
        PIERRE,
        "SPEC-008",
        "EP-004",
        "Modelamiento / Aprendizaje",
        notas=(
            "Lo pidio el profesor. El motivo real no es el peso del instalador "
            "(el modelo corre en el servidor, no viaja en el .exe) sino que un "
            "modelo de 1 GB no entra comodo en un Space gratuito."
        ),
    ),
    nueva(
        "TA-071",
        "Pedir y probar el microfono antes de empezar el examen",
        "En la sala de espera, pedir el microfono y demostrar que entra sonido "
        "antes de que el examen empiece. Hoy se abre al empezar y el estudiante "
        "se entera tarde de que estaba silenciado o de que eligio el aparato "
        "equivocado.",
        [
            "Se pide el microfono en la sala, despues del consentimiento",
            "Una barra de nivel se mueve al hablar: ver que llega sonido, no leer que llega",
            "Se pide una frase corta y se confirma que el VAD la detecta",
            "Un microfono que falla NO impide rendir: se avisa, queda registrado y decide el docente",
            "Los errores dicen que hacer: elegir otro aparato, quitar el silencio, dar permiso",
            "Probado con el microfono desconectado, silenciado y con permiso denegado",
        ],
        "2 pt",
        PIERRE,
        "SPEC-008",
        "EP-002",
        "Paso a Producción",
        notas="Reutiliza abrirCamara({ audio: true }), que ya resuelve permisos y errores.",
    ),
    nueva(
        "TA-072",
        "Completar el guardado del fragmento de audio senalado",
        "Cerrar la cadena: que el fragmento marcado se suba, se enlace al "
        "evento y el docente pueda reproducirlo desde la revision del caso. "
        "Hay piezas puestas, pero nadie lo ha visto funcionar de punta a punta.",
        [
            "Un fragmento con alerta se reproduce desde la revision del caso",
            "Solo se sube audio con habla, nunca el microfono continuo",
            "Se mide cuanto espacio ocupa por examen y se anota",
            "Probado contra Storage real, no contra el almacenamiento en memoria",
        ],
        "1 pt",
        PIERRE,
        "SPEC-008",
        "EP-004",
        "Evaluación",
        dependencia="TA-070",
        notas="El profesor pregunto por la acumulacion de espacio. Storage gratuito tiene limite.",
    ),
    # ---------------------------------------------------------- Jesus: camara
    nueva(
        "TA-073",
        "Calibrar los umbrales de mirada y persona adicional con datos propios",
        "Los umbrales de hoy (yaw 25 grados, min_faces 2, similitud 0.45) son "
        "un punto de partida razonado, no medido. Justificarlos con datos o "
        "proponer otros.",
        [
            "Cada umbral queda justificado con una medicion, no con una intuicion",
            "Si un umbral cambia, se cambia en exam_session.py y se explica por que",
            "Se prueba con poca luz, con lentes y a contraluz, no solo en condiciones buenas",
            "Si un numero no cumple la meta se anota igual: es un hallazgo, no un fracaso",
        ],
        "2 pt",
        JESUS,
        "SPEC-007",
        "EP-003",
        "Modelamiento / Aprendizaje",
        notas="Los umbrales viven en un solo sitio a proposito: se calibran ahi y los tres clientes se enteran.",
    ),
    nueva(
        "TA-074",
        "Medir accuracy y FPR de los detectores de vision",
        "El manifiesto del dataset de vision tiene solo la cabecera y no hay "
        "results/evaluation.json. Sin medicion no se puede afirmar que los "
        "detectores funcionan.",
        [
            "Dataset etiquetado con consentimiento, con manifiesto y procedencia",
            "results/evaluation.json con matriz de confusion, accuracy y FPR por detector",
            "La condicion 'mirando la pantalla, normal' es la mas poblada: mide falsos positivos",
            "Conjunto de prueba final separado del de calibrado",
            "Meta: accuracy >= 80 % y FPR < 20 % por detector",
        ],
        "2 pt",
        JESUS,
        "SPEC-007",
        "EP-006",
        "Evaluación",
        dependencia="TA-073",
        notas="El README del spike ya dice honestamente que esto esta pendiente. Mantener ese rigor.",
    ),
    nueva(
        "TA-075",
        "Probar la verificacion facial de punta a punta en el navegador",
        "HU-006 esta fusionada y la cadena de endpoints esta comprobada contra "
        "Supabase, pero nadie la ha visto correr en un navegador con sesion "
        "iniciada. Probarla como la usaria un estudiante.",
        [
            "Un estudiante real registra su foto de referencia desde la sala",
            "Pide la comparacion y la sala se actualiza sola cuando llega el resultado",
            "Una verificacion fallida deja esperando, no expulsa",
            "Probado con mala luz y con lentes, para ver que pasa cuando falla de verdad",
            "Capturas de pantalla de cada paso para la evidencia",
        ],
        "1 pt",
        JESUS,
        "SPEC-005",
        "EP-002",
        "Evaluación",
        notas="No dar por bueno lo que pasa pruebas automatizadas: esto hay que verlo funcionar.",
    ),
    # --------------------------------------------- Jesus + Pierre: avisos
    nueva(
        "HU-025",
        "Avisar al estudiante durante el examen de lo que se detecta",
        "Hasta ahora el estudiante veia las alertas al terminar. Avisarle en el "
        "momento y diciendole que se detecto, para que pueda corregir lo que "
        "sea un malentendido.",
        [
            "El aviso dice la senal concreta: 'se detecto una segunda persona', no un generico",
            "Un solo componente de aviso compartido entre camara y microfono",
            "No se repite el mismo aviso mientras la condicion siga activa",
            "El tono documenta, no acusa: nada de 'estas copiando'",
            "No tapa el enunciado de la pregunta",
            "Probado con los dos modulos disparando a la vez",
        ],
        "2 pt",
        f"{JESUS}, {PIERRE}",
        "SPEC-007/008",
        "EP-003",
        "Paso a Producción",
        notas=(
            "Que se pongan de acuerdo en el componente ANTES de escribir dos. "
            "Coordinarlo en la daily, no por mensajes sueltos."
        ),
    ),
    # ------------------------------------------------------- Rider: uso real
    nueva(
        "HU-026",
        "Que crear un examen y calificarlo se entienda sin que nadie lo explique",
        "Usar el sistema como si no lo hubiera construido uno mismo y anotar "
        "donde se traba. Crear examen pide muchos datos de golpe, banco y "
        "preguntas propias son dos caminos para lo mismo sin explicar cuando "
        "conviene cada uno, y editar/cancelar/borrar estan juntos sin que se "
        "distinga cual es el peligroso.",
        [
            "Queda claro que campos son obligatorios y cuales no",
            "Se explica cuando conviene un banco y cuando preguntas propias",
            "Las tres acciones de edicion se distinguen a simple vista",
            "El docente ve de donde sale la nota y puede corregir lo de desarrollo",
            "Un docente que no sea del equipo crea un examen sin ayuda",
        ],
        "2 pt",
        RIDER,
        "SPEC-003",
        "EP-001",
        "Paso a Producción",
        notas="Si a Hector no le queda claro el banco de preguntas, a un docente de verdad menos.",
    ),
    nueva(
        "HU-027",
        "Mas vistas para el estudiante",
        "El estudiante solo puede entrar, rendir y ver su nota. Falta lo "
        "evidente: sus examenes pasados y futuros, el detalle de uno rendido y "
        "que se le va a supervisar antes de aceptar.",
        [
            "Lista de examenes: los que vienen y los que ya rindio",
            "Detalle de un examen rendido: que respondio, que nota saco, que se le marco",
            "Antes de aceptar, se ve con claridad que se va a observar",
            "Probado con un estudiante que tenga varios examenes, no solo uno",
        ],
        "2 pt",
        RIDER,
        "SPEC-002",
        "EP-005",
        "Paso a Producción",
        notas="La pantalla de consentimiento es lo que hace honesto al sistema. Que se entienda.",
    ),
    nueva(
        "HU-028",
        "Descargar la aplicacion desde la portada",
        "La portada no tiene de donde bajar la aplicacion. Hace falta un "
        "apartado visible con el enlace al Release, para que sirve y que "
        "requisitos tiene.",
        [
            "Boton de descarga apuntando al GitHub Release",
            "Se explica por que hace falta: el examen se rinde ahi, no en el navegador",
            "Se dicen los requisitos y los permisos que va a pedir",
            "Probado descargando desde otra maquina",
        ],
        "1 pt",
        RIDER,
        "SPEC-006",
        "EP-000",
        "Paso a Producción",
        dependencia="TA-060",
        notas="Depende de que exista el Release. Publicarlo primero.",
    ),
    nueva(
        "TA-076",
        "El examen solo se rinde en la aplicacion, no en el navegador",
        "Hoy se puede rendir desde el navegador. Con la web publicada, "
        "cualquiera con el enlace se saltaria la supervision de escritorio "
        "entera: sin kiosco, sin procesos, sin monitores, sin proteccion de "
        "captura.",
        [
            "Las rutas de rendir y sala quedan bloqueadas fuera de la aplicacion",
            "El mensaje no es un error: dice que se rinde en la app y ofrece la descarga",
            "El docente sigue usando la web para todo lo suyo",
            "Probado en navegador normal y dentro de la aplicacion",
        ],
        "1 pt",
        RIDER,
        "SPEC-006",
        "EP-002",
        "Paso a Producción",
        dependencia="HU-028",
        notas="window.api solo existe dentro de Electron. Ya se usa asi en AccesoExamen.tsx.",
    ),
    nueva(
        "TA-077",
        "Corregir los textos que dicen 'Panel del docente' al estudiante",
        "El titulo de la pagina es global, asi que la ventana de la aplicacion "
        "donde hay un estudiante rindiendo dice 'Panel del docente'. El "
        "estudiante lo ve.",
        [
            "El titulo cambia por ruta, o queda neutro",
            "Se revisan los demas textos que suponen que quien mira es el docente",
            "Comprobado dentro de la aplicacion, no solo en el navegador",
        ],
        "1 pt",
        RIDER,
        "SPEC-006",
        "EP-002",
        "Paso a Producción",
        prioridad="Media",
    ),
    nueva(
        "HU-029",
        "Mejorar el flujo del estudiante al rendir",
        "El examen va de una pregunta en una, pero al estudiante le falta "
        "saber donde esta: cuanto tiempo le queda, cuantas lleva y que pasa si "
        "se le cae la conexion.",
        [
            "Se ve el tiempo restante del examen",
            "Se ve en que pregunta va y cuantas quedan sin responder",
            "Al entregar, se confirma diciendo cuantas van sin responder",
            "Si se cae la conexion, el estudiante lo sabe y sabe que lo suyo esta guardado",
            "Probado cortando la red a mitad de examen",
        ],
        "2 pt",
        RIDER,
        "SPEC-002",
        "EP-002",
        "Paso a Producción",
        notas="Coordinar con HU-025: los avisos en vivo conviven con esta pantalla.",
    ),
    # ----------------------------------------------------------- Hector
    nueva(
        "TA-078",
        "Dejar el despliegue preparado, sin publicar todavia",
        "Crear cuentas, configurar variables y dejar el CI/CD listo, pero no "
        "publicar hasta que las pruebas de aceptacion esten en verde. "
        "Desplegar algo sin probar es ensenar una demo que se rompe.",
        [
            "Cuentas creadas: Vercel, Render, Hugging Face Spaces y Upstash",
            "Variables y secretos configurados en cada servicio y en GitHub Secrets",
            "CORS del dominio publico resuelto antes de publicar",
            "El instalador se construye apuntando a la web publicada, no a localhost",
            "Nada se publica hasta que TA-063, TA-064 y TA-065 esten en verde",
        ],
        "2 pt",
        HECTOR,
        "SPEC-001",
        "EP-000",
        "Paso a Producción",
        notas=(
            "web.ts apunta a localhost:5173 sin variable de entorno. Es el error "
            "que Rider no podia resolver en otra maquina."
        ),
    ),
    nueva(
        "TA-079",
        "Recorrido completo del sistema y registro de defectos",
        "Recorrer el sistema entero como lo haria un docente y un estudiante, "
        "anotando todo lo que falle o confunda. De aqui salen los defectos que "
        "se corrigen esta semana.",
        [
            "Recorrido: crear examen, codigo, entrar, verificar, rendir, detectar, entregar, revisar, decidir",
            "Cada fallo encontrado queda anotado con como reproducirlo",
            "Se prueban las tres pantallas que nadie ha visto funcionar: camaras en vivo, evidencia del caso, verificacion facial",
            "Se graba el recorrido completo",
        ],
        "2 pt",
        HECTOR,
        "SPEC-001",
        "EP-006",
        "Evaluación",
        notas="Tres pantallas pasan pruebas y nadie las ha visto correr con sesion iniciada.",
    ),
    nueva(
        "DO-031",
        "Revisar el backlog con cada integrante y cerrar sus tareas",
        "El Scrum Master de la semana repasa el backlog persona por persona, ve "
        "lo que hizo cada uno y va cerrando sus tareas una a una. Es la segunda "
        "daily.",
        [
            "Se revisa con los cuatro, uno por uno",
            "Cada tarea revisada queda cerrada o con lo que le falta anotado",
            "Los titulos se corrigen: lo que no tiene interaccion de usuario no es historia de usuario",
            "Queda grabado y los acuerdos escritos en Notion",
        ],
        "1 pt",
        HECTOR,
        "SPEC-001",
        "EP-000",
        "Definición del Problema",
        notas=(
            "El profesor fue explicito: el que lleva la semana revisa el backlog "
            "junto con su equipo, no cada uno por su lado."
        ),
    ),
]

# ---------------------------------------------------------------------------
# 5. El despliegue de produccion queda condicionado
# ---------------------------------------------------------------------------
por_codigo["EN-012"]["Dependencia"] = "TA-078"
por_codigo["EN-012"]["Notas"] = (
    "No se publica hasta que la prueba de humo y las dos de aceptacion esten "
    "en verde. El profesor pide desplegado en las semanas 7, 11 y 15; si la "
    "semana 7 no llega, se publica en cuanto llegue y se dice por que."
).strip()

salida = filas + NUEVAS
with SALIDA.open("w", encoding="utf-8-sig", newline="") as destino:
    escritor = csv.DictWriter(destino, fieldnames=COLUMNAS)
    escritor.writeheader()
    escritor.writerows(salida)

# ---------------------------------------------------------------------------
# Comprobaciones: que no se repita lo que ya fallo otras veces
# ---------------------------------------------------------------------------
codigos = [f["Código"] for f in salida]
assert len(codigos) == len(set(codigos)), "hay codigos repetidos"
ordenes = [int(f["Orden"]) for f in salida]
assert len(ordenes) == len(set(ordenes)), "hay ordenes repetidos"
assert not [f for f in salida if f["Status"] == "Done"], "nada puede estar en Done"
assert not [f for f in salida if f["Horas estimadas"] or f["Horas reales"]], "las horas van vacias"

SEMANA_SPRINT = {4: "Sprint 0", 5: "Sprint 0", 6: "Sprint 1", 7: "Sprint 1"}
for f in salida:
    if not f["Semana"]:
        continue
    numero = int(f["Semana"].split()[-1])
    esperado = SEMANA_SPRINT.get(numero, "Sprint 2" if numero <= 11 else "Cierre")
    assert f["N° Sprint"] == esperado, f"{f['Código']}: {f['Semana']} con {f['N° Sprint']}"

print(f"{len(salida)} filas -> {SALIDA.name}  ({len(NUEVAS)} nuevas)")
