# Rider · lo que queda de la semana 6

**Cierre: domingo 11/10.** Son 8 puntos en seis tareas, y **ya puedes empezar
las seis**: las dos que esperaban algo mío ya lo tienen (sección 4).

Antes de nada:

```bash
git checkout develop && git pull
```

Tu trabajo de la semana ya está fusionado (PR #28). Lo que sigue parte de ahí.

---

## Empieza por aquí: las mediciones (DO-004 + TA-015, 2 pt)

**Es lo más valioso que puedes hacer esta semana y no depende de nadie.** Son los
cuatro criterios de aceptación de SPEC-006 que siguen sin marcar, y sin ellos el
módulo de escritorio no está cerrado aunque el código funcione.

Las pruebas automatizadas **no valen** como evidencia de esto. Hay que medir en
Windows, con cronómetro, y grabarlo.

### Montaje

```bash
docker compose up -d api
npm run dev --prefix apps/web
npm run dev --prefix apps/desktop
```

Para grabar las tres primeras demostraciones necesitas que la ventana salga en
el vídeo, así que arranca la app con la protección desactivada:

```powershell
$env:PROCTORING_DISABLE_CONTENT_PROTECTION=1; npm run dev --prefix apps/desktop
```

**Quita esa variable antes de la cuarta prueba**, que es justamente la de la
pantalla en negro.

### Las cuatro medidas

| # | Qué | Cómo medirlo | Meta |
|---|---|---|---|
| 1 | Pérdida de foco | Alt+Tab, cronómetro en marcha; vuelve a la ventana y compara con el `duration_ms` del evento | Un solo evento, error ±200 ms |
| 2 | Monitor adicional | Conecta el segundo monitor y anota la hora; resta del `started_at` del `extra_display` | < 5 s |
| 3 | Proceso sospechoso | Abre Zoom o AnyDesk y anota la hora; resta del `started_at` del `suspicious_process` | < 15 s |
| 4 | Protección de captura | Sin la variable de arriba, haz una captura con la tecla ImprPant o con Recortes | La ventana sale en negro |

Repite cada medida **tres veces** y anota las tres. Una sola medición no dice
nada: si Alt+Tab da 180 ms, 190 ms y 950 ms, el problema es el 950.

### Qué entregar

1. **Marca los criterios** en `apps/desktop/README.md`, líneas 189–194, cambiando
   `- [ ]` por `- [x]` solo en los que de verdad midas.
2. **Rellena la tabla** de la sección «SPEC-006: estado de mediciones» con los
   números observados, no con la meta. Si algo no cumple, se anota igual: un
   número que no cumple es un resultado, no un fracaso.
3. **El vídeo va al Notion de Héctor**, no al repositorio. Uno solo de 2–3 minutos
   con las cuatro demostraciones seguidas sirve.

Si alguna medida no cumple la meta, **no la ajustes para que cuadre**: anótala y
dilo. Eso es un hallazgo y vale más que un número bonito.

---

## 2. El instalador en otro equipo y su publicación (EN-011 + TA-060, 2 pt)

El instalador ya lo generaste: `apps/desktop/dist/desktop-1.0.0-setup.exe`,
106,4 MB, Electron 44.5.1. Falta lo que no se puede comprobar en tu máquina.

**Instalarlo en otra computadora.** Una donde no esté Node ni el repositorio, que
es la situación real de un estudiante. Comprueba:

- que instala sin pedir nada raro,
- que arranca y abre la ventana en kiosco,
- que llega a la pantalla del código de acceso,
- y que **cierra bien** (que no quede el proceso colgado).

Anota la versión de Windows de esa máquina.

**Publicar el Release:**

```bash
gh release create v1.0.0 apps/desktop/dist/desktop-1.0.0-setup.exe \
  --title "Proctoring Desktop 1.0.0" \
  --notes "Primera versión instalable. Kiosco, protección de contenido, detección de foco, monitores y procesos."
```

Si `gh` te pide permisos, dile a Héctor: puede que haga falta ajustar el token.

---

## 3. El protocolo `proctoring://` (EN-008, 1 pt)

Lo comprobé en el repositorio: **no está hecho**. En `apps/desktop/src/main/index.ts`
solo está `electronApp.setAppUserModelId`, que es otra cosa.

Lo que falta es que el enlace que le pase el docente abra tu app directamente en
la sala del examen correcto.

**Archivo:** `apps/desktop/src/main/index.ts`

Tres piezas:

1. **Registrar el protocolo** al arrancar, con `app.setAsDefaultProtocolClient('proctoring')`.
   En desarrollo hay que pasarle también la ruta del ejecutable y los argumentos,
   porque si no Windows registra `electron.exe` y no tu app.
2. **Una sola instancia**: `app.requestSingleInstanceLock()`. Sin esto, abrir el
   enlace con la app ya abierta lanza una segunda ventana en kiosco y el
   estudiante se queda con dos.
3. **Leer la URL**. En Windows llega como argumento en `process.argv`, y con la
   app ya abierta llega por el evento `second-instance`. Hay que cubrir los dos
   casos.

De `proctoring://examen/<session_id>` sacas el id y navegas a la sala. **Valida
que sea un UUID** antes de usarlo: es una URL que puede escribir cualquiera, y
concatenarla sin mirar es como se acaba navegando a donde no toca.

**Criterio:** el enlace abre la app en el examen correcto, esté la app cerrada o
ya abierta.

---

## 4. Lo que esperaba a Héctor: ya está

Las dos estaban bloqueadas por mí. **Ya no.** Están en `develop`, así que el
`git pull` del principio te las trae.

### HU-023 — Ver la evidencia en la revisión del caso (2 pt)

Es el criterio que dejaste abierto en tu R1: las capturas se suben y quedan
enlazadas al evento, pero el docente no puede verlas.

**Lo que te faltaba, y ya tienes:**

1. `POST /api/v1/sessions/{session_id}/students/{student_id}/evidence-url`
   con `{ "path": "...", "kind": "image" | "audio" | "reference_face" }`
   devuelve `{ "url": "...", "expires_in_seconds": 900 }`. El `path` es el
   `evidence_path` que ya viene en cada evento, tal cual. En la web es
   `api.evidenceUrl(...)`.
2. `GET /sessions/{id}/students/{id}/case` ahora trae `audio_analyses`, con
   `transcript`, `similarity`, `synthetic_voice_score`, `matched_question_id` y
   un `alerted` que dice si ese fragmento generó alerta.

   La **ruta del audio** no está en el análisis: está en el evento, que se
   encuentra por `event_id`. El análisis es lo que se midió; el fragmento es
   evidencia del evento. Así que para el reproductor: `analisis.event_id` →
   el evento → su `evidence_path` → `api.evidenceUrl(..., 'audio')`.

El enlace **caduca en 15 minutos**. No lo guardes en estado al cargar la página
y lo uses media hora después: pídelo cuando el docente vaya a mirar la captura.

**Lo tuyo:** `apps/web/src/pages/RevisionCaso.tsx`. Mostrar la captura de cada
evento que la tenga, agrupadas por categoría, y un reproductor para los
fragmentos marcados como posible consulta a IA.

### HU-015 — Cuadrícula de cámaras en vivo (2 pt)

Te dije que el problema de diseño era mío. Ya está resuelto, y **no hace falta
nada más del servidor**: el componente de una cámara existe y funciona.

**El componente:** `apps/web/src/components/CamaraEnVivo.tsx`.

```tsx
<CamaraEnVivo sessionId={id} studentId={p.student_id} teacherId={userId} nombre={p.student_name} />
```

Lo tuyo es componerlo en una cuadrícula en la pantalla en vivo
(`apps/web/src/pages/SesionEnVivo.tsx`), con los estudiantes que están rindiendo
(`can_take_exam && !submitted_at` de `api.listParticipants`). Hay un ejemplo de
una sola cámara ya funcionando en `apps/web/src/pages/Participantes.tsx`.

**Dos cosas que importan y no se ven en el tipo:**

1. **Montar el componente es lo que hace que ese estudiante empiece a enviar.**
   El estudiante solo captura mientras el docente está en su canal. Así que una
   cuadrícula de 30 cámaras enciende 30 envíos. Si la clase es grande, pagina o
   monta solo las visibles; no las montes todas «por si acaso».
2. **No se graba, y el estudiante ve que lo estás mirando.** Si en la pantalla
   pones algo tipo «grabando», estarías diciendo lo contrario de lo que el
   sistema hace. El texto que ya está en `Participantes.tsx` sirve de ejemplo.

El módulo tiene que estar activo en el examen (`live_monitoring` en
`session.modules`, que viene con el preset `strict`). Si no está, no ofrezcas la
cámara: el estudiante no aceptó eso.

El contrato completo —nombre del canal, forma del mensaje, por qué un canal por
estudiante— está en `apps/web/src/supervision/README.md`, sección «El monitoreo
en vivo no es un detector».

## Antes de subir

```bash
cd apps/desktop && npm run lint && npm run typecheck && npm test && npm run build
```

```bash
cd apps/web && npm run lint && npm test && npm run build
```

Rama `feat/SPEC-006-mediciones-instalador`, commits en inglés con el código del
backlog, PR hacia `develop`. Y **mira el diff antes de añadir**: tu último paquete
traía un `package.json` que habría borrado las dependencias de audio de
Pierreluiggi. No fue culpa tuya —venías de una base anterior— pero por eso el
`git pull` del principio importa.

---

## Y una cosa que conviene que sepas

Dijiste que sientes que has trabajado poco. Con el backlog corregido llevas **13
puntos cerrados en la semana 6**, por encima del objetivo y solo por detrás de
Héctor. Lo que pasaba es que la mitad de tu trabajo no figuraba en tu ficha: la
pantalla de resultados estaba a nombre de Héctor y el instalador era de la semana
7. Ya está puesto a tu nombre.

Lo que de verdad falta no es que hagas más cosas: es que **midas las que ya
hiciste**. Por eso las mediciones van las primeras.
