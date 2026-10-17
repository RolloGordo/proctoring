# `apps/web` — Web del docente y vista del examen (React + TypeScript + Vite)

**Responsables:** Rodriguez Ruiz, Rider (UI) · Limay Capristan, Jesús (spike de visión)
**Backlog:** EN-002 (UI) / EN-008 (visión)

Una sola aplicación web sirve a los dos usuarios:

- **El docente** la abre en su navegador: crear exámenes, alertas en vivo, revisión de evidencia y
  decisión justificada.
- **El estudiante** ve la misma web, pero cargada **dentro de la app de escritorio**
  ([`apps/desktop`](../desktop/)) en la ruta del examen. La web no sabe que está en Electron: usa
  solo lo que el `preload` expone por `contextBridge`.

## Arrancar

```bash
cd apps/web && npm install && npm run dev
```

Queda en <http://localhost:5173>. Necesita la API levantada:

```bash
docker compose up -d
```

Copia `.env.example` a `.env.local` y ajusta lo que necesites. Sin variables de Supabase, la web
funciona **sin login**, igual que la API con `AUTH_ENABLED=false`: es el modo de desarrollo
mientras el equipo termina sus módulos.

| Variable | Para qué |
|---|---|
| `VITE_API_URL` | la API. Por defecto `http://localhost:8000` |
| `VITE_SUPABASE_URL` | proyecto Supabase. **Si falta, no hay login ni alertas en vivo** |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | clave publicable. Es segura en el navegador porque RLS protege los datos |

La `SUPABASE_SERVICE_ROLE_KEY` **nunca** va aquí: Vite expone al navegador todo lo que empiece por
`VITE_`.

## Pantallas

| Ruta | Qué hace | Estado |
|---|---|---|
| `/login` | acceso con Supabase Auth | hecho |
| `/sesiones` | lista de exámenes del docente | hecho |
| `/sesiones/nueva` | crear examen, elegir nivel de supervisión | hecho |
| `/sesiones/:id` | **alertas en vivo** y línea de tiempo de señales | hecho |
| `/sesiones/:id/estudiantes/:id` | revisión del caso y decisión justificada | pendiente |
| `/examen/:id` | rendición del examen (vista del estudiante) | pendiente |

## Alertas en vivo

La API inserta una fila en `alerts` y la pantalla la recibe por **Supabase Realtime**, sin
preguntar nada. Es lo que sostiene la meta de avisar en menos de 5 s (ADR-0007).

Realtime solo trae lo que ocurre **a partir de** la suscripción, así que la pantalla primero carga
lo ya ocurrido con `GET /api/v1/sessions/{id}/alerts` y después escucha. Las alertas que llegan por
los dos caminos se deduplican por id.

Las señales `low` **no** generan alerta: quedan registradas y se ven en la línea de tiempo, pero no
interrumpen. Un docente que recibe un aviso por cada parpadeo deja de mirarlos.

## Estilo

El sistema de diseño está en [`src/styles/tokens.css`](src/styles/tokens.css) y
[`base.css`](src/styles/base.css), y sale del tema **Agency** de Start Bootstrap, que es la
referencia que pidió el equipo:

- **Montserrat 700 en mayúsculas** para títulos, navegación, botones y encabezados de tabla.
- **Roboto Slab** para el texto, y en cursiva para los subtítulos.
- Amarillo `#ffc800` como acento, usado **poco**: botón principal, pestaña activa, código de
  acceso y la marca de la alerta más reciente. Un acento que sale en todas partes deja de serlo.
- Oscuro `#212529` para la cabecera y la pantalla de acceso.

Esto no es una landing page: es una herramienta que el docente mira durante una hora seguida
mientras vigila un examen. Por eso se conservan la tipografía y la paleta del tema, pero con
escalas más bajas, esquinas poco redondeadas, sin degradados y sin animaciones decorativas. La
única animación es el punto que late cuando hay conexión en vivo, porque ahí sí comunica algo.

Si añades pantallas, usa las clases que ya existen (`tarjeta`, `boton`, `campo`, `tabla`,
`severidad-*`) antes de escribir CSS nuevo.

## Calidad

```bash
npm run lint && npm test && npm run build
```

Es lo mismo que corre el CI. Hay pruebas del cliente de la API: que conserve el código de estado
para distinguir 401 de 403, que traduzca el 422 de Pydantic a algo legible, y que mande el token
solo cuando existe.

## Reglas

- **Interfaz en español**, **código en inglés** (componentes, props, variables). Las clases CSS y
  los nombres de pantalla van en español porque describen la interfaz.
- Los textos describen lo observado, nunca lo interpretan: «salió de la ventana», no «hizo
  trampa». El sistema es un auditor, no un juez.
- No subas video. Las capturas van **directo a Storage** con la URL firmada que entrega
  `POST /api/v1/evidence/upload-url`; al evento solo le pones el `evidence_path`.

## Subcarpetas

- [`spikes/vision/`](spikes/vision/) — spike de visión por computadora (Jesús), con su propio
  README.
