# Semana 6 · qué le falta a cada uno

Resumen de una página. **Cada uno tiene su archivo con el detalle**, y es
autocontenido: nadie necesita leer el de otro.

- [Rider](./rider-semana-06.md) — 4 tareas
- [Jesús](./jesus-semana-06.md) — 1 tarea
- [Pierreluiggi](./pierreluiggi-semana-06.md) — 1 tarea

Estado comprobado contra `develop` el **10/10**. Si algo aquí no coincide con lo
que les dijo otra herramienta, esto es lo verificado en el repositorio.

---

## Ya casi nada está bloqueado

Rider dijo: «hay unas que están vinculadas a otras, no se puede avanzar si no
terminan las que uno tiene». **Era cierto hasta anoche.** Ya no.

| Esperaba | A que terminara | Estado |
|---|---|---|
| HU-023 (Rider) | TA-056 de Héctor — URL firmada de lectura | ✅ **en `develop`** |
| HU-015 (Rider) | HU-022 de Héctor — el canal de monitoreo | ✅ **en `develop`** |
| TA-017 (Jesús) | HU-006 del propio Jesús | ⚠️ depende de él mismo |
| TA-062 (Pierre) | Grabaciones del equipo | ⚠️ 10 minutos de cada uno |

**No hay ninguna tarea esperando a otra persona**, salvo que Pierre necesita que
le graben audios.

---

## Antes de empezar, los tres

```bash
git checkout develop && git pull
```

```bash
docker compose up -d --build api
```

El segundo no es opcional: el contenedor de la API **no recarga solo**. Si no lo
reconstruyen, sigue sirviendo el código viejo y verán errores que parecen del
código recién bajado (`Extra inputs are not permitted` en campos que sí
existen). Pasa cada vez que alguien toca `services/api`.

---

## Una línea por persona

**[Rider](./rider-semana-06.md)** — medir lo que ya construyó (es lo primero y
nadie más puede hacerlo), publicar el Release, y dos vistas que ya tienen todo
lo que necesitaban del servidor: la evidencia en la revisión del caso y la
cuadrícula de cámaras.

**[Jesús](./jesus-semana-06.md)** — la pantalla que pide la cámara al entrar.
Los cinco endpoints y el worker con InsightFace llevan días hechos; falta solo
el cliente. Es el agujero más visible del producto: hoy nadie le pide la cámara
al estudiante.

**[Pierreluiggi](./pierreluiggi-semana-06.md)** — grabar tres grupos de audio y
medir similitud y voz sintética. Es el diferencial del proyecto y es lo único
que sigue sin un solo número.

---

## El patrón de la semana

A los tres les queda sobre todo **medir**, no programar. Eso es exactamente lo
que sostiene la meta SMART de **accuracy ≥ 80 % y FPR < 20 % por módulo**, y es
lo que el docente va a pedir ver.

Lo que verifiqué para decir esto:

- `gh release list` está vacío → EN-011/TA-060 pendientes de verdad.
- Los cinco criterios de `apps/desktop/README.md` siguen sin marcar → TA-015 pendiente.
- `RevisionCaso.tsx` tiene cero `<img>` y cero `<audio>` → HU-023 parcial.
- Ningún cliente llama a los endpoints de identidad → HU-006 es el agujero visible.
- `services/ai/results/` no tiene ni una medición de similitud o voz sintética → TA-062.
- `apps/web/spikes/vision/datasets/manifest.csv` tiene solo la cabecera, cero filas.
