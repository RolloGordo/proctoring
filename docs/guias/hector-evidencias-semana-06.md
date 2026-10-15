# Héctor · qué hice entre el 5/10 y el 9/10

Material para redactar el informe y sacar capturas. Todo lo de aquí sale del
repositorio y de la base real, no de memoria: cada línea tiene su commit o su
comprobación detrás.

## En números

| | |
|---|---|
| Commits propios | **27** (05/10 15:00 → 09/10 18:52) |
| Líneas | **+23 022 / −1 121** |
| Archivos distintos tocados | **198** |
| PR fusionados en la ventana | **19** — 13 míos y **6 de compañeros** que revisé e integré |
| Pruebas nuevas | **239** en 13 archivos nuevos de la API · **44** en 3 de la web |
| Suite completa hoy | 847 (API) + 74 (web) + 41 (escritorio) + 76 (IA) = **1 038** |
| Migraciones mías aplicadas y verificadas | **3** |
| Endpoints que expone la API | **33** |

---

## Tarea por tarea

### HU-003 — Calificación automática de preguntas objetivas

**Commits:** `2a1cc8e`, `a1a35a0` (05/10) · **PR #19**

Al entregar, la API corrige sola lo objetivo (opción múltiple, verdadero/falso,
numérico con tolerancia) y deja marcado lo que necesita corrección a mano. El
`a1a35a0` es el arreglo de leer de vuelta las columnas de calificación desde
Supabase, que no estaban viajando.

**Archivos:** `question_repository.py` (memoria y Supabase), `answer_repository.py`,
`schemas.py`, `PanelEstudiante.tsx`, `Participantes.tsx`.

**Captura:** `/estudiante` con un examen entregado — se ve la nota. Y
`/sesiones/{id}/participantes`, columna **Nota**.

---

### TA-010 — Cálculo de riesgo desglosado por señal · HU-004 — API de revisión de caso · HU-007 — Revisión y decisión justificada

**Commit:** `246de8b` (05/10) · **PR #21**

Las tres salen del mismo commit porque son la misma pieza vista desde tres
capas. El riesgo **no es un número suelto**: se desglosa por señal, diciendo
cuántas veces ocurrió, cuánto duró y cuántos puntos aporta cada una. Es lo que
convierte «100, nivel alto» en algo que el docente puede discutir.

La decisión exige **justificación de 10 caracteres como mínimo** y no se edita:
se agrega otra. Es evidencia, no un campo de formulario.

**Archivos:** `domain/risk.py` (109 líneas), `domain/decision.py` (99),
`use_cases/review_case.py` (162), `routers/review.py` (94),
`decision_repository.py` (memoria y Supabase), `RevisionCaso.tsx` (272).
**Pruebas:** `test_case_review.py` (333 líneas) y `test_decision_and_risk.py` (190).

**Captura:** ya la tienes — la pantalla de **RIESGO** con el desglose
(`Salió de la ventana` 9 veces, 1 min 28 s, 50 pts) y la de **TU DECISIÓN** con
la justificación obligatoria y el contador `(0/10)` en rojo. Esas dos valen por
las tres tareas. Añade la **LÍNEA DE TIEMPO** con las 11 señales.

> Dato para el informe: la captura que tienes muestra `anydesk` y `discord`
> detectados como aplicación sospechosa. Eso es el módulo de Rider alimentando
> mi cálculo de riesgo — sirve para enseñar que las piezas están integradas, no
> solo escritas.

---

### EN-016 — Portada pública y paneles de docente y estudiante

**Commit:** `3840f84` (05/10) · **PR #18**

**Archivos nuevos:** `Portada.tsx` (263), `PanelDocente.tsx` (264),
`PanelEstudiante.tsx` (166), `Capas.tsx` (182, el marco y la barra lateral).

**Captura:** `/` (portada), `/docente`, `/estudiante`. La barra lateral con
PANEL / MIS EXÁMENES / CREAR EXAMEN / BANCOS / MIS CURSOS ya sale en tus
capturas.

---

### EN-017 — Cursos y matrícula de estudiantes

**Commit:** `133c41e` (05/10) · **PR #20**

Además de los cursos, aquí es donde la sala de espera pasó a mostrar el
**nombre** del estudiante en vez de un UUID.

**Captura:** `/cursos`, `/cursos/{id}` con alumnos matriculados, y
`/sesiones/{id}/participantes` mostrando nombres.

---

### HU-019 — Banco de preguntas reutilizable · TA-053 — Sorteo determinista

**Commits:** `4cf3511`, `eb6aed5` (06/10) · **PR #26**

Lo importante de TA-053 y lo que conviene explicar en el informe: el sorteo es
**determinista**. La semilla es la matrícula, no el estudiante. Eso significa
que si alguien recarga la página a mitad del examen recibe **exactamente** las
mismas preguntas, y que un segundo intento trae otras. Sin eso, recargar
perdería lo respondido.

Y vive en un solo sitio (`application/exam_questions.py`), compartido por quien
sirve el examen y quien lo califica: si cada uno tuviera su copia, se podría
calificar a alguien por preguntas que nunca vio.

**Archivos:** `domain/question_bank.py`, `use_cases/manage_banks.py`,
`routers/banks.py`, `question_bank_repository.py` (memoria y Supabase),
`Bancos.tsx`, `Banco.tsx`, `BancosDelExamen.tsx`, `EditorPregunta.tsx`.
**Migración:** `20261006120000_question_banks.sql`.
**Pruebas:** `test_question_bank.py` (20) + `test_banks.py` (20).

**Captura:** `/bancos` (ya la tienes, con «Banco de prueba · 2 preguntas»),
`/bancos/{id}` con las preguntas dentro, y `/sesiones/nueva` con la casilla del
banco marcada (también la tienes). Para enseñar el sorteo: crea un banco con 20
preguntas, pon «preguntas por estudiante: 5», y captura dos recargas seguidas
del examen mostrando **las mismas 5**.

---

### HU-020 — Editar, cancelar y borrar un examen · TA-054 — Nota sobre 20

**Commits:** `ab15f84`, `cc7f06a` (06/10) · **PR #27**   

Salió de un problema que me dijiste: un docente que se equivoca al crear no
podía arreglar nada. Hay tres verbos distintos a propósito:

- **Editar** lo que se equivocó.
- **Cancelar**: retira el examen y conserva todo (eventos, alertas, respuestas).
  Quien use el código lee «tu docente canceló este examen», no un error
  cualquiera.
- **Borrar**: solo si no entró nadie. Para el examen recién creado con la fecha
  mal.

TA-054 es la nota sobre 20 —la escala peruana— con los puntos de cada pregunta
repartidos proporcionalmente, para poder poner 2 puntos a una y 1 a otra sin
hacer cuentas.

**Archivos:** `use_cases/edit_exam_session.py`, `use_cases/edit_questions.py`,
`EditarSesion.tsx`.
**Migración:** `20261007020000_exam_editing.sql` (`max_score`, `cancelled_at`).
**Pruebas:** `test_edit_exam_session.py` (27), `test_edit_questions.py` (18),
`test_edit_exams.py` (28), `test_escala_de_nota.py` (14).

**Captura:** `/sesiones/{id}/editar` entera, con las tres zonas (editar, retirar,
borrar) y los textos que explican la diferencia.

---

### TA-055 — Endpoint de importación QTI y paquetes SCORM

**Commit:** `590c4cd` (09/10) · **PR #31**

`POST /api/v1/question-banks/{bank_id}/import/qti`. Acepta un XML suelto o un
paquete comprimido, y distingue uno de otro mirando los primeros bytes
(`PK\x03\x04`), no la extensión.

Lo que conviene contar: el lector de paquetes tiene **tres límites** contra un
zip malicioso — máximo 300 archivos, 20 MB descomprimidos y una razón de
expansión de 100. Un zip de 1 MB que se expande a 10 GB se rechaza antes de
tocar el disco.

Y una decisión de diseño: un ítem que no se entiende **no hace fallar la
importación**. Vuelve en `issues`, para que importar cuarenta preguntas no se
caiga por una.

**Archivos:** `adapters/inbound/qti/importer.py`, `adapters/inbound/qti/package.py`,
`ports/qti_parser.py`, `use_cases/import_qti.py`, `ImportarQti.tsx`.
**Pruebas:** `test_import_qti.py` (25).

**Captura:** `/bancos/{id}`, el bloque de importar, con un QTI real subido y el
resultado («N preguntas importadas, M con problemas»).

---

### HU-011 — Reglas y seguridad del examen

**Commits:** `9c7f360`, `898cfb3` (09/10) · **PR #34** · más `4cf3511` (barajado)

Cuatro reglas. Dos ya estaban (barajar preguntas y opciones, subconjunto del
banco) y dos las cerré el 9:

**Código de acceso retenido hasta la hora de inicio.** La columna
`reveal_code_at_start` existía desde la primera migración y **no la leía nadie**.
Ahora funciona por omisión: la API no manda `access_code` hasta `starts_at`.
Esconderlo solo en la pantalla sería decoración — viajaría igual en el JSON.

**Sin volver atrás.** `allow_back_navigation` se guardaba y no se cumplía en
ninguna parte, porque el examen se pintaba entero en una lista y «volver atrás»
ni siquiera existía. Ahora va de una pregunta en una y la regla la aplica la
API: una pregunta ya respondida no se vuelve a responder. Esconder el botón no
es cumplir la regla; la petición se puede repetir.

Eso arregló además algo que el propio código tenía marcado como provisional: el
`question_id` de cada evento era «la primera sin responder», adivinado. Ahora es
la pregunta que el estudiante tiene delante — que es contra cuyo enunciado el
servicio de IA compara lo que dice en voz alta. Con la pregunta equivocada, ese
diferencial no mide nada.

**Pruebas:** `test_reveal_code.py` (10), `test_back_navigation.py` (6).

**Captura:** `/sesiones/nueva` con la casilla «Mostrar el código de acceso solo
al empezar» (ya la tienes). Después, `/sesiones` mostrando `· · · · · ·` en la
columna CÓDIGO en vez del código. Y el examen del estudiante: «Pregunta 1 de 2»
con el aviso «Este examen no permite volver a una pregunta ya respondida», y la
misma pregunta ya respondida con los campos en gris.

---

### HU-022 — Monitoreo en vivo

**Commit:** `2929961` (09/10) · **PR #34** · *la tarea más grande de la semana*

El docente ve la cámara del estudiante mientras rinde. El fotograma viaja por
Supabase Realtime y **se pierde**: no pasa por la API, no entra en Storage y no
queda en ninguna tabla.

Tres decisiones que conviene defender en el informe:

1. **Un canal por estudiante, no por sesión.** Con un canal común, para publicar
   su propio fotograma el estudiante tendría que poder unirse, y unirse implica
   poder recibir: vería la cámara de sus compañeros.
2. **Si nadie mira, no se envía.** El estudiante se entera por *presence* de que
   el docente entró al canal, y solo entonces captura. Es una promesa más fuerte
   que «sale siempre pero no se guarda», y además no gasta la cuota de Realtime.
3. **La autorización es RLS sobre `realtime.messages`**, separada por tipo de
   mensaje: el fotograma solo lo publica el propio estudiante matriculado, solo
   lo lee el docente dueño del examen, y la presencia la escriben ambos.

**Archivos:** `supervision/monitoreo.ts` (el contrato de las dos puntas),
`components/CamaraEnVivo.tsx`, `supervision/camara.ts`,
`supervision/useSupervision.ts`, `Participantes.tsx`.
**Migración:** `20261009180000_live_monitoring_channel.sql`.
**Pruebas:** `monitoreo.test.ts` (23).

**Captura:** `/sesiones/{id}/participantes` con «Ver cámara» en un estudiante
rindiendo, y el recuadro con la imagen y el estado (`En vivo` / `Sin señal` /
`Desconectado`). En la pantalla del estudiante, el aviso «Tu docente está viendo
tu cámara en este momento. No se está grabando».

---

### TA-056 — URL firmada de lectura de evidencias

**Commit:** `fa59347` (09/10)

Los tres buckets son privados, así que hasta ahora una captura se subía y nadie
podía mirarla. `POST /sessions/{id}/students/{id}/evidence-url` devuelve una URL
firmada que **caduca a los 15 minutos**: un enlace copiado de la pantalla de
revisión no puede convertirse en acceso permanente a la cara de alguien.

La comprobación que importa: la ruta lleva el dueño en el prefijo
(`{session_id}/{student_id}/{uuid}.jpg`) y tiene que coincidir. Sin eso, un
docente con un examen propio podría pedir la URL de **cualquier** archivo del
bucket cambiando el cuerpo de la petición.

También metí los `audio_analyses` dentro del caso, para que el docente pueda
escuchar el fragmento marcado en vez de leer solo «posible consulta a IA».

**Pruebas:** `test_read_evidence.py` (13).

---

### DO-029 — Guías de trabajo por integrante

**Commits:** `accf8ed`, `efe1515` (06/10), `afc1f3c` (09/10)

Cuatro documentos: `docs/guias/README.md`, `rider-escritorio.md`,
`jesus-vision.md`, `pierreluiggi-ia-audio.md`, más `rider-semana-06.md` con el
cierre de la semana. 783 + 87 + 191 líneas. Qué archivo tocar, qué hacer
exactamente y cómo subirlo.

**Captura:** el árbol `docs/guias/` y un fragmento de uno de ellos.

---

### DO-030 — Revisión e integración de los PR de la semana 6

**Seis PR de compañeros revisados e integrados:** #28 y #35 (Rider), #29 y #33
(Jesús), #30 y #32 (Pierreluiggi).

Esto es lo que más cuesta explicar y más vale. Lo concreto que salió de esas
revisiones está en la sección de fallos, más abajo.

---

## Lo que no se ve en los commits

### Migraciones aplicadas y verificadas contra Supabase real

| Migración | Qué trae |
|---|---|
| `20261006120000_question_banks.sql` | `question_banks`, `question_bank_items`, `session_question_banks`, `questions.bank_id` |
| `20261007020000_exam_editing.sql` | `max_score` (20 por defecto) y `cancelled_at` |
| `20261009180000_live_monitoring_channel.sql` | Canal privado de monitoreo: 2 funciones y 2 políticas RLS sobre `realtime.messages` |

Ninguna se aplicó a ciegas: después de cada una comprobé por SQL que las tablas,
columnas y políticas quedaran como decía la migración.

### Servicios que levanté

- **API** en Docker (`docker compose up -d --build api`) y con `uvicorn` directo
  para pruebas sin autenticación.
- **Redis** y el **worker de IA** por compose.
- **Web** con Vite en `localhost:5173`.
- **Supabase Cloud** (proyecto `proctoring`): SQL, Auth, Storage y Realtime.

### Verificaciones empíricas — la parte de «investigación»

Esto es lo que yo contaría como investigación, porque en cada caso la respuesta
no estaba en la documentación y hubo que medirla:

1. **El canal de monitoreo, contra el proyecto real, con cuatro identidades.**
   Creé usuarios de prueba, un examen y una matrícula, abrí el canal como
   estudiante, como docente dueño, como otro docente y como un tercero, y
   comprobé qué deja pasar RLS. Resultado: 10 de 10 comprobaciones en verde.
   Lo borré todo al terminar.

   El hallazgo que casi me engaña: **`send()` responde `ok` aunque RLS rechace el
   mensaje**. El servidor acusa el envío, no el resultado de la política. Si me
   hubiera fiado de eso habría afirmado lo contrario de lo que pasa. Por eso la
   comprobación mide la **entrega**, y añadí un caso de control que demuestra
   que la prueba sí puede observar ese sentido.

2. **Cómo parsea Node un esquema no estándar** (`proctoring://`), para revisar lo
   de Rider: barra final, mayúsculas, `../`, `%2e%2e`, UUID codificado.

3. **Qué método acepta Storage en una URL firmada de subida.** POST responde 400
   y PUT responde 200. Ver abajo.

4. **El adaptador de Supabase contra la base real** para `reveal_code_at_start`:
   guardar, leer y borrar, comprobando que el valor viaja en los dos sentidos.

5. **Pruebas de mutación** en cada guarda nueva: reintroduje el fallo a mano y
   confirmé que la prueba se pone roja. Sin eso, una prueba que pasa no demuestra
   nada.

---

## Fallos que encontré y corregí

Esta sección vale para el informe más que la lista de funcionalidades: enseña
criterio, no volumen.

**Un examen con banco no se podía responder.** `commit 3a53561`.
Las respuestas se validaban contra las preguntas del examen. Una pregunta de
banco tiene `session_id` nulo y cuelga del banco, así que el examen se mostraba
entero y **rechazaba todas las respuestas**. Los bancos estaban entregados y la
funcionalidad estaba inservible; no lo habríamos visto hasta la demo.

**La subida de evidencia usaba POST, y Storage solo acepta PUT.** `commit 9dc0d4d`.
Salió al revisar el PR #28 de Rider. El fallo era silencioso: el 4xx se leía como
«no hay evidencia disponible» y el evento se enviaba sin `evidence_path`, así que
**no se habría guardado ni una captura**. Su prueba usaba un simulacro que
aceptaba cualquier método. Lo comprobé contra el Storage real y endurecí el
simulacro para que devuelva 400 a lo que no sea PUT.

**Tres entregas de compañeros venían de una base antigua** y habrían revertido
trabajo ajeno: `package.json` sin las dependencias de MediaPipe o de audio,
`tasks.py` pisando el worker del otro, `App.tsx` borrando una ruta. No fue culpa
de ellos —venían de un `git pull` viejo— pero había que fusionarlo a mano.

**Un PR apilado contra otra rama feature no disparaba el CI**, porque el flujo
solo corre en PR hacia `main` o `develop`. Y reapuntar la rama no lo vuelve a
disparar: hay que cerrar y reabrir.

---

## Lo que encontré y **no** he corregido

Para que lo menciones como hallazgo, o me digas que lo tome:

**La cabecera del examen dice «Supervisión activa» siempre.** En `Capas.tsx` es
texto fijo, no estado. Si la cámara falla o la supervisión no arranca, el
estudiante igual lee que lo están supervisando. En un sistema cuya promesa es ser
honesto sobre lo que observa, eso está al revés.

**Nadie pide la cámara al entrar.** Los endpoints de identidad existen
(`/me/reference-face`, `/exam/{id}/identity/check`) y el worker de verificación
facial también, pero **ningún cliente los llama**: la sala de espera nunca abre
la cámara y la verificación se queda en `pending`. Es HU-006, de Jesús, y sigue
en Open.

---

## Capturas que te faltan, en orden de valor

1. **Monitoreo en vivo funcionando** — es la tarea más grande y no tienes ninguna.
   Dos pantallas lado a lado: tú con «Ver cámara» abierta y el estudiante con el
   aviso de que lo estás mirando.
2. **Una pregunta a la vez con la regla de no volver atrás** — la pregunta
   respondida en gris y el aviso.
3. **El código retenido** — `· · · · · ·` en la lista de exámenes antes de la
   hora de inicio, y el código visible después.
4. **Importar un QTI** a un banco, con el resultado.
5. **Editar / cancelar / borrar** un examen.
6. **El sorteo determinista** — dos recargas con las mismas preguntas.
7. **El CI en verde** — la pestaña Actions con los 7 jobs del PR #34.
8. **La suite completa** — `uv run pytest` mostrando 847, y los otros tres.

Las de riesgo, decisión, bancos, crear examen y alertas en vivo ya las tienes.
