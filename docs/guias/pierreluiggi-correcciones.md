# Pierreluiggi · correcciones del primer examen real

Héctor rindió un examen completo contra el **sistema desplegado** el 16/10.
Habló en voz alta varias veces durante el examen. **No se subió ni un fragmento
de audio, ni se registró ninguna señal de voz.**

En la revisión del caso, el apartado dice literalmente: «No hay fragmentos de
audio señalados como alerta».

> **Contexto si pegas esto en un chat de IA:** plataforma de proctoring para
> exámenes remotos (UPAO, Taller Integrador 1). Tu parte es `services/ai`: el
> worker que transcribe el audio, lo compara con el enunciado y detecta voz
> sintética, más la detección de habla en el navegador
> (`apps/web/src/supervision/detectores/voz.ts`). **Código y commits en inglés;
> interfaz en español.** Lee `CLAUDE.md`.
>
> **La regla que define el proyecto:** solo hay alerta si se cumplen **las dos**
> condiciones — lo dicho se parece al enunciado **y** responde una segunda voz
> sintética. Leer en voz alta nunca debe alertar. Y el worker **mide**, la API
> **decide**.

```bash
git checkout develop && git pull
```

```bash
cd services/ai && uv sync --locked
```

---

## Lo que ya arreglé, para que no lo busques

**En producción no había `SharedArrayBuffer`.** Las cabeceras COOP/COEP solo
estaban en el servidor de desarrollo, y el VAD solo trae el runtime de ONNX
**multihilo**, que lo necesita. Medido en la web desplegada:
`crossOriginIsolated: false`, cuando en local era `true`.

Ya están puestas en `apps/web/vercel.json`. Antes de nada, abre la web
desplegada, pulsa **F12** → **Console** y escribe:

```js
self.crossOriginIsolated
```

Tiene que decir `true`.

También está desplegado el worker, en Render: su salud responde
`{"queue": true, "queues": ["high","audio"]}`, o sea está conectado a la cola.

## 1 · Por qué no se subió nada (punto 9) · 3 pt · **lo primero**

Con las cabeceras puestas, sigue el rastro de punta a punta. `useSupervision`
**descarta en silencio** un detector que no consigue prepararse, así que un
fallo del VAD no deja ni rastro en pantalla.

Con la consola abierta durante un examen real contra la web desplegada:

- [ ] ¿Arranca Silero? ¿O lanza al preparar?
- [ ] Al hablar, ¿se emite `speech_detected`?
- [ ] ¿Se sube el fragmento a Storage con la URL firmada?
- [ ] ¿Llega el trabajo a la cola y lo coge el worker? (mira los logs en Render)
- [ ] ¿Vuelve el resultado a la API?

Rompe la cadena por donde se rompa y arréglalo ahí. Y **que deje de fallar
callando**: si el VAD no arranca, el estudiante tiene que verlo y el docente
tiene que saber que ese módulo no estuvo activo. Tu `PruebaMicrofono` ya lo
hace en la sala de espera; hace falta lo mismo durante el examen.

## 2 · El arranque en frío (importante para la demo) · 1 pt

El plan gratuito apaga el worker sin uso y tarda cerca de un minuto en volver.
La API lo despierta al encolar (lo añadí), pero **el primer análisis tras un
rato dormido se pasa del presupuesto de 10 s**.

- [ ] Medir cuánto tarda de verdad el primer análisis tras una pausa
- [ ] Medir cuánto tarda con el worker ya despierto, que es el número que vale para el objetivo
- [ ] Decir los dos en el informe. Esconder el primero sería mentir por omisión

## 3 · TA-064: la latencia sigue sin medirse · 2 pt · **bloquea el cierre**

Esto sigue igual que cuando lo revisé. Tu prueba de cola contra Redis real es
buena y es la primera que ejercita la cola de verdad, pero **todo lo caro está
simulado**: el ASR, la similitud, el detector y las dos llamadas HTTP. Aquí
tarda 61 ms, no los 2 141 ms que el informe atribuye a inferencia.

Falta **una sola corrida cronometrada sin mocks**: audio real, Deepgram real,
modelo de similitud real, API real, y el número desglosado por etapa.

Si no cumple los 10 s, también es un resultado válido. Lo que no se puede es
presentar como medido algo que no se midió.

## 4 · TA-062: el número que falta · 1 pt

Tu informe dice «Accuracy 92,20 %, FPR 0,00 %». El JSON crudo dice
`tp:22 fp:0 fn:11 tn:108`, o sea **FNR del 33,3 %: se escapa una de cada tres
voces sintéticas**. Y con ese balance, decir «todo es real» saca 76,6 %.

- [ ] Añadir FNR y recall junto al accuracy y el FPR
- [ ] Decir cuál es la línea base trivial, para que el 92 % se pueda interpretar
- [ ] Explicar qué significa: el sistema no caza un tercio de los casos, y eso es coherente con ser auditor y no juez

---

## Antes de subir

```bash
cd services/ai && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

> Pasa **mypy** además de ruff y pytest. El CI me pilló nueve errores de tipos
> por saltármelo.

Las evidencias (capturas, vídeos, informes) van **al Notion**, no al repositorio.

---

# Añadido el 17/10 · integré tu entrega y mido lo que faltaba

Buen trabajo en dos cosas concretas:

- **Mediste TA-064 de verdad**, sin mocks: **54,3 s en frío y 5,11 s en
  caliente**. El segundo cumple el presupuesto de 10 s con margen, y dijiste sin
  maquillar que el frío no lo cumple por el plan gratuito. Eso cierra la tarea.
- Diagnosticaste el COOP/COEP por tu cuenta y llegaste a la misma causa.

**Entró tu `avisos.ts` completo** (`ProblemaAudio`, `avisoAudio`,
`avisoDetectorFallido`), que era aditivo y limpio — al contrario que el de
Jesús, que partía de una base vieja. Le añadí `avisoDetectoresNoDisponibles`
para cuando caen varios módulos a la vez: cuatro cuadros de aviso encima de
alguien que está rindiendo son peor que uno.

Tu mecanismo del `useSupervision` quedó, pero escrito sobre la versión actual:
un módulo que no arranca entra en `fallidos`, el estudiante lo ve, el docente lo
ve en vivo y queda registrado. `avisoDetectorFallido` sigue siendo quien decide,
así que `habla` sigue dando el mensaje de micrófono y no el de cámara.

## Lo que ya está descartado con pruebas

Comprobado contra la web desplegada, no supuesto:

- `self.crossOriginIsolated === true` — tu corrección está viva en producción
- `/vad/silero_vad_v5.onnx`, `/vad/ort-wasm-simd-threaded.wasm` y
  `/vad/vad.worklet.bundle.min.js` responden **HTTP 200** con el tamaño correcto
- La cola de eventos **nunca se atascó**: en las cinco sesiones los eventos
  llegan hasta el segundo de la entrega
- `ai_voice` y `external_voices` están activos en la base, con
  `similarity_threshold: 0.6` y `synthetic_threshold: 0.5`

Así que el VAD **puede** arrancar en producción. Lo que no sabemos es si
arranca.

## Un fallo que arreglé y que te afectaba a ti

En `emisor.ts`, si `uploadAudio` lanzaba, **la señal entera desaparecía**: ni
fragmento de audio ni rastro de que se hubiera detectado voz. Y lo segundo es lo
que de verdad importa. Jesús lo había visto para las imágenes; el audio tenía el
mismo problema. Ahora el evento se manda igual, con
`metadata.capture_error = 'upload_failed'`.

Además, el reintento era **mudo**: con la cola atascada no llegaba nada a la API
y no quedaba ni una línea en consola. Ahora lo dice.

## Lo que te va a contestar la pregunta, sin adivinar

Hay una tabla `supervision_diagnostics` (de Jesús) y le añadí el código
`vision_module_summary`: al terminar cada examen se escribe una fila por
detector. **El de habla tiene fila propia**, aunque no cuente fotogramas,
porque es la mitad del problema.

```sql
select module, details from supervision_diagnostics
where code = 'vision_module_summary' and module = 'habla'
order by created_at desc;
```

- No hay fila, pero sí una `vision_module_failed` con `module: 'habla'` →
  **el VAD no arrancó**, y `details.reason` dice por qué
- `self_emitting: true, episodes: 0` → arrancó y nunca oyó habla: mira el umbral
  del VAD y si la pista de audio llega de verdad al detector

Empieza por ahí antes de tocar nada.

## Sigue pendiente (del documento de arriba)

- **TA-062**: el FNR del 33,3 % sigue sin estar en el informe. El accuracy del
  92,2 % con `tp:22 fp:0 fn:11 tn:108` significa que se escapa **una de cada
  tres** voces sintéticas, y decir «todo es real» saca 76,6 %. Hay que decirlo:
  es coherente con ser auditor y no juez, pero hay que decirlo.
