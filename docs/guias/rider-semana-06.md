# Rider · lo que te queda de la semana 6

Estado comprobado contra `develop` el **10/10**. Si algo aquí no coincide con lo
que te dijo otra herramienta, esto es lo verificado en el repositorio.

## Antes de nada

```bash
git checkout develop && git pull
```

```bash
docker compose up -d --build api
```

El segundo **no es opcional**. El contenedor de la API no recarga solo: si no lo
reconstruyes, sigue sirviendo el código viejo y vas a ver errores que parecen
del código que acabas de bajar (`Extra inputs are not permitted` en campos que
sí existen). Repítelo cada vez que alguien toque `services/api`.

## Ya no estás bloqueado por nadie

Dijiste que las tareas están vinculadas entre sí y que no se puede avanzar hasta
que otro termine. **Era cierto hasta anoche.** Ya no:

| Tu tarea | Esperaba | Estado |
|---|---|---|
| HU-023 | La URL firmada de lectura (Héctor) | ✅ **está en `develop`** |
| HU-015 | El canal de monitoreo (Héctor) | ✅ **está en `develop`** |

Las otras dos nunca dependieron de nadie. Puedes empezar las cuatro hoy.

## Lo tuyo que ya está dentro

HU-005 (login en la app), TA-011 (captura de evidencia), HU-008 (resultados),
TA-059 (clasificación de procesos) y EN-008 (`proctoring://`). Fusionados en los
PR **#28** y **#35**.

> Una corrección pequeña para tu ficha: en HU-015 pusiste «hay cámara
> individual». Ese componente (`CamaraEnVivo.tsx`) es de Héctor, es parte de
> HU-022. **Lo tuyo es la cuadrícula.** Mejor que tu evidencia lo diga así:
> reclamar algo que el commit atribuye a otro queda peor que el trabajo que sí
> hiciste, que es bastante.

---

## 1. Las mediciones · DO-004 + TA-015 — **empieza por aquí**

**Lo verifiqué:** en `apps/desktop/README.md` los cinco criterios de aceptación
siguen con `- [ ]`, y la tabla de la sección «SPEC-006: estado de mediciones»
dice *Pendiente* en las cinco filas.

Es lo más valioso que puedes hacer esta semana y **nadie más puede hacerlo**:
necesita Windows, cronómetro, un segundo monitor y Zoom o AnyDesk. Las pruebas
automatizadas no sustituyen esto: verifican funciones, no tiempos reales.

### Montaje

```bash
docker compose up -d api
npm run dev --prefix apps/web
```

Para que la ventana salga en el vídeo de las tres primeras pruebas, arranca con
la protección desactivada:

```powershell
$env:PROCTORING_DISABLE_CONTENT_PROTECTION=1; npm run dev --prefix apps/desktop
```

**Quita esa variable antes de la cuarta prueba**, que es justamente la de la
pantalla en negro.

### Las cuatro medidas

| # | Qué | Cómo medirlo | Meta |
|---|---|---|---|
| 1 | Pérdida de foco | Alt+Tab, cronómetro en marcha; vuelve y compara con el `duration_ms` del evento | Un solo evento, error ±200 ms |
| 2 | Monitor adicional | Conecta el segundo monitor y anota la hora; resta del `started_at` del `extra_display` | < 5 s |
| 3 | Proceso sospechoso | Abre Zoom o AnyDesk y anota la hora; resta del `started_at` del `suspicious_process` | < 15 s |
| 4 | Protección de captura | Sin la variable de arriba, captura con ImprPant o con Recortes | La ventana sale en negro |

**Repite cada una tres veces** y anota las tres. Una sola medición no dice nada:
si Alt+Tab da 180 ms, 190 ms y 950 ms, el resultado interesante es el 950.

### Qué entregar

1. Marca los `- [x]` en `apps/desktop/README.md` **solo** en lo que de verdad midas.
2. Rellena la tabla de la sección R3 con los números **observados**, no con la meta.
3. El vídeo va al Notion de Héctor, no al repositorio. Uno de 2–3 minutos con las
   cuatro demostraciones seguidas sirve.

Si algo no cumple la meta, **no lo ajustes para que cuadre**: anótalo y dilo. Un
número que no cumple es un hallazgo, y vale más en la defensa que un número
bonito sin respaldo.

---

## 2. El instalador en otro equipo y el Release · EN-011 + TA-060

**Lo verifiqué:** `gh release list` está **vacío**. El instalador existe en tu
máquina (`apps/desktop/dist/desktop-1.0.0-setup.exe`) y no está publicado.

Instálalo en una computadora **sin Node y sin el repositorio** — que es la
situación real de un estudiante. Comprueba que:

- instala sin pedir nada raro,
- arranca y abre la ventana en kiosco,
- llega a la pantalla del código de acceso,
- y **cierra bien** (que no quede el proceso colgado).

Anota la versión de Windows de esa máquina.

```bash
gh release create v1.0.0 apps/desktop/dist/desktop-1.0.0-setup.exe \
  --title "Proctoring Desktop 1.0.0" \
  --notes "Primera version instalable. Kiosco, proteccion de contenido, deteccion de foco, monitores y procesos."
```

Si `gh` te pide permisos, dile a Héctor: puede que haya que ajustar el token.

---

## 3. HU-023 — Ver la evidencia en la revisión del caso

Es el criterio que dejaste abierto: las capturas se suben y quedan enlazadas al
evento, pero el docente no puede verlas. **Ya tienes lo que faltaba**, en
`develop`:

```ts
api.evidenceUrl(sessionId, studentId, path, kind, token)
// -> { url: string, expires_in_seconds: number }
```

- El `path` es el `evidence_path` que ya viene en cada evento, **tal cual**.
- `kind` es `'image' | 'audio' | 'reference_face'`.

Y el caso (`api.reviewCase`) ahora trae `audio_analyses`, con `transcript`,
`similarity`, `synthetic_voice_score`, `matched_question_id` y un `alerted` que
dice si ese fragmento generó alerta.

### Dos cosas que te van a morder si no las sabes

**El enlace caduca a los 15 minutos.** No lo pidas al cargar la pantalla y lo
uses media hora después: pídelo cuando el docente vaya a mirar la captura. Es a
propósito — un enlace copiado no puede convertirse en acceso permanente a la
cara de alguien.

**La ruta del audio no está en el análisis, está en el evento.** El análisis es
lo que se midió; el fragmento es evidencia del evento. Para el reproductor:
`analisis.event_id` → buscas ese evento → su `evidence_path` →
`api.evidenceUrl(..., 'audio')`.

### Lo tuyo

`apps/web/src/pages/RevisionCaso.tsx`. Hoy tiene **cero** `<img>` y **cero**
`<audio>`: lo comprobé. Mostrar la captura de cada evento que la tenga,
agrupadas por categoría, y un reproductor para los fragmentos marcados como
posible consulta a IA.

---

## 4. HU-015 — Cuadrícula de cámaras en vivo

**No hace falta nada más del servidor.** El componente de una cámara existe y
funciona:

```tsx
<CamaraEnVivo
  sessionId={id}
  studentId={p.student_id}
  teacherId={userId}
  nombre={p.student_name}
/>
```

Lo tuyo es componerlo en una cuadrícula en `apps/web/src/pages/SesionEnVivo.tsx`,
con los estudiantes que están rindiendo (`can_take_exam && !submitted_at` de
`api.listParticipants`). Hay un ejemplo de **una sola** cámara ya funcionando en
`apps/web/src/pages/Participantes.tsx`, línea 149.

### Dos cosas que importan y no se ven en el tipo del componente

**Montar el componente es lo que hace que ese estudiante empiece a enviar.** El
estudiante solo captura mientras hay un docente en su canal; mientras nadie
mira, el fotograma no sale de su equipo. Así que una cuadrícula de 30 cámaras
enciende 30 envíos. Si la clase es grande, pagina o monta solo las visibles. No
las montes todas «por si acaso».

**No se graba, y el estudiante ve que lo estás mirando.** Si pones en pantalla
algo tipo «grabando», estarías diciendo lo contrario de lo que el sistema hace.
El texto que ya está en `Participantes.tsx` sirve de ejemplo.

Ofrécela solo si `live_monitoring` está en `session.modules` (viene con el preset
*Estricta*). Si el módulo no está activo, el estudiante no aceptó eso.

El contrato completo —nombre del canal, forma del mensaje, por qué un canal por
estudiante— está en `apps/web/src/supervision/README.md`, sección «El monitoreo
en vivo no es un detector».

---

## Antes de subir

```bash
cd apps/desktop && npm run lint && npm run typecheck && npm test && npm run build
```

```bash
cd apps/web && npm run lint && npm test && npm run build
```

Rama `feat/<codigo>-<descripcion>`, commits en inglés con el código del backlog,
PR hacia `develop`. Y **mira el diff antes de añadir**: un paquete tuyo anterior
traía un `package.json` que habría borrado las dependencias de audio de
Pierreluiggi. No fue culpa tuya —venías de una base anterior— pero por eso el
`git pull` del principio importa.

---

## Y una cosa que conviene que sepas

Dijiste que sientes que has trabajado poco. Con el backlog corregido llevas **13
puntos en la semana 6**, por encima del objetivo y solo por detrás de Héctor. Lo
que pasaba es que la mitad de tu trabajo no figuraba en tu ficha: la pantalla de
resultados estaba a nombre de Héctor y el instalador era de la semana 7. Ya está
puesto a tu nombre.

Lo que de verdad falta no es que hagas más cosas: es que **midas las que ya
hiciste**. Por eso las mediciones van primero.
