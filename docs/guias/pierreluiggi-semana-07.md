# Pierreluiggi · semana 7

**Lunes 12/10 → viernes 16/10.** Revisión del sprint el sábado 17.

Eres el dueño de **todo lo que entra por el micrófono**: permiso, captura,
transcripción, análisis y guardado del fragmento. Y compartes con Jesús el aviso
que el estudiante ve mientras rinde.

**7 tareas, 12 puntos.**

## La regla de esta semana

**No des por funcionando nada que no hayas visto funcionar.** Tu módulo pasa
pruebas automatizadas, pero esas simulan `fetch` y simulan el audio. Esta semana
todo se prueba contra Supabase y Storage reales, y también **cuando falla**: sin
permiso, sin red, con el micrófono silenciado.

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

## TA-070 · Deepgram sustituye a faster-whisper · 2 pt

**Archivo:** `services/ai/audio_runtime.py`, por dentro de `measure_audio`.

El contrato **no se toca**. El worker sigue recibiendo el mismo trabajo
(`GET /internal/audio-jobs/{event_id}`) y devolviendo los mismos campos
(`transcript`, `similarity`, `synthetic_voice_score`, `processing_ms`,
`model_versions`). Solo cambia de dónde sale el texto.

```
antes:  descargar audio → faster-whisper local → texto
ahora:  descargar audio → POST a Deepgram → texto
```

**El motivo real, para que lo sepas.** El profesor lo pidió porque pensaba que el
modelo viaja dentro del instalador y que por eso la app pesaría un giga. Lo
comprobé y **no es así**: `faster-whisper` corre en `services/ai`, en el
servidor, y el `.exe` no lleva ningún modelo. Eso puedes decírselo.

Lo que sí es cierto, y es más urgente: **1 GB no entra cómodo en un Hugging Face
Space gratuito**. Arranque en frío larguísimo y memoria al límite. Sin quitarlo
no hay servicio de IA desplegado.

**Qué tienes que hacer:**

- [ ] La transcripción sale de Deepgram
- [ ] La clave va en `.env` y GitHub Secrets. **Nunca en el repositorio**, ni de ejemplo
- [ ] Quitar `faster-whisper` de `pyproject.toml` y del `requirements` — es la mitad del beneficio
- [ ] `model_versions` dice qué motor se usó, para poder comparar mediciones viejas con nuevas
- [ ] **Probado con un audio real subido a Storage**, no con un simulacro

> **Guarda tu medición con faster-whisper.** El WER de 17,7 % que ya tienes es un
> resultado válido. No lo borres: es la comparativa que justifica el cambio, y
> eso en el informe vale más que el cambio en sí.

---

## TA-071 · Pedir y probar el micrófono antes del examen · 2 pt

Hoy el micrófono se abre cuando el examen ya empezó. Si el estudiante lo tiene
silenciado, o eligió el aparato que no era, se entera tarde — o no se entera
nunca y nosotros creemos que no habló.

Va en la **sala de espera**, junto a la comprobación de cámara que hizo Jesús.

- [ ] Se pide el micrófono después del consentimiento
- [ ] **Una barra de nivel que se mueva al hablar.** Un texto que diga «micrófono listo» no prueba nada: tiene que *ver* que su voz llega
- [ ] Se le pide una frase corta y se confirma que el VAD la detecta — eso prueba la cadena entera, no solo el permiso
- [ ] Los errores dicen qué hacer: elegir otro aparato, quitar el silencio, dar permiso
- [ ] **Probado con el micrófono desconectado, silenciado y con permiso denegado**

Reutiliza `abrirCamara({ audio: true })` de `apps/web/src/supervision/camara.ts`:
ya resuelve permisos y traduce los errores del navegador. No lo reimplementes.

> **Un micrófono que no funciona no puede impedir rendir.** Igual que con la
> cara: se avisa, queda registrado y el docente decide. Nadie se queda sin examen
> por un periférico.

---

## TA-072 · Completar el guardado del fragmento señalado · 1 pt

Hay piezas puestas, pero **nadie ha visto la cadena entera funcionar**. Eso es lo
que hay que cerrar.

- [ ] Un fragmento con alerta **se reproduce** desde la revisión del caso (Rider ya hizo el reproductor)
- [ ] Solo se sube audio con habla, nunca el micrófono continuo
- [ ] Mide **cuánto espacio ocupa por examen** y anótalo
- [ ] Probado contra Storage real, no contra el almacenamiento en memoria

El profesor preguntó por la acumulación de espacio y es una pregunta justa:
Storage gratuito tiene límite.

---

## TA-064 · Aceptación del worker con Redis y Storage reales · 2 pt

Esta es la que de verdad dice si tu módulo funciona. Hasta ahora el worker se ha
probado en local y con simulacros.

- [ ] Un evento `speech_detected` real encola un trabajo en Redis
- [ ] El worker lo recoge, descarga el audio de Storage y lo analiza
- [ ] El resultado vuelve a la API y aparece en la revisión del caso
- [ ] Probado con el worker en un proceso aparte, no en el mismo de la API

**Es una de las tres pruebas de las que depende el despliegue.** Hasta que esta
esté en verde, no publicamos.

---

## HU-009 · Alerta de consulta a IA por voz, versión 1 · 1 pt

La regla que no se toca:

> Solo hay alerta si se cumplen **las dos** condiciones: lo que dijo se parece al
> enunciado **y** responde una segunda voz sintética.
>
> **Leer la pregunta en voz alta para concentrarse NO genera alerta.**

`speech_detected` nace **siempre** con severidad baja. Solo la API la escala. No
lo decidas en el cliente ni en el worker.

- [ ] Probado con los dos casos: alguien leyendo en voz alta (sin alerta) y alguien preguntándole a una IA (con alerta)

---

## HU-025 · El aviso al estudiante, con Jesús · 2 pt

Hasta ahora el estudiante veía las alertas **al terminar**. Ahora se le avisa
**durante**, y **diciéndole qué se detectó**: «se detectó una segunda voz», no un
genérico.

Tú pones las de audio, Jesús las de cámara, pero **el aviso en pantalla es uno
solo**. Pónganse de acuerdo en el componente **antes** de escribir dos, o el
estudiante acaba con dos cajas distintas diciendo cosas parecidas. Decídanlo en
la daily, no por mensajes sueltos.

- [ ] Un solo componente compartido
- [ ] No se repite el mismo aviso mientras la condición siga activa — **un aviso cada tres segundos es ruido** y pone nervioso a quien no hace nada malo
- [ ] El tono documenta, no acusa: nada de «estás copiando»
- [ ] No tapa el enunciado de la pregunta — háblalo con Rider, que está tocando esa pantalla
- [ ] Probado con los dos módulos disparando a la vez

---

## TA-062 · Lo que arrastras de la semana 6 · 2 pt

Las mediciones de **similitud y voz sintética**. Lo comprobé: en
`services/ai/results/` no hay ni una.

Es el diferencial del proyecto y lo único del equipo que sigue sin un solo
número. Tres grupos de grabación:

| Grupo | Qué se graba | Qué debe dar |
|---|---|---|
| **Control legítimo** | Alguien lee la pregunta en voz alta y nada más | similitud alta, voz sintética baja → **sin alerta** |
| **Habla cualquiera** | Conversación normal, no sobre el examen | similitud baja → **sin alerta** |
| **La trampa** | Lee la pregunta y una IA responde en voz alta | ambas altas → **alerta** |

El primero importa más que los otros dos juntos: es el que mide **falsos
positivos**, y la meta es FPR < 20 %. Si acusamos a alguien por leer en voz alta,
el sistema no sirve.

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
entra al repositorio**.
