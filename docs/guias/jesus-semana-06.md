# Jesús · lo que te queda de la semana 6

Estado comprobado contra `develop` el **10/10**. Cada afirmación de aquí se
verificó en el repositorio, no de memoria.

## Antes de nada

```bash
git checkout develop && git pull
```

```bash
docker compose up -d --build api
```

El segundo **no es opcional**. El contenedor de la API no recarga solo: si no lo
reconstruyes, sigue sirviendo el código viejo y vas a ver errores que parecen
del código que acabas de bajar. Repítelo cada vez que alguien toque
`services/api`.

## No estás bloqueado por nadie

Tu única tarea en Open depende solo de ti. El backend que necesita lleva días
hecho y fusionado.

## Lo tuyo que ya está dentro

SP-009 (detectores de rostro, persona adicional y orientación de cabeza),
TA-057 (auditoría de RLS y cierre de la escalada de privilegios), TA-061
(ajustes tras la revisión) y EN-010. Fusionados en los PR **#29** y **#33**.

Y `services/ai/face_pipeline.py` con InsightFace también está.

---

## HU-006 — Registrar foto de referencia · **tu única tarea en Open**

Esta es, ahora mismo, **el agujero más visible del producto**: el estudiante
entra al examen y **nadie le pide la cámara**.

Lo comprobé buscando en todo `apps/web/src` y `apps/desktop/src`: **ningún
cliente llama a los endpoints de identidad**. Resultado: la verificación se
queda en `pending` y el docente acaba admitiendo a mano a todo el mundo, que es
justo lo contrario de lo que el módulo promete.

### No te falta backend. Está todo hecho

| Endpoint | Para qué |
|---|---|
| `POST /api/v1/me/reference-face` | El estudiante registra, **una vez**, la cara con la que se le comparará |
| `POST /api/v1/evidence/upload-url` | URL firmada para subir la imagen a Storage |
| `POST /api/v1/exam/{session_id}/identity/check` | Manda la captura del día y pide la verificación |
| `GET /api/v1/internal/face-jobs/{participant_id}` | El worker recoge el trabajo |
| `POST /api/v1/internal/sessions/.../identity-result` | El worker devuelve el resultado |

Y el worker también: `verify_face` en `services/ai/tasks.py`, apoyado en tu
`face_pipeline.py`.

**Lo que falta es solo el cliente.**

### Lo tuyo, paso a paso

**Archivo:** `apps/web/src/pages/SalaDeEspera.tsx` (hoy no abre la cámara en
ningún momento: lo comprobé).

1. **Abrir la cámara** con `abrirCamara` de `apps/web/src/supervision/camara.ts`.
   Ya resuelve los permisos y traduce los errores del navegador a algo que el
   estudiante pueda accionar («no diste permiso», «otra aplicación está usando la
   cámara», «no se encontró una cámara»). No lo reimplementes.

2. **Capturar un fotograma** con `capturarFotograma` del mismo archivo. Devuelve
   un JPEG a resolución completa, que es lo que quieres para comparar caras.

3. **Subirlo directo a Storage** con URL firmada:
   `POST /api/v1/evidence/upload-url` con `kind: "reference_face"`, y después
   **subir con PUT, no con POST**.

   > ⚠️ Storage responde **400 a POST** y 200 a PUT. Esto ya nos costó un fallo
   > silencioso una vez: el 4xx se leía como «no hay evidencia disponible», el
   > evento se enviaba sin ruta, y no se guardaba ni una captura. Lo comprobé
   > contra el Storage real.

4. **Llamar a `identity/check`** con la ruta devuelta.

5. **No hagas nada más.** La sala ya se actualiza sola: `session_participants`
   está publicada en Realtime y la pantalla del docente escucha los cambios.

### La regla que no se toca

**Una verificación fallida no expulsa a nadie.** Deja al estudiante esperando, y
el docente lo admite a mano desde su sala. Mala luz, lentes o una cámara barata
no pueden costarle el examen a nadie.

Eso ya está así en la API (`RecordIdentityCheck` lo dice explícitamente). Lo que
hace falta es que **la pantalla no lo contradiga**: nada de «identidad
rechazada, no puedes entrar». El mensaje correcto es que el docente va a
revisarlo.

### Por qué esto va antes que TA-017

TA-017 (verificación con ArcFace) no se puede medir de verdad mientras no haya
fotos de referencia contra las que comparar. HU-006 es lo que le da material.

---

## Lo que sigue pendiente de SP-009 (no está en Open, pero lo sabes)

Tu propio README lo dice, y está bien que lo diga:

> «las métricas de accuracy/FPR siguen **pendientes de medición**. No se
> inventaron datos ni capturas.»

Lo comprobé: `apps/web/spikes/vision/datasets/manifest.csv` tiene **solo la
cabecera**, cero filas. Y no hay `results/evaluation.json`.

Para cerrar la meta SMART (**accuracy ≥ 80 % y FPR < 20 % por detector**) hace
falta el dataset etiquetado. Tus herramientas ya están listas
(`tools/dataset.py`, `tools/evaluate.py`), así que esto es grabar, etiquetar y
correr, no programar.

**Lo que conviene grabar**, con el equipo y con consentimiento:

| Condición | Para qué |
|---|---|
| Mirando la pantalla, normal | Mide **falsos positivos** de `gaze`. Es la más importante |
| Mirando claramente fuera | Mide los aciertos de `gaze` |
| Nadie delante de la cámara | `face_absent` |
| Dos o tres personas a la vez | `extra_person`, y de paso probar `min_faces=3` |
| Mala luz, lentes, contraluz | Los casos donde el sistema se equivoca |

El primero importa más que los otros. Si marcamos mirada fuera de pantalla a
alguien que solo estaba pensando, el módulo no sirve por mucho que acierte en
los casos fáciles.

**No inventes datos.** Que tu README diga que no se inventaron es una de las
mejores cosas que hay escritas en este repositorio; mantenlo así.

---

## Antes de subir

```bash
cd apps/web && npm run lint && npm test && npm run build
```

```bash
cd services/api && uv run ruff check . && uv run mypy src && uv run pytest
```

Rama `feat/<codigo>-<descripcion>`, commits en inglés con el código del backlog,
PR hacia `develop`.

Y **mira el diff antes de añadir**. Dos entregas tuyas anteriores venían de una
base antigua y habrían revertido trabajo de otros: un `package.json` sin las
dependencias de audio de Pierreluiggi, un `tasks.py` que pisaba su worker y un
`App.tsx` que borraba una ruta de Rider. No fue culpa tuya —venías de un `git
pull` viejo— pero por eso el pull del principio importa tanto.
