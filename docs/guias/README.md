# Guías de trabajo

Una por integrante, con **qué archivos tocar y qué hacer exactamente**. No
repiten la arquitectura: para eso está [`CLAUDE.md`](../../CLAUDE.md) y
[`docs/estado-y-plan-de-trabajo.md`](../estado-y-plan-de-trabajo.md).

| Quién | Guía | Qué le toca |
|---|---|---|
| Jesús Limay | [jesus-vision.md](jesus-vision.md) | Rostro, mirada, persona adicional, verificación de identidad |
| Pierreluiggi Zevallos | [pierreluiggi-ia-audio.md](pierreluiggi-ia-audio.md) | Detección de habla, transcripción, similitud, voz sintética, importación QTI |
| Rider Rodriguez | [rider-escritorio.md](rider-escritorio.md) | Capturas de evidencia, pantalla compartida, instalador, UI |
| Héctor Silva | — | API, banco de preguntas, monitoreo en vivo, despliegue |

> Cuando una guía dice **(nuevo)** junto a una ruta, ese archivo todavía no
> existe: lo creas tú. Todo lo demás que se cita sí está en el repositorio.

---

## Cómo trabajar (esto vale para los cuatro)

### 1. Antes de empezar, actualiza

```bash
git checkout develop
git pull
```

**Hazlo cada día.** La mayoría de los conflictos de este proyecto han salido de
trabajar sobre una copia vieja.

### 2. Una rama por tarea

```bash
git checkout -b feat/SPEC-007-deteccion-mirada
```

El nombre es `feat/<código>-<qué-hace>`. Los códigos están en cada guía.

### 3. Toca solo tu carpeta

| Quién | Carpeta |
|---|---|
| Jesús | `apps/web/spikes/vision/`, `apps/web/src/supervision/detectores/vision.ts`, `supabase/migrations/` |
| Pierreluiggi | `services/ai/`, `apps/web/src/supervision/detectores/voz.ts` |
| Rider | `apps/desktop/`, `apps/web/src/` (interfaz) |

Si necesitas algo de otra carpeta, **pídelo** en vez de cambiarlo. Subir una copia
desactualizada de la carpeta de otro es como se revierte sin querer el trabajo
ajeno, y ya pasó dos veces.

### 4. Antes de subir, pasa la puerta

La misma que corre el CI. Si falla aquí, fallará allá:

```bash
cd services/api && uv run ruff format . && uv run ruff check . && uv run mypy . && uv run pytest && uv run lint-imports
```

```bash
cd services/ai && uv run ruff format . && uv run ruff check . && uv run mypy . && uv run pytest
```

```bash
cd apps/web && npm run lint && npm test && npm run build
```

```bash
cd apps/desktop && npm run lint && npm run typecheck && npm test && npm run build
```

### 5. Commit y pull request

Mensajes **en inglés**, con el formato `tipo(código): qué hace`:

```
feat(SPEC-007): detect gaze away with MediaPipe
```

Tipos: `feat`, `fix`, `test`, `docs`, `chore`, `ci`.

```bash
git push -u origin feat/SPEC-007-deteccion-mirada
```

Después abre el PR hacia `develop` desde GitHub. **No se empuja a `main`.**

### Terminado significa

- [ ] PR a `develop` con el CI en verde (los 7 jobs)
- [ ] Una prueba que cubra el criterio de aceptación de tu tarea
- [ ] README o docstring actualizado
- [ ] Evidencia (captura o vídeo) para el Notion de Héctor

---

## Tres reglas del proyecto que ninguna tarea rompe

**1. No se graba vídeo continuo.** La cámara del estudiante se *mira* en vivo
mientras rinde, pero no se guarda. Lo único que queda después son **capturas de
los eventos que fueron alerta** y los **fragmentos de audio** marcados. Un
detector que guarde vídeo entero rompe la promesa que el sistema le hace al
estudiante en la pantalla de consentimiento.

**2. Un evento por condición, no uno por fotograma.** Las detecciones con
duración emiten **un solo evento al cerrarse**, con cuánto duró. Emitir uno por
fotograma multiplica los falsos positivos y revienta la meta de FPR < 20 %. Esto
ya está resuelto en `SeguimientoCondicion`: úsalo, no lo reimplementes.

**3. El sistema no acusa, documenta.** Ningún detector decide que alguien copió.
Mide, guarda los números y el docente resuelve con una justificación escrita. En
particular, `speech_detected` es **siempre** severidad baja: hablar en voz alta
es legítimo.

---

## Medir es parte del trabajo, no un extra

La meta del proyecto es **accuracy ≥ 80 % y FPR < 20 % por módulo**. Un detector
que funciona "cuando lo probé" no cuenta. Protocolo común:

1. **Aparta un conjunto de prueba final** que no uses para ajustar umbrales.
   Calibra con una parte, reporta con otra. Pierreluiggi ya marca sus resultados
   como `exploratory_not_final_test`: mantengan ese rigor.
2. **Reporta accuracy, FPR y la matriz de confusión.**
3. **Mide en condiciones difíciles**, no solo en las buenas: poca luz, lentes,
   ruido de fondo, voz de IA mezclada con la propia. Si solo mides en lo fácil, el
   FPR real será mucho peor.
4. **Guarda cada resultado** en `results/*.json` con los parámetros, los hashes de
   los datos y el entorno, como ya hace `services/ai`.

### Datos personales

Rostros y voces son datos sensibles. **Solo personas del equipo, con
consentimiento escrito**, y los archivos **nunca al repositorio** (`.gitignore`).
Se versionan solo manifiestos, procedencia y resultados.
