# Jesús · correcciones del primer examen real

Héctor rindió un examen completo contra el **sistema desplegado** el 16/10.
Durante el examen habló, miró el celular, se salió del encuadre y miró a los
costados. **No se registró ni una sola señal de cámara, ni una captura.**

Tus detecciones de proceso y foco (las de la app de escritorio) sí funcionaron
perfectamente. Lo que no produjo nada fue la visión.

> **Contexto si pegas esto en un chat de IA:** plataforma de proctoring para
> exámenes remotos (UPAO, Taller Integrador 1). Tu parte es la visión por
> computadora en `apps/web/src/supervision/` y el mantenimiento de la base en
> `supabase/migrations`. **Código y commits en inglés; interfaz en español;
> tablas en snake_case.** Lee `CLAUDE.md`. **El sistema es auditor, no juez:**
> nunca expulsa a nadie, registra y decide el docente.

```bash
git checkout develop && git pull && npm install --prefix apps/web
```

Web desplegada: **https://proctoring-brown.vercel.app**

---

## Lo que ya arreglé, para que no lo busques

En producción faltaban las cabeceras COOP/COEP, así que no había
`SharedArrayBuffer` y el runtime de ONNX multihilo no arrancaba. Ya están en
`apps/web/vercel.json`. **Eso era condición necesaria, no la causa única.**

Antes de nada, abre la web desplegada, pulsa **F12** → pestaña **Console**, y
escribe:

```js
self.crossOriginIsolated
```

Tiene que decir `true`. Si dice `false`, avísame antes de seguir.

## 1 · Por qué no se registró nada (punto 9) · 3 pt · **lo primero**

`useSupervision` **descarta en silencio** los detectores que no consiguen
prepararse. Por eso no hubo ningún error en pantalla: simplemente no había
detector.

Averigua cuál es el caso. Con la consola abierta durante un examen real:

- [ ] ¿Se prepara el detector de visión, o lanza al prepararse?
- [ ] ¿Llega el `MediaStream` de la cámara al detector?
- [ ] ¿Se emiten señales y fallan al subirse, o no se emiten?

Y **que deje de fallar en silencio**: si un detector no arranca, el estudiante
tiene que verlo y el docente tiene que saber que ese módulo no estuvo activo
durante el examen. Una supervisión que no supervisó y nadie se entera es peor
que no tenerla.

- [ ] Un detector que no arranca se registra y se avisa, no se descarta callando
- [ ] Probado de punta a punta: mirar a un lado genera `gaze_away` y llega al docente
- [ ] Probado que la captura sube a Storage y el docente la abre desde la revisión

## 2 · La verificación facial no sirvió (punto 10) · 2 pt

Héctor tuvo que admitirse a mano desde la cuenta del docente. La verificación
automática no resolvió.

- [ ] Averiguar si falla la captura, la subida, el worker o la comparación
- [ ] Un fallo de verificación dice **por qué**, no solo que no pudo
- [ ] La admisión manual sigue existiendo: es la salida correcta cuando la cámara no reconoce a alguien
- [ ] Probado con buena y con mala luz

## 3 · La cámara en vivo va mal (punto 12) · 2 pt

> «La calidad de la cámara en vivo es muy mala, lenta en fotogramas.»

Y eso con **un** estudiante. Con treinta hay que saber qué pasa antes de la
demo.

- [ ] Medir cuántos fotogramas por segundo llegan de verdad y con cuánto retardo
- [ ] Decidir y escribir el compromiso: ¿más calidad o más fluidez? ¿cuántos estudiantes a la vez?
- [ ] Probado con al menos tres estudiantes simultáneos (pide ayuda a los demás)

## 4 · La detección es demasiado general (punto 19) · 2 pt

> «Muy general y poco precisa al indicar si estoy mirando a un costado, tengo un
> objeto extraño en la mano o si entra alguien al cuarto.»

Esto enlaza con tus métricas, que siguen sin tomarse. El objetivo del proyecto
es **accuracy ≥ 80 % y FPR < 20 % por módulo**, y de mirada y rostro no hay
ningún número.

- [ ] Casos etiquetados: mirada dentro/fuera, rostro presente/ausente, una persona/dos
- [ ] Accuracy, FPR y **FNR** por módulo
- [ ] Decir el número aunque no llegue al 80 %: un resultado medido que no cumple vale más que un «cumple» sin medir

## 5 · Falta el nombre del estudiante (punto 11) · 1 pt · con Rider

Las alertas dicen «Estudiante e989cb23» porque **no se pide nombre y apellidos
al registrarse**. La columna `profiles.full_name` existe y está vacía.

- [ ] El registro pide nombre y apellidos y los guarda en `profiles.full_name`
- [ ] Alertas, resultados y revisión del caso muestran el nombre, no el id
- [ ] Los perfiles que ya existen sin nombre no rompen nada: se ve el correo

> El formulario de registro es de Rider; la columna y la migración, tuyas.
> Pónganse de acuerdo antes de empezar para no hacerlo dos veces.

---

## Antes de subir

```bash
cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build
```

Si tocas la base, **crea una migración nueva** en `supabase/migrations`. No
toques el esquema desde el panel de Supabase.

---

# Añadido el 17/10 · lo que ya está descartado con pruebas

Integré tu entrega. **No busques la causa donde yo ya busqué**, que me costó
medio día. Todo esto está comprobado contra la web desplegada, no supuesto:

| Hipótesis | Resultado |
|---|---|
| Los modelos no están desplegados | **Falsa.** `/mediapipe/face_landmarker.task`, `/mediapipe/wasm/*` y `/vad/*` responden HTTP 200 con el tamaño y el `content-type` correctos |
| MediaPipe no arranca en producción | **Falsa.** `FaceLandmarker.createFromOptions` crea el landmarker en 1 491 ms, con `detectForVideo` disponible |
| Falta `SharedArrayBuffer` (COOP/COEP) | **Falsa ya.** `self.crossOriginIsolated === true` en la web desplegada |
| El `<video>` suelto no da fotogramas | **Falsa.** `readyState 4`, `videoWidth 640`, `currentTime` avanzando |
| La cola de eventos se atascó | **Falsa.** En las cinco sesiones los eventos llegan hasta el segundo de la entrega |
| Los nombres de módulo no coinciden | **Falsa.** El enum `supervision_module` trae `gaze`, `extra_person`, `ai_voice`, `external_voices`, todos activos |

Conclusión: **el detector de visión se prepara bien y observa, pero nunca
dictamina.** Queda por descartar el umbral y la medición: `yaw_degrees: 25` con
`min_duration_ms: 3000`, y los ángulos que salen de `angulosDesdeMatriz`.

## Lo que ahora te lo va a decir, sin adivinar

Tu `supervision_diagnostics` está integrada, **y le añadí un código más**:
`vision_module_summary`. Al terminar cada examen se escribe una fila por
detector con `frames`, `verdicts`, `episodes` y `failed`.

Así, tras el próximo examen:

```sql
select module, details from supervision_diagnostics
where code = 'vision_module_summary' order by created_at desc;
```

- `frames: 0` → el fotograma no llega al detector
- `frames: 4800, verdicts: 0` → **mira y nunca le parece que pase nada**: es el umbral o el cálculo del ángulo
- `verdicts: 300, episodes: 0` → la histéresis se come los episodios

Es la medición que faltaba. Empieza por ahí.

## De tu entrega: qué entró y qué no

**Entró:** `diagnostics.ts` y su prueba, la migración (ver abajo), el canal
`reportarVision` de `monitoreo.ts` con tu prueba, tu corrección del emisor
(importante: una subida fallida se llevaba la señal entera), la resolución de
cámara y los tres fallos seguidos antes de retirar un detector.

**No entró, y conviene que sepas por qué:**

- **`avisos.ts`** — tu versión parte de una base anterior y borra el
  `GestorDeAvisos` entero, que es HU-025 (silenciar repeticiones, agrupar
  simultáneas, retirar solo). Me quedé con la base actual más lo de Pierre.
- **`camara.ts`** — tu versión borra `abrirMicrofono()` y
  `traducirMicrofono()`, que son de Pierre y los usa `PruebaMicrofono.tsx`.
  Habría roto la compilación. Tomé solo los cambios de resolución.

No es culpa tuya: es que trabajaste sobre un `develop` de antes. **Haz `git
pull` antes de empezar**, siempre.

## Tu migración

Sigue **sin aplicar**: la decide Héctor. `recordDiagnostic` se come sus propios
errores, así que el código funciona sin la tabla (solo no registra nada).
Cuando se aplique, lleva ya el código `vision_module_summary` en el CHECK.

## El `live_monitoring` no se arreglaba donde lo arreglaste

Subiste `AJUSTES_POR_DEFECTO` en el cliente, pero esos ajustes se escriben en
`session_modules.settings` al crear la sesión, desde
`services/api/.../domain/exam_session.py`. El cliente solo los usa si no hay
nada en la base, y siempre hay algo. Lo cambié en el origen (2 fps, 480 px,
0,62). **Las sesiones ya creadas conservan los suyos**: para ver la mejora hay
que crear una sesión nueva.
