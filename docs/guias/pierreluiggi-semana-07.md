# Pierreluiggi · semana 7

**Entrega: sábado 17/10.** Esa semana el sistema tiene que estar desplegado y
funcionando en público.

Eres el dueño de **todo lo que entra por el micrófono**: permiso, captura,
transcripción, análisis y el guardado del fragmento. Y compartes con Jesús las
alertas que el estudiante ve mientras rinde.

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

---

## 1. Deepgram sustituye a faster-whisper

El profesor lo pidió en la reunión y tiene razón, aunque conviene que sepas el
motivo real, porque no es el que él dijo.

Él pensaba que el modelo viaja dentro del instalador y que por eso la app pesaría
un giga. **No es así:** `faster-whisper` corre en `services/ai`, en el servidor, y
el `.exe` no lleva ningún modelo. Eso puedes decírselo.

El problema de verdad es el despliegue: **un modelo de 1 GB no entra cómodo en un
Hugging Face Space gratuito**. Arranque en frío larguísimo y memoria al límite.
Si queremos el servicio de IA publicado el sábado, hay que quitarlo.

### Qué cambia exactamente

**Archivo:** `services/ai/audio_runtime.py`, por dentro de `measure_audio`.

El contrato **no se toca**. El worker sigue recibiendo el mismo trabajo
(`GET /internal/audio-jobs/{event_id}`) y sigue devolviendo lo mismo
(`transcript`, `similarity`, `synthetic_voice_score`, `processing_ms`,
`model_versions`). Solo cambia de dónde sale el `transcript`.

```
antes:  descargar audio -> faster-whisper local -> texto
ahora:  descargar audio -> POST a Deepgram -> texto
```

**La clave va en el servidor**, nunca en el navegador. `.env` en local y
**GitHub Secrets** en el despliegue. Si la clave acaba en el cliente, cualquiera
se gasta el crédito.

**Quita la dependencia** de `faster-whisper` del `pyproject.toml` y del
`requirements`. Es la mitad del beneficio: sin ella la imagen del servicio
adelgaza y se puede desplegar.

### Lo que no cambia, y conviene que no cambie

`model_versions` sigue existiendo. Pon ahí `{"stt": "deepgram-nova-2"}` o lo que
uses. Es lo que permite comparar mediciones viejas con nuevas: si dentro de tres
semanas el FPR sube, hay que poder saber con qué se midió cada cosa.

> **Guarda tus mediciones con faster-whisper.** El WER de 17,7 % que ya tienes es
> un resultado válido y citable. No lo borres: es la comparativa que justifica el
> cambio, y eso en el informe vale más que el cambio en sí.

---

## 2. El micrófono se pide y se prueba **antes** del examen

Hoy el micrófono se abre cuando empieza el examen. Si el estudiante lo tiene
silenciado, o eligió el micrófono que no es, se entera cuando ya está rindiendo
—o no se entera nunca y nosotros creemos que no habló.

Lo que falta es una comprobación en la **sala de espera**, junto a la de cámara
que acaba de hacer Jesús:

1. Pedir el micrófono (ya tienes `abrirCamara({ audio: true })` en
   `apps/web/src/supervision/camara.ts`; reutilízalo, resuelve los permisos y
   traduce los errores).
2. **Mostrar que entra sonido.** Una barra de nivel que se mueva al hablar. Un
   texto que diga «micrófono listo» no prueba nada: el estudiante tiene que
   *ver* que su voz llega.
3. Pedirle que diga una frase corta y confirmar que el VAD la detecta. Eso
   prueba la cadena entera, no solo el permiso.
4. Si falla, decir qué hacer: elegir otro micrófono, quitar el silencio, dar
   permiso en la barra del navegador.

**Un micrófono que no funciona no puede impedir rendir.** Igual que con la cara:
se avisa, queda registrado y el docente decide. Nadie se queda sin examen por un
periférico.

---

## 3. Guardar el fragmento cuando la voz es rara

Esto ya funciona a medias y hay que cerrarlo. Hoy se sube el fragmento de **todo**
`speech_detected`. Lo que falta es que el docente pueda **oír** lo que se marcó,
y que no se suba audio que no aporta.

- El fragmento se sube solo si hay habla (el VAD ya lo hace, bien).
- Rider ya construyó el reproductor en la revisión del caso y lee
  `audio_analyses[].alerted`. Comprueba de punta a punta que un fragmento
  marcado se puede reproducir desde ahí.
- Revisa cuánto está ocupando. El profesor preguntó por la acumulación de
  espacio y es una pregunta justa: Storage gratuito tiene límite.

### La regla que no se toca

> Solo hay alerta si se cumplen **las dos** condiciones: lo que dijo se parece al
> enunciado **y** responde una segunda voz sintética.
>
> **Leer la pregunta en voz alta para concentrarse NO genera alerta.**

`speech_detected` nace **siempre** con severidad baja. Solo la API la escala. No
lo decidas en el cliente ni en el worker.

---

## 4. Las alertas del estudiante, con Jesús

Hasta ahora el estudiante veía las alertas **al terminar**. Ahora se le avisa
**durante**, y **diciéndole qué se detectó**: «se detectó una segunda voz», no un
genérico.

Tú pones las de audio, Jesús las de cámara, pero **el aviso en pantalla es uno
solo**: pónganse de acuerdo en el componente antes de escribir dos. Si cada uno
hace el suyo, el estudiante acaba con dos cajas distintas diciendo cosas
parecidas.

Sugerencia de reparto: que uno haga el componente y el otro lo use. Decídanlo en
la daily, no por mensajes sueltos.

Cuidado con una cosa: **un aviso que aparece cada tres segundos es ruido** y
pone nervioso a quien no está haciendo nada malo. Agrupa, y no repitas el mismo
aviso mientras la condición siga activa.

---

## 5. Lo que te quedó de la semana 6

**TA-062** sigue abierta: grabaciones del equipo y medición de **similitud y voz
sintética**. Lo comprobé, en `services/ai/results/` no hay ni una medición de
esas dos cosas.

Es el diferencial del proyecto y lo único del equipo que sigue sin un solo
número. Si esta semana no entra entera, al menos deja el conjunto de control
—gente leyendo la pregunta en voz alta, sin trampa— que es el que mide los
falsos positivos.

---

## Antes de subir

```bash
cd services/ai && uv run pytest
```

```bash
cd services/api && uv run ruff check . && uv run mypy src && uv run pytest
```

Rama `feat/<codigo>-<descripcion>`, commits en inglés con el código del backlog,
PR hacia `develop`. Mira el diff antes de añadir, y **la clave de Deepgram no
entra al repositorio** ni en un ejemplo.
