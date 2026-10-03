# `apps/desktop` — App de escritorio del estudiante (Electron + TypeScript)

**Responsable:** Rodriguez Ruiz, Rider (Scrum Master)
**Backlog:** EN-002 / TA-00x (app de escritorio y detección de entorno)

Esta carpeta está preparada pero **vacía a propósito**: la implementa Rider. Lee
[`CLAUDE.md`](../../CLAUDE.md) §3 antes de empezar.

## Objetivo

Aplicación de escritorio que carga la **misma web** (`apps/web`) en la ruta del examen, dentro de
una ventana en modo kiosco, y que detecta desde el proceso `main` lo que el navegador no puede ver:
foco de ventana, monitores adicionales y procesos sospechosos.

El docente usa solo la web. El estudiante **necesita** esta app porque los permisos de sistema
(pantallas, lista de procesos, protección de contenido) no existen en un navegador.

## Estructura esperada

```
apps/desktop/
├── src/
│   ├── main/        # proceso principal: ventana, kiosco, protección, pantallas, procesos, protocolo
│   ├── preload/     # API mínima expuesta con contextBridge
│   └── renderer/    # carga apps/web; apenas un contenedor
├── electron.vite.config.ts
├── package.json
└── tsconfig.json
```

Andamiaje recomendado: [`electron-vite`](https://electron-vite.org/).

```bash
npm create @quick-start/electron@latest . -- --template vanilla-ts
```

## Pasos

### 1. Ventana en modo kiosco y protegida (`src/main/window.ts`)

```ts
const win = new BrowserWindow({
  kiosk: true,
  fullscreen: true,
  webPreferences: {
    contextIsolation: true,   // obligatorio
    sandbox: true,            // obligatorio
    nodeIntegration: false,   // obligatorio
    preload: path.join(__dirname, '../preload/index.js'),
  },
});
win.setContentProtection(true);   // la ventana no sale en capturas ni en screen share
win.setAlwaysOnTop(true, 'screen-saver');
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
const BLOCKLIST = ['zoom', 'anydesk', 'teamviewer', 'obs64', 'obs', 'discord'];
```

Busca también indicios de máquina virtual (`vmware`, `virtualbox`, `vboxservice`). En `metadata`
manda `{ process_name, pid }`. **No mates el proceso**: el sistema es auditor, no juez.

### 5. Enviar los eventos a la API

Todos los eventos usan el contrato de [`packages/contracts`](../../packages/contracts/) y van a:

```
POST http://localhost:8000/api/v1/events
Content-Type: application/json
```

Hay un ejemplo válido por tipo de evento en `packages/contracts/examples/`. La respuesta es
`201` con `{ "id": "...", "severity": "low|medium|high" }`.

Pon la URL en una variable de entorno (`VITE_API_URL`), no la escribas fija.

### 6. Preload: solo lo necesario

```ts
contextBridge.exposeInMainWorld('proctoring', {
  onFocusLost: (cb) => ipcRenderer.on('focus-lost', (_e, p) => cb(p)),
  getDisplayCount: () => ipcRenderer.invoke('displays:count'),
});
```

Nada de `ipcRenderer` crudo ni `require` en el renderer.

## Criterios de aceptación

- [ ] `npm run dev` abre la ventana en kiosco y a pantalla completa.
- [ ] Al hacer Alt+Tab y volver, se registra **un** `focus_lost` con `duration_ms` correcto (±200 ms).
- [ ] Conectar un segundo monitor genera `extra_display` en menos de 5 s.
- [ ] Abrir Zoom o AnyDesk genera `suspicious_process` en menos de 15 s.
- [ ] La ventana aparece en negro al intentar capturarla o compartir pantalla.
- [ ] Los eventos llegan a la API y responden `201` (comprobable en los logs de la API).
- [ ] `npm run lint` y `npm run build` pasan (el CI los va a correr).

## Evidencia para la semana

Video corto mostrando: Alt+Tab → evento en los logs de la API; conectar monitor → evento; abrir
Zoom → evento; intentar capturar pantalla → ventana en negro.
Guárdalo en `docs/evidencias/semana-05/rider/`.
