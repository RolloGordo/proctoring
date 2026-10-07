# Rider — app de escritorio e interfaz

**Tu área:** la app de escritorio (kiosco, protección, detección de entorno) y la
interfaz de la web.
**SPEC:** 006 (entorno) y 002/003 (pantallas).

Lee antes [`docs/guias/README.md`](README.md).

---

## Lo que ya tienes hecho

| Qué | Dónde |
|---|---|
| Ventana en kiosco con protección de contenido | `src/main/index.ts`, `src/main/protection.ts` |
| Foco de ventana (`focus_lost`) | `src/main/events.ts` |
| Monitores adicionales (`extra_display`) | `src/main/index.ts` |
| Procesos sospechosos (`suspicious_process`) | `src/main/processes.ts` |
| Envío a la API con reintentos y renovación de token | `src/main/sender.ts` |

Y lo que se añadió después sobre tu base: carga del examen desde la web
(`src/main/web.ts`), navegación atada al origen, y permisos de cámara
(`src/main/permisos.ts`).

---

## Tarea R1 — Evidencia visual de las alertas (5 h)

**Rama:** `feat/SPEC-006-capturas-evidencia`
**Archivos:** `src/main/capturas.ts` (nuevo), `src/main/index.ts`

**Esta es la más importante y la que más se nota.** Hoy el docente ve que hubo una
alerta, pero no *qué* pasó. El prototipo tiene una galería de capturas por
categoría: eso necesita que alguien tome la captura.

Cuando se detecta un evento de severidad **alta** (`suspicious_process`,
`extra_display`, `screen_share`), hay que:

1. Capturar la pantalla con `desktopCapturer`
2. Pedir una URL firmada: `POST /api/v1/evidence/upload-url` con
   `kind: "image"`, `extension: "jpg"`
3. Subirla **directo a Storage** con esa URL
4. Mandar el evento con `evidence_path` = la ruta devuelta

```ts
import { desktopCapturer, screen } from 'electron'

const { width, height } = screen.getPrimaryDisplay().workAreaSize
const fuentes = await desktopCapturer.getSources({
  types: ['screen'],
  thumbnailSize: { width: Math.round(width / 2), height: Math.round(height / 2) }
})
const jpeg = fuentes[0].thumbnail.toJPEG(70)
```

Tres reglas:

- **Solo cuando hay evento.** Nunca periódica. Capturar cada 30 segundos es
  grabar la pantalla de alguien, y rompe la promesa del consentimiento.
- **Un tope por examen** (unas 20 capturas) y **una cada pocos segundos como
  mucho**: si AnyDesk sigue abierto, no queremos 400 capturas iguales.
- **La captura nunca pasa por la API.** Va directo a Storage, como el audio.

Mira `src/main/sender.ts`: la cola y los reintentos ya están resueltos, conviene
reusar esa idea en vez de escribir otra.

**Terminado cuando:** abres AnyDesk durante un examen de prueba y, en la revisión
del caso, el docente ve la captura del momento.

---

## Tarea R2 — Detectar pantalla compartida (3 h)

**Rama:** `feat/SPEC-006-screen-share`
**Archivo:** `src/main/processes.ts`

El evento `screen_share` está en el contrato y **nadie lo emite todavía**. Hoy
`processes.ts` detecta que Zoom o Meet están *abiertos*, que no es lo mismo que
estar compartiendo pantalla.

Lo razonable sin permisos de sistema raros: en Windows, mirar si el proceso de
Zoom/Teams tiene una ventana de "compartiendo", o si está activo el proceso
auxiliar que esas aplicaciones levantan solo al compartir (por ejemplo
`CptHost.exe` en Zoom). **Investiga y documenta lo que encuentres**: si resulta
que no se puede distinguir de forma fiable, dilo en el README y lo dejamos como
`suspicious_process`. Es una respuesta válida y mejor que un detector que miente.

En `metadata`: `{ source, detected_by, process_name }`.

---

## Tarea R3 — Medir y documentar tus criterios (3 h)

**Rama:** `docs/SPEC-006-evidencia`

Tu README (`apps/desktop/README.md`) tiene 7 criterios de aceptación **sin
marcar**. Son tuyos y son medibles:

| Criterio | Cómo medirlo |
|---|---|
| Alt+Tab y volver → **un** `focus_lost` con duración ±200 ms | cronómetro contra el `duration_ms` del evento |
| Conectar un monitor → `extra_display` en **< 5 s** | hora de conexión vs. `started_at` |
| Abrir Zoom/AnyDesk → `suspicious_process` en **< 15 s** | igual |
| Capturar la ventana → **sale en negro** | captura de pantalla del intento |

Graba un vídeo corto con las cuatro. Es evidencia directa de la meta SMART
("alerta al docente en < 5 s") y hoy **no existe ninguna medición**.

> La ventana está protegida contra capturas, así que para grabar el resto del
> vídeo necesitas `PROCTORING_DISABLE_CONTENT_PROTECTION=1`. Para la prueba de
> la captura en negro, déjala **puesta**: eso es justamente lo que se demuestra.

El vídeo va al Notion de Héctor, no al repositorio. Marca los criterios en el
README y di con qué los mediste.

---

## Tarea R4 — Pantalla de resultados del docente (6 h)

**Rama:** `feat/SPEC-003-resultados`
**Archivos:** `apps/web/src/pages/Resultados.tsx` (nuevo), `apps/web/src/App.tsx`

El docente puede ver alertas en vivo y revisar un caso, pero **no puede ver las
notas de su examen**. En el prototipo es la pantalla "Resultados".

Lo que ya existe para construirla:

| Dato | De dónde |
|---|---|
| Lista de participantes con nota | `GET /api/v1/sessions/{id}/participants` (trae `score`, `student_name`, `submitted_at`) |
| Decisiones tomadas | `GET /api/v1/sessions/{id}/decisions` |
| Enlace a la revisión | `/sesiones/:id/estudiantes/:estudianteId` |

Una tabla con: estudiante, entregado, nota, estado de revisión (si hay decisión) y
un enlace a "Revisar". Más un resumen arriba: cuántos entregaron, nota media,
cuántos casos quedan por revisar.

Usa el sistema de diseño que ya está (`tarjeta`, `tabla`, `chip`, `severidad-*`) y
mira `apps/web/src/pages/Participantes.tsx` como referencia: es la pantalla más
parecida.

> Ojo con una cosa: la nota puede ser **parcial** si el examen tiene preguntas de
> desarrollo, que todavía las califica el docente a mano. El panel del estudiante
> ya lo muestra así ("5 de 10 · faltan desarrollos por calificar"); haz lo mismo
> aquí en vez de mostrar un número que parece definitivo.

---

## Tarea R5 — Instalador (4 h)

**Rama:** `chore/EN-004-instalador`
**Archivo:** `apps/desktop/electron-builder.yml`

```bash
npm run build:win --prefix apps/desktop
```

Comprueba que el `.exe` instala y arranca **en una máquina que no es la tuya**
(la de un compañero vale). Sin eso no sabemos si falta una dependencia del
sistema.

Después, publicarlo en GitHub Releases. Coordínalo con Héctor: toca el CI, que es
su carpeta.

---

## Orden recomendado

```
R3 (medir)      ──► hoy mismo, no depende de nada y es evidencia que falta
R1 (capturas)   ──► lo que más se nota en la revisión del docente
R2 (screen_share)
R4 (resultados) ──► trabajo de interfaz, sin Electron
R5 (instalador) ──► al final
```

**R3 primero**: son 3 horas, no depende de nadie, y cierra cuatro criterios de
aceptación que llevan abiertos desde la semana 5.
