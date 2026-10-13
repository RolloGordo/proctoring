# Jesús · semana 7

**Entrega: sábado 17/10.** Esa semana el sistema tiene que estar desplegado y
funcionando en público.

Eres el dueño de **todo lo que entra por la cámara**: identidad, rostro, mirada,
persona adicional, capturas y las métricas que lo respaldan. Y compartes con
Pierreluiggi las alertas que el estudiante ve mientras rinde.

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

El `npm install` importa esta semana: toqué el `package.json` de la web por un
fallo de despliegue de tu módulo, y lo explico abajo.

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

Lo resolví siguiendo el patrón que Pierreluiggi ya tenía para el VAD: los `.wasm`
se copian de `node_modules` en el `prebuild`, y el modelo quedó versionado con su
licencia (Apache-2.0) y su sha256 en `public/mediapipe/provenance.json`.

> Entiendo por qué no lo habías versionado — tu README dice «descargar con
> licencia y procedencia verificadas» y «no incluir el modelo en el
> repositorio». Era una decisión razonada. Pero el modelo no está publicado en
> npm, así que no hay forma de traerlo en el build sin depender de Google en
> mitad de un despliegue. Versionarlo con la procedencia al lado cumple lo que tú
> querías y además no se puede romper.

---

## 1. Capturas cuando se detecta algo · lo más importante

**Hoy los detectores de visión no mandan ni una captura.** Lo comprobé: solo el
de voz usa `captureSender`. Así que cuando salta mirada fuera de pantalla o
persona adicional, el evento llega **sin `evidence_path`** y el docente, en la
pantalla de revisión que Rider acaba de construir, no tiene nada que mirar.

Es la pieza que hace que todo lo demás sirva: sin imagen, el docente ve «mirada
fuera de pantalla, 4,5 s» y tiene que creérselo.

### Cómo hacerlo

Lo que necesitas ya existe:

- `capturarFotograma(video, calidad)` en `apps/web/src/supervision/camara.ts`
- `context.captureSender()` en el contexto del detector — mira cómo lo usa
  `voz.ts`, línea 100, es el mismo mecanismo

### Y el **cuándo** importa más que el cómo

El profesor lo corrigió en la reunión y conviene entenderlo bien. Tu idea era
tomar foto al principio, a mitad y al final. Él dijo que no:

> «Cuando se esté moviendo, por ejemplo, ahí recién tienes que tomar captura.»

O sea: **la captura se toma cuando la condición se cumple**, no en momentos
fijos. Una foto del minuto 30 no prueba nada si no pasó nada en el minuto 30; la
que importa es la del instante en que el detector dijo «hay dos caras».

Eso además encaja con la regla del proyecto: un evento por condición, con su
duración, y **una** captura que lo respalda. Ni una por fotograma.

---

## 2. Calibración

Dijiste en la reunión que es donde más tiempo se te fue, y es verdad que los
umbrales de hoy son un punto de partida, no un resultado medido:

```python
SupervisionModule.GAZE: {"yaw_degrees": 25, "min_duration_ms": 3000},
SupervisionModule.EXTRA_PERSON: {"min_faces": 2},
SupervisionModule.FACE_VERIFICATION: {"similarity_threshold": 0.45},
```

Están en `services/api/src/proctoring_api/domain/exam_session.py`, en un solo
sitio a propósito: se calibran ahí y los tres clientes se enteran.

Lo que hace falta es **justificar esos números con datos**. Si 25 grados marca a
gente que solo estaba pensando, el resultado de tu trabajo es proponer el número
correcto con la medición al lado. Eso es lo que se espera, no que el número
quede bonito.

---

## 3. Métricas · lo que sigue sin existir

Tu propio README lo dice, y está muy bien que lo diga:

> «las métricas de accuracy/FPR siguen **pendientes de medición**. No se
> inventaron datos ni capturas.»

Lo comprobé: `apps/web/spikes/vision/datasets/manifest.csv` tiene **solo la
cabecera**, cero filas, y no hay `results/evaluation.json`.

La meta es **accuracy ≥ 80 % y FPR < 20 % por detector**. Tus herramientas ya
están (`tools/dataset.py`, `tools/evaluate.py`): esto es grabar, etiquetar y
correr.

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

> El profesor sugirió mirar si hay algo más ligero (OpenCV, o un modelo pequeño
> entrenado solo para esto). Vale la pena mirarlo **con una medición al lado**:
> si lo ligero acierta igual, se cambia; si no, el dato justifica quedarse. No lo
> cambies solo porque lo dijo.

---

## 4. Las alertas del estudiante, con Pierreluiggi

Hasta ahora el estudiante las veía **al terminar**. Ahora se le avisa
**durante**, y **diciendo qué se detectó**: «se detectó una segunda persona», no
un genérico.

Tú pones las de cámara, Pierreluiggi las de audio, pero **el aviso en pantalla es
uno solo**. Pónganse de acuerdo en el componente antes de escribir dos, o el
estudiante acaba con dos cajas distintas diciendo cosas parecidas. Decídanlo en
la daily.

Dos cuidados:

- **Un aviso cada tres segundos es ruido** y pone nervioso a quien no está
  haciendo nada. Agrupa, y no repitas mientras la condición siga activa.
- El sistema **documenta, no acusa**. «Se detectó una segunda persona» está
  bien; «estás copiando» no. Lo resuelve el docente.

---

## 5. Lo que te quedó de la semana 6

**HU-006** ya está fusionada (PR #38) y funciona: probé la cadena completa contra
el Supabase real, 10 de 10. Pero nadie la ha visto correr en un navegador con
sesión iniciada. Pruébala tú de punta a punta y sácale la captura.

**TA-017** (ArcFace) ahora sí se puede medir, porque ya hay fotos de referencia
contra las que comparar.

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
