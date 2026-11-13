# Jesús — Rendimiento de la cámara y calibración

> Responsable: Jesús Limay. Sigue a `jesus-camara-encuadre-y-mirada.md` y `jesus-disponibilidad.md`.
> Reunión del 07/11: «lo de la cámara ya está integrado; le falta calibrar» y «está muy lenta».

## 1. Rendimiento: el examen ya no se congela

### Qué pasaba

Los tres modelos de MediaPipe (rostro, objetos y pose) corrían en el **hilo principal** del
navegador, el mismo que dibuja la página y que envía la vista en vivo al docente. Mientras un modelo
calculaba, la página no podía pintar.

### Cómo se midió

Chromium con los modelos reales de `public/mediapipe/`, una cámara simulada de 960×540 con un rostro,
los módulos `gaze`, `extra_person` y `objects` (más el encuadre), el mismo ciclo de 125 ms de
`useSupervision` y la captura de la vista en vivo a 8 fps. Equipo de 2 núcleos; en un portátil de
4 núcleos o más, los números absolutos son mejores, pero la diferencia se mantiene.

| | Antes | Solo fotograma reducido y turnos | **Con el motor en un worker** |
|---|---|---|---|
| Hilo principal ocupado | 86 % | 82 % | **5–6 %** |
| Fluidez de la interfaz | 18 fps | 22 fps | **60 fps** |
| Ciclo más lento (congelamiento) | 810 ms | 423 ms | **8–14 ms** |
| Vista en vivo del docente (configurada a 8) | 7 fps | 7,7 fps | **8 fps** |
| Análisis por segundo (rostro / objetos / pose) | 6,9 / ~4 / ~2 | similar | 4,6 / 3,2 / 1,1 |

Los análisis por segundo bajan un poco porque el worker usa un solo núcleo y salta fotogramas en
lugar de acumularlos. Aun así sobran: las reglas exigen 3 s (mirada), 5 s (rostro ausente y
encuadre), 2 s (persona extra) y 0,5 s (objeto).

### Qué se cambió

| Archivo | Cambio |
|---|---|
| `detectores/motor.worker.ts` (nuevo) | Los tres modelos en un Web Worker **clásico**. MediaPipe carga su WASM con `importScripts`, que un worker de módulo no tiene (comprobado: «self.import is not a function») |
| `detectores/motorRemoto.ts` (nuevo) | Cliente: pide un fotograma por ciclo reducido a 640 px (`createImageBitmap`, transferido sin copiar), **salta fotogramas si el worker está ocupado** y turna objetos y pose. Si el worker no arranca, falla o tarda más de 5 s, se termina y los detectores **vuelven al hilo principal** |
| `detectores/motorProtocolo.ts` (nuevo) | Tipos de los mensajes, compartidos por las dos puntas |
| `detectores/fotograma.ts` (nuevo) | Camino de respaldo en el hilo principal: fotograma reducido una vez por ciclo y un solo modelo pesado por ciclo |
| `detectores/vision-core.ts` | `compactarRostro` y `medicionDesdeRostro`: la misma función calcula la medición en el worker y en el hilo principal, así que las reglas no pueden dar otro resultado según dónde corrió el modelo |
| `detectores/vision.ts`, `objetos.ts`, `encuadre.ts` | Leen del worker si está activo; si no, usan su motor local como antes |

Sin cambios en la configuración de Vercel: la CSP ya permite `worker-src 'self'` y
`'wasm-unsafe-eval'`. La app de escritorio carga el examen desde la web, así que usa lo mismo.
`npm run build` genera `assets/motor.worker-*.js` (IIFE, ~127 KB); se comprobó que ese archivo
carga los tres modelos y analiza un fotograma real (1 rostro, 52 blendshapes, 33 puntos de pose).

La calibración de la mirada y la comprobación de encuadre de la sala de espera siguen midiendo en el
hilo principal: necesitan la respuesta del fotograma que están mirando, y son unos segundos.

## 2. Calibración

### 2.1 Umbral facial (verificación de identidad)

Producción en Contabo usa el motor OpenCV SFace (`PERFIL=ligero`), pero el umbral seguía en **0,45**,
el valor pensado para ArcFace (InsightFace), que mide en otra escala. Con SFace, ese 0,45 dejaba como
«no coincide» a estudiantes que sí eran ellos.

Ahora es **0,363**: el umbral de coseno que publican los autores del modelo en su implementación de
referencia (`opencv_zoo/models/face_recognition_sface/sface.py`, `_threshold_cosine = 0.363`),
medido en LFW, donde la versión int8 que usamos acierta el 99,32 %.

- `services/api/src/proctoring_api/domain/identity.py` y `exam_session.py`: el valor por defecto.
- Las sesiones ya creadas guardan su umbral: el cambio aplica a las nuevas.
- Confirmarlo con fotos del equipo sigue pendiente (SPEC-005):
  `FACE_ENGINE=opencv uv run python -m spikes.face_verify pares.csv` da FAR/FRR por umbral.

### 2.2 Calibración de la mirada (sala de espera)

| Problema | Corrección |
|---|---|
| Cada paso tomaba **un** fotograma: un parpadeo en ese instante falseaba los ojos para todo el examen | Seis fotogramas por paso y la mediana (`combinarMuestras`); hacen falta 4 con un solo rostro |
| Se podía mirar las piernas en «esquina inferior» y subir el umbral de los ojos hasta apagar la regla | Un paso que baja la vista más de 0,55 sobre el centro se rechaza y se repite (`validarPaso`) |
| La mirada lateral con los ojos no se calibraba | Las cuatro esquinas fijan `eyeSideThreshold` (entre 0,55 y 0,8) |
| Se presentaba como «opcional», sin decir para qué sirve | «Recomendada»: explica que evita avisos falsos. **Sigue sin bloquear** la entrada, por el criterio de accesibilidad del 07/11 (el sistema no prohíbe: deja evidencia y decide el docente) |

Las calibraciones guardadas antes de este cambio siguen cargando.

## 3. Cómo repetir la medición

1. `npm run build` en `apps/web` y abrir un examen con mirada y objetos activos.
2. En las herramientas del navegador, pestaña **Performance**, grabar 20 s durante el examen.
3. Antes: bloques largos de «Task» en el hilo principal. Ahora: el trabajo aparece en el hilo
   `motor-vision` y el principal queda casi libre.
4. En la consola, si el worker se cae se ve: `[visión] el motor en segundo plano se detuvo; sigue en
   el hilo principal: …`.

## 4. Pendiente

- Probar en 2 o 3 portátiles reales del equipo, sobre todo uno de gama baja, y anotar los números.
- Confirmar 0,363 con pares de fotos propios (TA-029).
- Opcional: probar el delegado de GPU de MediaPipe en el worker. Puede ser más rápido en portátiles
  con GPU integrada, pero no se pudo medir aquí, sin GPU, así que no se activó.
