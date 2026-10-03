# `apps/web` — Web del docente y vista del examen (React + TypeScript + Vite)

**Responsables:** Rodriguez Ruiz, Rider (UI) · Limay Capristan, Jesús (spike de visión)
**Backlog:** EN-002 (UI) / EN-008 (visión)

Una sola aplicación web sirve a los dos usuarios:

- **El docente** la abre en su navegador: crear sesiones, elegir módulos de detección, sala de
  espera, alertas en vivo, resultados, revisión de caso y decisión justificada.
- **El estudiante** ve la misma web, pero cargada **dentro de la app de escritorio**
  ([`apps/desktop`](../desktop/)) en la ruta del examen. La web no sabe que está en Electron: usa
  solo las funciones que el `preload` expone por `contextBridge`.

## Pantallas del docente

| Ruta | Qué hace |
|---|---|
| `/login` | Supabase Auth; el rol sale de `profiles.role` |
| `/sessions` | lista y creación de sesiones de examen |
| `/sessions/:id/setup` | elegir qué módulos de detección se activan (`session_modules`) |
| `/sessions/:id/lobby` | sala de espera: quién llegó, estado de verificación facial |
| `/sessions/:id/live` | **alertas en vivo** por Supabase Realtime |
| `/sessions/:id/results` | resultados y riesgo desglosado por señal |
| `/sessions/:id/students/:studentId` | revisión del caso con evidencia, y **decisión justificada** |

En la pantalla de decisión la justificación es **obligatoria** (la columna es `NOT NULL` en la base
de datos). El sistema es un auditor: muestra las señales y la evidencia, y el docente decide.
Nunca muestres un veredicto automático.

## Pantallas del estudiante

`/exam/:sessionId` — consentimiento, verificación de identidad por rostro, el examen pregunta por
pregunta, y de fondo MediaPipe (visión) y Silero VAD (habla).

## Montaje

```bash
cd apps/web
npm create vite@latest . -- --template react-ts
npm install @supabase/supabase-js
npm run dev
```

## Reglas

- **Interfaz en español**, **código en inglés** (componentes, props, variables).
- TypeScript estricto, ESLint + Prettier. El CI corre `npm run lint` y `npm run build`.
- La URL de la API en `VITE_API_URL`, nunca escrita fija.
- Las claves de Supabase que usa la web son la **anon key** y nada más. La
  `SUPABASE_SERVICE_ROLE_KEY` vive solo en el servidor.
- No subas video. Las capturas van **directo a Storage** con la URL firmada que entrega
  `POST /api/v1/evidence/upload-url`; al evento solo le pones el `evidence_path`.

## Subcarpetas

- [`spikes/vision/`](spikes/vision/) — spike de visión por computadora (Jesús). Tiene su propio
  README con los umbrales y criterios de aceptación.
