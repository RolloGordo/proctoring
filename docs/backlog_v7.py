"""Backlog v7: mete lo que se acordo en la daily del 13/10 y que no estaba.

El v6 se escribio sin esa reunion delante, asi que faltaban encargos concretos
—el importador de PDF entre ellos— y la fecha limite era la equivocada.
"""

from __future__ import annotations

import csv
from pathlib import Path

RAIZ = Path(r"C:\Users\Usuario\Desktop\proctoring")
ENTRADA = RAIZ / "docs" / "Backlog_v6_real.csv"
SALIDA = RAIZ / "docs" / "Backlog_v7_real.csv"

HECTOR = "hsilvav2@upao.edu.pe"
RIDER = "rrodriguezr36@upao.edu.pe"
JESUS = "jlimayc1@upao.edu.pe"

S7_INICIO = "2026-10-12"
LIMITE_EQUIPO = "2026-10-15"  # jueves: lo acordado en la daily
LIMITE_HECTOR = "2026-10-16"  # el despliegue va despues de recibir lo de todos

filas = list(csv.DictReader(ENTRADA.open(encoding="utf-8-sig")))
COLUMNAS = list(filas[0].keys())

# ---------------------------------------------------------------------------
# 1. La fecha limite real
#
# En la daily: "Maximo jueves entonces, chicos", porque el viernes es la expo
# de Corpus y el jueves Jesus tiene tesis. El v6 decia viernes.
# ---------------------------------------------------------------------------
for f in filas:
    if f["Semana"].strip() != "Semana 7":
        continue
    f["Fecha Fin"] = LIMITE_HECTOR if f["Responsable"] == HECTOR else LIMITE_EQUIPO

# ---------------------------------------------------------------------------
# 2. Web **y** escritorio, en las dos
#
# Se dijo tres veces y enfatico: "Todos se encargan de web y escritorio, no
# solamente en un solo lado". No estaba en ningun criterio.
# ---------------------------------------------------------------------------
EN_LAS_DOS = (
    "- Funciona igual en la web y en la aplicacion de escritorio, no solo en una"
)
PARA_AMBAS = {
    "TA-018", "TA-071", "TA-072", "TA-075", "HU-025", "HU-027", "HU-029", "TA-077",
}
for f in filas:
    if f["Código"] in PARA_AMBAS:
        f["Criterios de Aceptación"] = f["Criterios de Aceptación"] + "\n" + EN_LAS_DOS

# ---------------------------------------------------------------------------
# 3. Lo que se encargo en la daily y no estaba escrito
# ---------------------------------------------------------------------------
orden = max(int(f["Orden"]) for f in filas)


def nueva(codigo, titulo, descripcion, criterios, puntos, responsable,
          spec, epica, fase, notas="", dependencia="", prioridad="Alta"):
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
        "Fecha Fin": LIMITE_HECTOR if responsable == HECTOR else LIMITE_EQUIPO,
        "Fase": fase,
    }


DE_LA_DAILY = [
    nueva(
        "TA-080",
        "Importar PDF y otros formatos a un banco de preguntas",
        "Hoy el importador solo acepta XML de QTI. Un docente tiene sus "
        "preguntas en los documentos que ya usa, no en QTI, y escribirlas una a "
        "una es justo lo que hace que no use la herramienta.",
        [
            "Se puede importar un documento con preguntas y queda como banco",
            "La vista previa dice a que banco va a ir antes de confirmar",
            "Un documento que no se entiende lo dice, en vez de crear preguntas rotas",
            "Probado con un archivo real del docente, no con uno inventado para la prueba",
        ],
        "2 pt",
        RIDER,
        "SPEC-003",
        "EP-001",
        "Paso a Producción",
        notas=(
            "Encargado en la daily del 13/10: «¿por que solamente pide XML? "
            "¿Que pasa si el profesor quiere acumular los PDFs que tiene de toda "
            "la semana y convertirlos en un banco?». No estaba en el v6 porque "
            "ese backlog se escribio sin la daily delante."
        ),
    ),
    nueva(
        "TA-081",
        "Atar los bancos de preguntas a un curso",
        "Los bancos existen sueltos. Un docente con varios cursos no tiene como "
        "saber cual banco es de cual, y la pantalla llega a decir «mis bancos» y "
        "«no tienes ningun curso» a la vez.",
        [
            "Un banco se puede asociar a un curso del propio docente",
            "La lista se puede ver por curso",
            "Un banco sin curso sigue funcionando: los que ya existen no se rompen",
        ],
        "2 pt",
        RIDER,
        "SPEC-003",
        "EP-001",
        "Paso a Producción",
        notas="De la daily del 13/10: «bancos de preguntas a cursos especificos, tambien ver esa funcionalidad».",
    ),
    nueva(
        "TA-082",
        "Probar y arreglar el apartado de cursos",
        "Nadie ha creado un curso todavia, asi que esa parte no se ha usado "
        "nunca de verdad. Recorrerla entera y corregir lo que aparezca.",
        [
            "Crear un curso, matricular estudiantes y verlos listados",
            "Las pantallas no se contradicen entre si",
            "Cada fallo encontrado queda anotado con como reproducirlo",
        ],
        "1 pt",
        RIDER,
        "SPEC-002",
        "EP-001",
        "Evaluación",
        notas="De la daily: «yo no he creado hasta ahorita ningun curso, tambien te queda por testear».",
        prioridad="Media",
    ),
    nueva(
        "TA-083",
        "La camara sigue encendida durante todo el examen",
        "No basta con pedirla al empezar: tiene que seguir activa hasta que el "
        "estudiante entregue. Si se apaga a mitad —la cierra, la desenchufa, "
        "otra aplicacion se la lleva— hay que notarlo y decirlo.",
        [
            "Se detecta que la camara dejo de emitir y se avisa al estudiante",
            "El docente ve que ese estudiante se quedo sin camara",
            "Quedarse sin camara NO expulsa: queda registrado y decide el docente",
            "Probado desenchufando la camara a mitad de examen",
            "Funciona igual en la web y en la aplicacion de escritorio, no solo en una",
        ],
        "2 pt",
        JESUS,
        "SPEC-007",
        "EP-003",
        "Paso a Producción",
        notas=(
            "De la daily: «que se quede prendido durante todo el examen». Jesus ya "
            "detecta el evento 'ended' de la pista; falta cerrar el aviso al "
            "docente y probarlo de verdad."
        ),
    ),
]

salida = filas + DE_LA_DAILY
with SALIDA.open("w", encoding="utf-8-sig", newline="") as destino:
    escritor = csv.DictWriter(destino, fieldnames=COLUMNAS)
    escritor.writeheader()
    escritor.writerows(salida)

# --- las mismas comprobaciones que en el v6
codigos = [f["Código"] for f in salida]
assert len(codigos) == len(set(codigos)), "hay codigos repetidos"
assert len({int(f["Orden"]) for f in salida}) == len(salida), "hay ordenes repetidos"
assert not [f for f in salida if f["Status"] == "Done"], "nada puede estar en Done"
assert not [f for f in salida if f["Horas estimadas"] or f["Horas reales"]], "las horas van vacias"

SEMANA_SPRINT = {4: "Sprint 0", 5: "Sprint 0", 6: "Sprint 1", 7: "Sprint 1"}
for f in salida:
    if not f["Semana"]:
        continue
    n = int(f["Semana"].split()[-1])
    esperado = SEMANA_SPRINT.get(n, "Sprint 2" if n <= 11 else "Cierre")
    assert f["N° Sprint"] == esperado, f"{f['Código']}: {f['Semana']} con {f['N° Sprint']}"

s7 = [f for f in salida if f["Semana"].strip() == "Semana 7"]
assert all(f["Fecha Fin"] in (LIMITE_EQUIPO, LIMITE_HECTOR) for f in s7)

print(f"{len(salida)} filas -> {SALIDA.name}  ({len(DE_LA_DAILY)} nuevas de la daily)")
print(f"semana 7: {len(s7)} tareas, limite {LIMITE_EQUIPO} para el equipo")
