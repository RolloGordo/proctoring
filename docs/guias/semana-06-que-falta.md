# Semana 6 · qué le falta a cada uno

Estado real al **10/10**, comprobado contra `develop` y contra el backlog, no de
memoria. Si algo aquí no coincide con lo que les dijo otra herramienta, manda
esto: aquí cada afirmación se verificó en el repositorio.

---

## Lo primero: **ya casi nada está bloqueado**

Rider dijo «hay unas que están vinculadas a otras, no se puede avanzar si no
terminan las que uno tiene». Eso **era** cierto hasta anoche. Ya no.

Lo que estaba enredado y cómo quedó:

| Esperaba | A que terminara | Estado |
|---|---|---|
| HU-023 (Rider) | TA-056 de Héctor — URL firmada de lectura | ✅ **en `develop`** |
| HU-015 (Rider) | HU-022 de Héctor — el canal de monitoreo | ✅ **en `develop`** |
| TA-017 (Jesús) | HU-006 del propio Jesús — la foto de referencia | ⚠️ depende de él mismo |
| TA-062 (Pierre) | Grabaciones del equipo | ⚠️ depende de **todos**, 10 minutos cada uno |

**Conclusión:** a día de hoy no hay ninguna tarea de nadie esperando a otra
persona, salvo que Pierre necesita que le graben audios. Todo lo demás es
trabajo propio.

**Antes de empezar, los tres:**

```bash
git checkout develop && git pull
```

```bash
docker compose up -d --build api
```

Ese segundo comando no es opcional. El contenedor de la API **no recarga solo**:
si no lo reconstruyen, seguirá sirviendo el código viejo y verán errores raros
como `Extra inputs are not permitted` en campos que sí existen. Pasa cada vez
que alguien toca `services/api`.

---

# Rider · 4 tareas

Lo tuyo ya fusionado: **PR #35** (`proctoring://`) y **PR #28** (capturas y
resultados). HU-005, TA-011, HU-008, TA-059 y EN-008 están implementados.

Una corrección a tu tabla, sin importancia para el trabajo pero sí para tu
ficha: en HU-015 pusiste «hay cámara individual». Ese componente
(`CamaraEnVivo.tsx`) es de Héctor, es parte de HU-022. **Lo tuyo es la
cuadrícula**, y es lo único que falta de esa tarea. Mejor que tu evidencia lo
diga así: queda más limpio que reclamar algo que el commit dice que es de otro.

### 1. Las mediciones · DO-004 + TA-015 — **empieza por aquí**

**Lo verifiqué:** en `apps/desktop/README.md` los cinco criterios siguen con
`- [ ]` y la tabla de la sección «SPEC-006: estado de mediciones» dice
*Pendiente* en las cinco filas.

Es lo más valioso que puedes hacer y **nadie más puede hacerlo**: necesita
Windows, cronómetro, un segundo monitor y Zoom o AnyDesk. Las pruebas
automatizadas no valen como evidencia de esto.

```powershell
$env:PROCTORING_DISABLE_CONTENT_PROTECTION=1; npm run dev --prefix apps/desktop
```

(Quita esa variable antes de la cuarta prueba, que es justo la de la pantalla en
negro.)

| # | Qué | Cómo medirlo | Meta |
|---|---|---|---|
| 1 | Pérdida de foco | Alt+Tab con cronómetro; compara con el `duration_ms` del evento | Un solo evento, ±200 ms |
| 2 | Monitor adicional | Conecta el segundo monitor y anota la hora; resta del `started_at` | < 5 s |
| 3 | Proceso sospechoso | Abre Zoom o AnyDesk y anota la hora; resta del `started_at` | < 15 s |
| 4 | Protección de captura | Sin la variable, haz una captura con ImprPant | La ventana sale en negro |

**Tres veces cada una**, y anota las tres. Una sola medición no dice nada: si
Alt+Tab da 180 ms, 190 ms y 950 ms, el problema es el 950.

Si algo no cumple la meta, **no lo ajustes para que cuadre**: anótalo y dilo. Un
número que no cumple es un resultado, no un fracaso, y vale más en el informe
que un número bonito sin respaldo.

**Entregas:** marca los `- [x]` que de verdad midas, rellena la tabla con los
números **observados** (no con la meta), y el vídeo va al Notion de Héctor.

### 2. El instalador en otro equipo y el Release · EN-011 + TA-060

**Lo verifiqué:** `gh release list` está **vacío**. El instalador existe en tu
máquina y no está publicado.

Instálalo en una computadora **sin Node y sin el repositorio** —que es la
situación real de un estudiante— y comprueba que instala, arranca en kiosco,
llega a la pantalla del código y **cierra bien** (que no quede el proceso
colgado). Anota la versión de Windows de esa máquina.

```bash
gh release create v1.0.0 apps/desktop/dist/desktop-1.0.0-setup.exe \
  --title "Proctoring Desktop 1.0.0" \
  --notes "Primera version instalable. Kiosco, proteccion de contenido, deteccion de foco, monitores y procesos."
```

### 3. HU-023 — Ver la evidencia en la revisión del caso

**Desbloqueado.** Está en `develop` lo que te faltaba:

- `api.evidenceUrl(sessionId, studentId, path, kind, token)` → `{ url, expires_in_seconds }`.
  El `path` es el `evidence_path` que ya viene en cada evento, tal cual.
  `kind` es `'image' | 'audio' | 'reference_face'`.
- El caso ahora trae `audio_analyses`: `transcript`, `similarity`,
  `synthetic_voice_score`, `matched_question_id` y un `alerted` que dice si ese
  fragmento generó alerta.

**Dos cosas que te van a morder si no las sabes:**

El enlace **caduca a los 15 minutos**. No lo pidas al cargar la página y lo uses
media hora después: pídelo cuando el docente vaya a mirar la captura.

La **ruta del audio no está en el análisis**, está en el evento. El análisis es
lo que se midió; el fragmento es evidencia del evento. Así que para el
reproductor: `analisis.event_id` → buscas ese evento → su `evidence_path` →
`api.evidenceUrl(..., 'audio')`.

**Archivo:** `apps/web/src/pages/RevisionCaso.tsx`. Hoy tiene cero `<img>` y cero
`<audio>`: lo comprobé.

### 4. HU-015 — Cuadrícula de cámaras en vivo

**Desbloqueado.** El componente existe y funciona:

```tsx
<CamaraEnVivo sessionId={id} studentId={p.student_id} teacherId={userId} nombre={p.student_name} />
```

Lo tuyo es componerlo en una cuadrícula en `apps/web/src/pages/SesionEnVivo.tsx`
con los estudiantes que están rindiendo (`can_take_exam && !submitted_at` de
`api.listParticipants`). Hay un ejemplo de **una sola** cámara ya funcionando en
`apps/web/src/pages/Participantes.tsx`, línea 149.

**Dos cosas que importan y no se ven en el tipo del componente:**

1. **Montar el componente es lo que hace que ese estudiante empiece a enviar.**
   El estudiante solo captura mientras el docente está en su canal. Una
   cuadrícula de 30 cámaras enciende 30 envíos. Si la clase es grande, pagina o
   monta solo las visibles. No las montes todas «por si acaso».
2. **No se graba, y el estudiante ve que lo estás mirando.** Si pones en pantalla
   algo tipo «grabando», estarías diciendo lo contrario de lo que el sistema
   hace. El texto que ya está en `Participantes.tsx` sirve de ejemplo.

Solo ofrécela si `live_monitoring` está en `session.modules` (viene con el preset
*Estricta*). Si no está activo, el estudiante no aceptó eso.

El contrato completo está en `apps/web/src/supervision/README.md`, sección «El
monitoreo en vivo no es un detector».

---

# Jesús · 1 tarea, y es la que desbloquea el flujo completo

Lo tuyo fusionado: **PR #29** y **PR #33**. SP-009 (detectores de visión),
TA-057 (auditoría de RLS) y TA-061 están implementados, y `face_pipeline.py`
existe con InsightFace.

### HU-006 — Registrar foto de referencia · *la única en Open*

Esta es **el agujero más visible del producto ahora mismo**: el estudiante entra
al examen y **nadie le pide la cámara**. Lo comprobé buscando en todo
`apps/web/src` y `apps/desktop/src`: ningún cliente llama a los endpoints de
identidad. Resultado: la verificación se queda en `pending` y el docente admite
a mano a todo el mundo.

**No te falta backend. Está todo hecho desde hace días:**

| Endpoint | Para qué |
|---|---|
| `POST /api/v1/me/reference-face` | El estudiante registra, una vez, la cara con la que se le comparará |
| `POST /api/v1/exam/{session_id}/identity/check` | Manda una captura al entrar y pide la verificación |
| `GET /api/v1/internal/face-jobs/{participant_id}` | El worker recoge el trabajo |
| `POST /api/v1/internal/sessions/.../identity-result` | El worker devuelve el resultado |

Y el worker también: `verify_face` en `services/ai/tasks.py` con
`face_pipeline.py`.

**Lo que falta es solo el cliente**, en `apps/web/src/pages/SalaDeEspera.tsx`:

1. Abrir la cámara (`abrirCamara` de `apps/web/src/supervision/camara.ts`, ya
   resuelve permisos y errores traducidos).
2. Capturar un fotograma (`capturarFotograma`, mismo archivo).
3. Subirlo **directo a Storage** con URL firmada —`POST /api/v1/evidence/upload-url`
   con `kind: "reference_face"`— y **con PUT, no POST**. Storage responde 400 a
   POST. Eso ya nos costó un fallo silencioso una vez.
4. Llamar a `identity/check` con la ruta.
5. La sala ya se actualiza sola por Realtime cuando llega el resultado.

**La regla que no se toca:** una verificación fallida **no expulsa a nadie**.
Deja al estudiante esperando y el docente lo admite a mano. Mala luz, lentes o
una cámara mala no pueden costarle el examen a nadie. Eso ya está así en la API;
que la pantalla no lo contradiga.

**Después, TA-017** (ArcFace) solo se puede medir de verdad cuando haya fotos de
referencia que comparar. Por eso HU-006 va primero.

### Y lo que te queda pendiente de SP-009 (no es Open, pero lo sabes)

Tu propio README lo dice y está bien que lo diga: *«las métricas de accuracy/FPR
siguen pendientes de medición. No se inventaron datos ni capturas.»*

Lo comprobé: `apps/web/spikes/vision/datasets/manifest.csv` tiene **solo la
cabecera**, cero filas. Para cerrar la meta SMART (accuracy ≥ 80 %, FPR < 20 %)
hace falta el dataset etiquetado y `results/evaluation.json`. No lo inventes —
grábalo con el equipo, igual que Pierre.

---

# Pierreluiggi · 1 tarea, y es el diferencial del proyecto

Lo tuyo fusionado: **PR #30** y **PR #32**. TA-012 (worker real de audio),
TA-013 (similitud), TA-016 (VAD en el navegador), HU-010 y HU-021 (QTI/SCORM) y
SP-010 están implementados.

### TA-062 — Grabaciones del equipo y medición de similitud y voz sintética

**Lo que ya tienes medido:** transcripción. `services/ai/results/evaluation-own.json`
con WER micro de **17.7 %** sobre 2 muestras propias (P01_01, P01_02), con hash
del manifiesto y factor de tiempo real. Eso está bien hecho y es citable.

**Lo que falta, y lo verifiqué:** en `services/ai/results/` **no hay ni una sola
medición de similitud ni de voz sintética**. Busqué esas palabras en todos los
resultados: cero.

Eso importa más que ninguna otra medición del proyecto, porque **es el
diferencial**. Todo lo demás que hacemos (foco, monitores, mirada) lo hace
cualquier sistema de proctoring. Lo que nos distingue es detectar la consulta a
una IA por voz, y la regla concreta es:

> Solo hay alerta si se cumplen **las dos** condiciones: lo que dijo se parece al
> enunciado **y** responde una segunda voz sintética.
>
> **Leer la pregunta en voz alta para concentrarse NO puede generar alerta.**

Esa segunda frase es lo que hay que **demostrar con números**, no afirmar.

**Lo que necesitas grabar** — y ya vi que el equipo empezó, hay audios
`Fabrizio_01` a `Fabrizio_07`. Organízalos en tres grupos:

| Grupo | Qué se graba | Qué debe dar |
|---|---|---|
| **Control legítimo** | Alguien lee la pregunta en voz alta, nada más | similitud alta, voz sintética baja → **sin alerta** |
| **Habla cualquiera** | Conversación normal, no sobre el examen | similitud baja → **sin alerta** |
| **La trampa** | Alguien lee la pregunta y un asistente de IA responde en voz alta | similitud alta **y** voz sintética alta → **alerta** |

El primer grupo es el más importante de todos. Es el que mide los **falsos
positivos**, y la meta es FPR < 20 %. Si acusamos a alguien por leer en voz alta,
el sistema no sirve.

**Entrega:** manifiesto con el mismo formato que ya usas (hash, procedencia,
consentimiento, condición) y un `results/` con similitud, voz sintética,
accuracy y FPR. Mantén el conjunto final separado del de calibrado, como ya
haces con `exploratory_not_final_test`.

Ya tienes montado todo lo que hace falta para medirlo: el worker, la similitud y
el clasificador. Esto es correr y anotar, no programar.

---

## Resumen en una línea cada uno

- **Rider:** medir lo que ya construiste (es lo primero), publicar el Release, y
  dos vistas que ya tienen todo lo que necesitaban del servidor.
- **Jesús:** la pantalla que pide la cámara al entrar. Backend y worker ya están;
  falta el cliente.
- **Pierreluiggi:** grabar los tres grupos y medir similitud y voz sintética. Es
  el diferencial del proyecto y es lo único que sigue sin números.

**El patrón de la semana:** a los tres les queda sobre todo **medir**, no
programar. Eso es exactamente lo que sostiene la meta SMART de accuracy ≥ 80 % y
FPR < 20 % por módulo, y es lo que el docente va a pedir ver.
