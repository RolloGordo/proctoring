# Jesús · semana 7

**Lunes 12/10 → viernes 16/10.** Revisión del sprint el sábado 17.

Eres el dueño de **todo lo que entra por la cámara**: identidad, rostro, mirada,
persona adicional, capturas y las métricas que lo respaldan. Y compartes con
Pierreluiggi el aviso que el estudiante ve mientras rinde.

**6 tareas, 10 puntos.**

## La regla de esta semana

**No des por funcionando nada que no hayas visto funcionar.** Tu módulo pasa
pruebas automatizadas y la cadena de endpoints está comprobada contra Supabase,
pero **nadie ha visto la verificación facial correr en un navegador con sesión
iniciada**. Esta semana eso se prueba, y se prueba también cuando falla: con mala
luz, con lentes, a contraluz.

## Antes de nada

```bash
git checkout develop && git pull
```

```bash
npm install --prefix apps/web
```

```bash
docker compose up -d --build api
```

El `npm install` importa: toqué el `package.json` de la web por un fallo de
despliegue de tu módulo, y lo explico ahora mismo.

---

## 0. Lo que te arreglé, para que lo sepas

Tu detección de visión **no habría funcionado en el sistema desplegado**, y no se
habría notado.

`vision.ts` pide `/mediapipe/wasm` y `/mediapipe/face_landmarker.task`. Esa
carpeta estaba en `.gitignore` y el script que la prepara nunca se enganchó al
build, así que esos archivos solo existían en tu máquina. En este checkout **el
modelo no estaba en absoluto**.

Y como `useSupervision` descarta un detector que no carga y deja seguir el
examen, la web publicada habría corrido **sin rostro, sin mirada y sin persona
adicional**, sin un solo error en pantalla.

Lo resolví con el patrón que Pierreluiggi ya tenía para el VAD: los `.wasm` se
copian de `node_modules` en el `prebuild`, el modelo quedó versionado con su
licencia (Apache-2.0) y su sha256 en `public/mediapipe/provenance.json`, y **si
falta, el build falla** en vez de publicar un examen ciego.

> Entiendo por qué no lo habías versionado — tu README dice «descargar con
> licencia y procedencia verificadas» y «no incluir el modelo en el
> repositorio». Era una decisión razonada. Pero el modelo no está publicado en
> npm, así que no hay forma de traerlo en el build sin depender de Google en
> mitad de un despliegue.

---

## TA-018 · Capturas cuando se detecta algo · 1 pt · **empieza por aquí**

**Hoy los detectores de visión no mandan ni una captura.** Lo comprobé: solo el
de voz usa `captureSender`. Cuando salta mirada fuera de pantalla o persona
adicional, el evento llega **sin `evidence_path`** y el docente, en la pantalla
de revisión que Rider acaba de construir, **no tiene nada que mirar**.

Es la pieza que hace que todo lo demás sirva. Sin imagen, el docente lee «mirada
fuera de pantalla, 4,5 s» y tiene que creérselo.

Lo que necesitas ya existe:

- `capturarFotograma(video, calidad)` en `apps/web/src/supervision/camara.ts`
- `context.captureSender()` — mira cómo lo usa `voz.ts`, línea 100

### El **cuándo** importa más que el cómo

El profesor lo corrigió en la reunión. Tu idea era tomar foto al principio, a
mitad y al final. Él dijo:

> «Cuando se esté moviendo, por ejemplo, ahí recién tienes que tomar captura.»

**La captura se toma cuando la condición se cumple**, no en momentos fijos. Una
foto del minuto 30 no prueba nada si no pasó nada en el minuto 30; la que importa
es la del instante en que el detector dijo «hay dos caras».

Eso encaja con la regla del proyecto: un evento por condición, con su duración, y
**una** captura que lo respalda. Ni una por fotograma.

- [ ] Probado de punta a punta: salta el detector → se sube la captura → el docente la abre desde la revisión del caso

---

## TA-075 · Probar la verificación facial en el navegador · 1 pt

HU-006 está fusionada y yo comprobé la cadena de endpoints contra Supabase (10 de
10). Pero **nadie la ha visto correr en un navegador con sesión iniciada**.
Pruébala como la usaría un estudiante.

- [ ] Un estudiante real registra su foto de referencia desde la sala
- [ ] Pide la comparación y la sala se actualiza sola cuando llega el resultado
- [ ] **Una verificación fallida deja esperando, no expulsa**
- [ ] Probado **con mala luz y con lentes**, para ver qué pasa cuando falla de verdad
- [ ] Capturas de cada paso para la evidencia

---

## TA-073 · Calibrar los umbrales con datos propios · 2 pt

Dijiste en la reunión que es donde más tiempo se te fue, y es verdad que los
números de hoy son un punto de partida, no un resultado medido:

```python
SupervisionModule.GAZE: {"yaw_degrees": 25, "min_duration_ms": 3000},
SupervisionModule.EXTRA_PERSON: {"min_faces": 2},
SupervisionModule.FACE_VERIFICATION: {"similarity_threshold": 0.45},
```

Están en `services/api/src/proctoring_api/domain/exam_session.py`, en un solo
sitio a propósito: se calibran ahí y los tres clientes se enteran.

- [ ] Cada umbral queda justificado **con una medición**, no con una intuición
- [ ] Si cambia, se cambia ahí y se explica por qué
- [ ] Probado con poca luz, con lentes y a contraluz, no solo en condiciones buenas
- [ ] **Si un número no cumple la meta, se anota igual.** Es un hallazgo, no un fracaso

---

## TA-074 · Medir accuracy y FPR · 2 pt

Tu propio README lo dice, y está muy bien que lo diga:

> «las métricas de accuracy/FPR siguen **pendientes de medición**. No se
> inventaron datos ni capturas.»

Lo comprobé: `apps/web/spikes/vision/datasets/manifest.csv` tiene **solo la
cabecera**, cero filas, y no hay `results/evaluation.json`.

Tus herramientas ya están (`tools/dataset.py`, `tools/evaluate.py`): esto es
grabar, etiquetar y correr.

**Qué grabar**, con el equipo y con consentimiento:

| Condición | Para qué |
|---|---|
| Mirando la pantalla, normal | Mide **falsos positivos** de `gaze`. La más importante |
| Mirando claramente fuera | Aciertos de `gaze` |
| Nadie delante de la cámara | `face_absent` |
| Dos o tres personas a la vez | `extra_person`, y probar `min_faces=3` |
| Mala luz, lentes, contraluz | Donde el sistema se equivoca |

La primera importa más que todas las demás juntas. Si marcamos mirada fuera de
pantalla a alguien que estaba pensando, el módulo no sirve por mucho que acierte
en lo fácil.

- [ ] `results/evaluation.json` con matriz de confusión, accuracy y FPR por detector
- [ ] Conjunto de prueba final **separado** del de calibrado
- [ ] Meta: accuracy ≥ 80 % y FPR < 20 % por detector

> El profesor sugirió mirar si hay algo más ligero (OpenCV, o un modelo pequeño
> entrenado solo para esto). Vale la pena mirarlo **con una medición al lado**:
> si lo ligero acierta igual, se cambia; si no, el dato justifica quedarse. No lo
> cambies solo porque lo dijo.

---

## TA-065 · Aceptación de la verificación facial con el modelo real · 2 pt

Esta es la que de verdad dice si tu módulo funciona: el worker comparando caras
de verdad, no un simulacro.

- [ ] El worker recoge el trabajo, descarga las dos imágenes y compara
- [ ] El resultado vuelve a la API y la sala del docente se actualiza
- [ ] Probado con la misma persona (debe coincidir) y con dos personas distintas (no debe)

**Es una de las tres pruebas de las que depende el despliegue.** Hasta que esté
en verde, no publicamos.

---

## HU-025 · El aviso al estudiante, con Pierreluiggi · 2 pt

Hasta ahora el estudiante las veía **al terminar**. Ahora se le avisa
**durante**, y **diciendo qué se detectó**: «se detectó una segunda persona», no
un genérico.

Tú pones las de cámara, Pierreluiggi las de audio, pero **el aviso es uno solo**.
Pónganse de acuerdo en el componente **antes** de escribir dos. Decídanlo en la
daily.

- [ ] Un solo componente compartido
- [ ] No se repite mientras la condición siga activa — **un aviso cada tres segundos es ruido**
- [ ] Documenta, no acusa: nada de «estás copiando»
- [ ] No tapa el enunciado — háblalo con Rider, que está tocando esa pantalla
- [ ] Probado con los dos módulos disparando a la vez

---

## Antes de subir

```bash
cd apps/web && npm run lint && npm test && npm run build
```

```bash
cd services/api && uv run ruff check . && uv run mypy src && uv run pytest
```

Rama `feat/<codigo>-<descripcion>`, commits en inglés con el código del backlog,
PR hacia `develop`. Y mira el diff antes de añadir: dos entregas tuyas anteriores
venían de una base vieja y habrían revertido trabajo de otros. Por eso el `git
pull` del principio importa tanto.
