# Pierreluiggi · lo que falta para cerrar

**Fecha límite del equipo: jueves 15/10.** Tu código está fusionado en `develop` (PR #43).

> Si pegas esto en un chat de IA: el proyecto es una plataforma de proctoring para
> exámenes remotos (UPAO, Taller Integrador 1). Tu parte es `services/ai`: el
> worker RQ que transcribe el audio, lo compara con el enunciado de la pregunta y
> detecta voz sintética. **Código, identificadores y commits en inglés; la interfaz
> en español.** Lee `CLAUDE.md` en la raíz antes de tocar nada.
>
> **La regla que define el proyecto:** solo hay alerta de IA por voz si se cumplen
> **las dos** condiciones — lo que se dijo se parece al enunciado **y** una segunda
> voz sintética responde. Leer en voz alta para concentrarse **nunca** debe alertar.
> Y el worker **mide**, la API **decide**: el worker no emite alertas.

## Antes de empezar

```bash
git checkout develop && git pull
```

```bash
cd services/ai && uv sync --locked
```

---

## Lo que YA entró (no lo rehagas)

- **TA-070** — Deepgram sustituye a faster-whisper. Fusionado.
- **TA-071** — `PruebaMicrofono.tsx` montado en la sala de espera. Fusionado.
- **HU-025** — tu anti-rebote quedó como `GestorDeAvisos`, fusionado con la redacción de Jesús.
- **TA-064** — tu prueba de cola contra Redis real. Fusionada, con dos correcciones (abajo).

### Dos cosas que te corregí al integrar, para que lo sepas

**1. Tu `audio_runtime.py` de la última entrega era anterior** y revertía el cambio
de URL firmada: volvía a exigir `SUPABASE_URL` y la clave de servicio en el worker.
Esa clave salta el RLS y abre todas las tablas y todos los buckets; el worker ahora
recibe una URL firmada de corta vida en el job y no necesita ninguna clave. **Parte
siempre de `develop`, no de tu copia local vieja.**

**2. Tu prueba de Redis borraba la cola de verdad.** El fixture hacía `flushdb()`
sobre lo que apuntara `REDIS_URL`, y en `.env` eso es `redis://redis:6379/0`, la
cola real. Correr la suite con el entorno documentado habría borrado los trabajos
de audio pendientes. Ahora la base 15 se fuerza siempre.

---

## 1. TA-064 · Medir la latencia de verdad · **bloquea el despliegue**

Tu informe dice que el presupuesto de 10 s «se cumple holgadamente con 2.14 s».
**Eso no está medido.** En esa prueba el ASR, la similitud, el detector de voz
sintética, la descarga de Storage y las dos llamadas HTTP están simulados con
`Mock`. En mi máquina la misma prueba tarda **61 ms**, porque no se infiere nada;
tus 2 141 ms eran el arranque del worker de RQ.

La prueba **sí** vale, y es la primera del proyecto que ejercita la cola de verdad.
Pero mide la cola, no la latencia.

Lo que falta es **una sola corrida cronometrada de punta a punta, sin mocks**:

- [ ] Audio real de un estudiante hablando (los tuyos de `p2_physical_test` sirven)
- [ ] Deepgram real, con la clave puesta
- [ ] Modelo de similitud real cargado
- [ ] API real respondiendo
- [ ] **El número medido**, desglosado por etapa, y si cumple o no los 10 s

Si no cumple, **también es un resultado válido** y hay que decirlo. Lo que no
puede pasar es presentar como medido algo que no se midió: es lo primero que el
profesor va a mirar, porque es el objetivo SMART del proyecto.

## 2. TA-062 · El número que falta en tu informe

Tu resumen dice «Accuracy 92,20 %, FPR 0,00 %». La metodología es sólida —umbral
desde un set de calibración aparte, XTTS reservado para test, escalador solo con
entrenamiento, semilla y hashes registrados— y eso hay que decirlo.

Pero el JSON crudo dice `tp:22 fp:0 fn:11 tn:108`. Eso es **FNR del 33,3 %: se le
escapa una de cada tres voces sintéticas**. Y con ese balance de clases, un
clasificador que conteste «todo es real» saca 76,6 % de accuracy.

- [ ] Añadir FNR y recall al informe, junto al accuracy y el FPR
- [ ] Decir explícitamente cuál es la línea base trivial (76,6 %) para que el 92 % se pueda interpretar
- [ ] Explicar qué significa en la práctica: el sistema **no caza** un tercio de los casos, y eso es coherente con ser auditor y no juez

No es un fallo tuyo: un FPR de 0 % con este umbral es justo lo que queremos
(preferimos no alertar antes que acusar a alguien inocente). Pero hay que contarlo
entero.

## 3. TA-071 · Evidencia con micrófono real

El componente está fusionado y las firmas verificadas, pero **no tiene prueba
automatizada**: el proyecto corre vitest con `environment: 'node'` y sin
testing-library, así que no se puede montar un componente. Lo dejé así a propósito;
meter jsdom a mitad de semana es una decisión de herramienta que no tomo solo.

Así que la verificación es tuya y es manual:

- [ ] Con micrófono real: se pide permiso, se ve la barra de nivel, la frase se detecta
- [ ] **Denegando el permiso**: sale el mensaje y **se puede entrar igual** al examen
- [ ] Sin micrófono conectado
- [ ] En la web **y** en la aplicación de escritorio
- [ ] Captura o vídeo de cada caso

## 4. TA-072 · La medición de almacenamiento

Tienes el informe escrito. Falta que los números salgan de una corrida real y que
digan cuánto ocupa una sesión completa, para saber si el plan gratuito de Supabase
aguanta un examen de 30 estudiantes.

---

## Antes de subir

```bash
cd services/ai && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

Las evidencias (capturas, vídeos, informes) van **al Notion**, no al repositorio.
