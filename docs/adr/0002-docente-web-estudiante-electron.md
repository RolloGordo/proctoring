# ADR-0002 — Docente en web, estudiante en aplicación de escritorio Electron

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-10-03 |
| **Decide** | Silva Vega, Héctor (Project Manager) |

## Contexto

El estudiante tiene que ser supervisado de verdad: hay que saber si conectó un segundo monitor,
si abrió AnyDesk o si se fue a otra ventana de Windows. Un navegador no puede ver nada de eso: no da
la lista de procesos, no enumera monitores de forma fiable y no puede impedir que el usuario comparta
su pantalla. El docente, en cambio, solo consulta y decide.

## Decisión

Dos clientes sobre **una sola aplicación web**:

- El **docente** abre la web en su navegador. No instala nada.
- El **estudiante** instala una app de **Electron + TypeScript** que carga esa misma web en la ruta
  del examen, dentro de una `BrowserWindow` con `kiosk: true` y `setContentProtection(true)`.

El proceso `main` de Electron aporta lo que el navegador no puede: `blur`/`focus` de la ventana,
`screen.getAllDisplays()`, y la lista de procesos cada 10 s. El `renderer` (la web) corre MediaPipe
y el VAD. La web accede al proceso `main` solo por las funciones que el `preload` expone con
`contextBridge`.

Seguridad obligatoria de Electron: `contextIsolation: true`, `sandbox: true`,
`nodeIntegration: false`, CSP restrictiva.

## Alternativas consideradas

- **Solo web, con la API de Screen Capture y permisos del navegador.** No detecta procesos ni
  monitores de forma fiable, y depende de permisos que el estudiante puede revocar.
- **Agente nativo por sistema operativo (C#/C++).** Más control, pero habría que mantener dos
  códigos y el equipo ya sabe TypeScript.
- **Extensión de navegador.** Se desactiva en dos clics y no ve fuera del navegador.

## Consecuencias

**A favor:** una sola interfaz que mantener; el docente no instala nada; conseguimos las señales de
entorno que son el núcleo del producto.

**En contra:** el estudiante tiene que instalar un ejecutable, con la fricción y la desconfianza que
eso trae; hay que firmar o al menos documentar el instalador; Electron pesa (~150 MB) y hay que
distribuirlo por GitHub Releases. Aceptamos la fricción porque sin ella el producto no cumple su
función.
