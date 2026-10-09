# `apps/desktop` — App de escritorio del estudiante (Electron + TypeScript)

**Responsable:** Rodriguez Ruiz, Rider (Scrum Master)
**Backlog:** EN-002 / TA-00x (app de escritorio y detección de entorno)

**Ya implementada** por Rider: ventana en kiosco, protección de contenido, foco, monitores,
procesos y envío a la API. Lee [`CLAUDE.md`](../../CLAUDE.md) §3 antes de tocarla.

## Cómo correrla

### Si sale `Error: Electron uninstall`

`npm install` descarga aparte un binario de ~100 MB y esa descarga puede fallar.
No es un fallo del código:

```powershell
node apps/desktop/node_modules/electron/install.js
```

Queda bien cuando existe `node_modules/electron/dist/electron.exe`.

### Dos servidores

| Puerto | Quién lo levanta | Qué sirve                                       |
| ------ | ---------------- | ----------------------------------------------- |
| 5173   | `apps/web`       | **El examen**, que es lo que carga esta ventana |
| 5180   | esta app         | El panel local de eventos (diagnóstico)         |

La app **no reimplementa el examen**: carga la misma web de `apps/web` en la ruta del examen,
dentro de la ventana protegida. Así que primero levanta la web y la API:

```bash
docker compose up -d api          # API en localhost:8000
npm run dev --prefix apps/web     # web en localhost:5173
```

Y después la app:

```bash
npm run dev --prefix apps/desktop
```

**No hay que configurar quién rinde ni en qué examen.** El estudiante inicia sesión en la web que
carga la ventana, escribe su código de acceso y el examen sale de ahí:

- **Quién:** al iniciar sesión, la web entrega el token al proceso principal (`window.api.setAuthSession`,
  que el preload ya exponía). De él sale el `student_id`. No se verifica la firma aquí: la API sí lo
  hace y rechaza con 403 cualquier evento cuyo `student_id` no coincida con el del token.
- **En qué examen:** de la URL. La supervisión empieza al llegar a `/examen/<id>/rendir`, **no antes**:
  el consentimiento se da en `/sala` y no se manda nada hasta que se acepta.
- **Al empezar**, la app vuelve a revisar monitores y procesos como si fuera el inicio del examen. Sin
  esto, un AnyDesk ya abierto se habría reportado antes de que existiera el examen, se habría
  descartado, y no volvería a avisar.

| Variable                                | Para qué                                                                         | Por defecto                           |
| --------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------- |
| `PROCTORING_PANEL`                      | `1` abre el panel local de eventos en vez del examen (diagnóstico).              | apagado                               |
| `PROCTORING_SESSION_ID`                 | Abre directo la sala de ese examen. La supervisión sigue empezando en `/rendir`. | pantalla del código                   |
| `PROCTORING_STUDENT_ID`                 | Respaldo para el panel local y para desarrollar **sin** login.                   | UUID nulo                             |
| `PROCTORING_WEB_URL`                    | Dónde vive la web del examen. En producción, la URL del despliegue.              | `http://localhost:5173`               |
| `PROCTORING_API_URL`                    | A dónde van los eventos.                                                         | `http://localhost:8000/api/v1/events` |
| `PROCTORING_KIOSK`                      | `1` fuerza el modo kiosco en desarrollo.                                         | apagado en dev                        |
| `PROCTORING_DISABLE_CONTENT_PROTECTION` | `1` deja que la ventana salga en capturas, para grabar evidencia.                | apagado                               |

> No definas `SUPABASE_URL` ni `SUPABASE_PUBLISHABLE_KEY` en el entorno de la app. El proceso principal
> sabe renovar el token por su cuenta tras un 401, pero la web ya le entrega cada renovación. Si los dos
> rotaran el mismo token de refresco, Supabase podría invalidar la sesión.

El **panel local de eventos** (`src/renderer/`) no es el examen: es la herramienta de diagnóstico
del proceso principal. Sirve para ver qué está detectando sin montar un examen entero.

La ventana está atada a su propio origen: si el examen intentara navegar a otro sitio, la
navegación se cancela. El preload expone `window.api` y ese sitio la heredaría.

## Objetivo

Aplicación de escritorio que carga la **misma web** (`apps/web`) en la ruta del examen, dentro de
una ventana en modo kiosco, y que detecta desde el proceso `main` lo que el navegador no puede ver:
foco de ventana, monitores adicionales y procesos sospechosos.

El docente usa solo la web. El estudiante **necesita** esta app porque los permisos de sistema
(pantallas, lista de procesos, protección de contenido) no existen en un navegador.

## Estructura

```
apps/desktop/
├── src/
│   ├── main/        # index, context, events, processes, protection, sender, web
│   ├── preload/     # API mínima expuesta con contextBridge
│   └── renderer/    # panel local de eventos (diagnóstico)
├── electron.vite.config.ts
├── package.json
└── tsconfig.json
```

Construida con [`electron-vite`](https://electron-vite.org/).

## Lo que pedía el enunciado (referencia)

### 1. Ventana en modo kiosco y protegida (`src/main/index.ts`)

```ts
const win = new BrowserWindow({
  kiosk: true,
  fullscreen: true,
  webPreferences: {
    contextIsolation: true, // obligatorio
    sandbox: true, // obligatorio
    nodeIntegration: false, // obligatorio
    preload: path.join(__dirname, '../preload/index.js')
  }
})
win.setContentProtection(true) // la ventana no sale en capturas ni en screen share
win.setAlwaysOnTop(true, 'screen-saver')
```

Además: CSP restrictiva, bloquear `Ctrl+C` / `Ctrl+V` / `Ctrl+Shift+I` / `F12` con
`globalShortcut` mientras el examen esté activo, y `win.on('close')` que pida confirmación.

### 2. Foco de ventana — evento `focus_lost`

Escucha `blur` y `focus` de la `BrowserWindow`. Mide la **duración** entre ambos y emite un solo
evento al recuperar el foco, con `duration_ms`. No emitas uno por cada `blur` suelto.

> Detalle que el docente pidió explícitamente: hay que detectar salida de pestaña **y** salida de
> la aplicación hacia otra ventana de Windows. `blur` cubre el segundo caso; para el primero el
> renderer escucha `visibilitychange`.

### 3. Monitores adicionales — evento `extra_display`

```ts
import { screen } from 'electron';
screen.getAllDisplays().length;        // al arrancar: si > 1, emite el evento
screen.on('display-added', ...);       // y durante el examen
screen.on('display-removed', ...);
```

En `metadata` manda `{ display_count, displays: [{ id, bounds, scale_factor }] }`.

### 4. Procesos sospechosos — evento `suspicious_process`

Con [`ps-list`](https://www.npmjs.com/package/ps-list), cada **10 s**. Lista inicial:

```ts
const BLOCKLIST = ['zoom', 'anydesk', 'teamviewer', 'obs64', 'obs', 'discord']
```

Busca también indicios de máquina virtual (`vmware`, `virtualbox`, `vboxservice`). En `metadata`
manda `{ process_name, pid }`. **No mates el proceso**: el sistema es auditor, no juez.

### 5. Enviar los eventos a la API

Todos los eventos usan el contrato de [`packages/contracts`](../../packages/contracts/) y van a:

```
POST http://localhost:8000/api/v1/events
Content-Type: application/json
Authorization: Bearer <access_token de Supabase Auth>
```

**Sobre el token:** la API comprueba que el `student_id` del cuerpo sea el mismo del token, así que
no puedes reportar eventos a nombre de otro. Si no mandas token recibes `401`; si mandas el de otro
estudiante, `403`.

Mientras no tengas la pantalla de login, arranca la API con `AUTH_ENABLED=false` en tu `.env` (ya
viene así en `.env.example`) y los eventos entran sin cabecera. En cuanto el login exista, pon
`AUTH_ENABLED=true` y empieza a mandar el token.

Hay un ejemplo válido por tipo de evento en `packages/contracts/examples/`. La respuesta es
`201` con `{ "id": "...", "severity": "low|medium|high" }`.

Pon el endpoint en la variable de entorno `PROCTORING_API_URL`, no lo escribas fijo. El valor por
defecto es `http://localhost:8000/api/v1/events`.

### 6. Preload: solo lo necesario

```ts
contextBridge.exposeInMainWorld('proctoring', {
  onFocusLost: (cb) => ipcRenderer.on('focus-lost', (_e, p) => cb(p)),
  getDisplayCount: () => ipcRenderer.invoke('displays:count')
})
```

Nada de `ipcRenderer` crudo ni `require` en el renderer.

## Criterios de aceptación

- [ ] `npm run dev` abre la ventana en kiosco y a pantalla completa. Pendiente de registrar una prueba manual.
- [ ] Alt+Tab genera un solo `focus_lost`; comparar `duration_ms` con cronómetro y registrar el error (meta: ±200 ms).
- [ ] Conectar un segundo monitor genera `extra_display` en menos de 5 s. Registrar el tiempo desde la conexión hasta `started_at`.
- [ ] Abrir Zoom o AnyDesk genera `suspicious_process` en menos de 15 s. Registrar el tiempo observado.
- [ ] Una captura externa con protección habilitada muestra la ventana en negro.
- [ ] Los eventos llegan a la API y responden `201`; guardar los logs de la prueba con API activa.
- [x] `npm run test`, `npm run lint` y `npm run build` pasan en el entorno de desarrollo.

## Evidencia para la semana

Video corto mostrando: Alt+Tab → evento en los logs de la API; conectar monitor → evento; abrir
Zoom → evento; intentar capturar pantalla → ventana en negro.
Guárdalo en `docs/evidencias/semana-05/rider/`.

## SPEC-006: estado de mediciones (R3)

Las pruebas automatizadas verifican funciones y el formato de eventos, pero no sustituyen las
mediciones en Windows. Las filas sin marcar requieren ejecutar la app y adjuntar el video al Notion
del equipo. No se anotan tiempos hasta que se midan físicamente.

| Medición              | Estado                                  | Cómo registrar el resultado                                                                                               |
| --------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Pérdida de foco       | Pendiente en Windows                    | Cronómetro al alternar con Alt+Tab; comparar con `duration_ms`, contar eventos y anotar el error en ms.                   |
| Monitor adicional     | Pendiente en equipo con segundo monitor | Anotar hora de conexión y `started_at`; calcular delta y verificar `< 5 s`.                                               |
| Proceso sospechoso    | Pendiente en Windows con Zoom o AnyDesk | Anotar hora de apertura y hora del evento; verificar `< 15 s`.                                                            |
| Protección de captura | Pendiente en Windows                    | Con `PROCTORING_DISABLE_CONTENT_PROTECTION` sin definir, guardar una captura externa en la que la ventana aparezca negra. |
| Video de evidencia    | Pendiente                               | Repetir las cuatro pruebas y enlazar el video del Notion del equipo.                                                      |

Para grabar las otras tres demostraciones, define `PROCTORING_DISABLE_CONTENT_PROTECTION=1`; quita
esa variable antes de comprobar la captura negra. No presentar las pruebas unitarias como evidencia
de las pruebas físicas.

## SPEC-006: capturas y pantalla compartida (R1/R2)

Las capturas se intentan solo para `suspicious_process`, `extra_display` y `screen_share`; no hay
capturas periódicas. Se limita a 20 por sesión y a una captura cada 5 segundos. Los fallos de red o
servidor al solicitar/subir una captura se reintentan hasta tres veces; si no se recuperan, el error
se registra y el evento se envía sin `evidence_path`.

La tarea original agrupa `extra_display` entre las señales altas, pero la API actualmente le asigna
severidad `medium`. Se conserva la captura para ese evento porque el pedido la nombra explícitamente;
no se modifica el nivel de riesgo.

`screen_share` no se infiere solo porque Zoom o Teams estén abiertos: `ps-list` expone nombres y PID,
no el estado de compartir pantalla ni un estado fiable de sus ventanas. `CptHost.exe` también se
trata como indicio de una aplicación auxiliar, no como confirmación de una transmisión. Zoom, Teams
y `CptHost` quedan reportados como `suspicious_process`; no se emite `screen_share` hasta contar con
una señal verificable para evitar alertas falsas. La API todavía no ofrece una URL firmada de
lectura; por eso la captura se almacena y queda vinculada al evento, pero aún no se puede mostrar en
la revisión del caso. Para cerrar ese criterio hace falta coordinar el endpoint con el responsable
de la API.

## SPEC-003: resultados (R4)

La web del docente ofrece `/sesiones/:id/resultados` desde la pantalla en vivo. Muestra entregas,
nota media de las notas automáticas disponibles, casos enviados y pendientes de decisión, y acceso
a la revisión individual. Si hay preguntas de desarrollo, las notas entregadas se etiquetan como
parciales hasta su revisión manual.

## Instalador (R5)

El instalador se generó correctamente con `npm run build:win --prefix apps/desktop` en
`dist/desktop-1.0.0-setup.exe` (106.4 MB, Electron 44.5.1). Confirmar que instala y arranca en otro
equipo sigue siendo una prueba manual; la publicación en GitHub Releases requiere coordinación con
quien mantiene el CI.

## Subir capturas y audio

El archivo **no se manda a la API**. Tres pasos:

```
1. POST /api/v1/evidence/upload-url
   { "session_id": "...", "student_id": "...", "kind": "image", "extension": "jpg" }
   -> 201 { "path": "...", "url": "...", "token": "...", "expires_in_seconds": 7200 }

2. subir el archivo directo a esa "url"

3. POST /api/v1/events con "evidence_path": el "path" del paso 1
```

`kind` es `image`, `audio` o `reference_face`. Las extensiones aceptadas están limitadas por el
bucket: imágenes `jpg`/`jpeg`/`png`/`webp`, audio `webm`/`wav`/`ogg`/`mp3`. Cualquier otra devuelve
`400`.

Ya está implementado y probado en la API: con `docker compose up` puedes usarlo hoy.
