# SPEC-007 — Laboratorio de visión (J1 y J2)

## Estado real
Código del spike, detectores y evaluadores implementados. Los videos consentidos no venían en `Taller.zip`; las métricas de accuracy/FPR siguen **pendientes de medición**. No se inventaron datos ni capturas.

## Instalación y funcionamiento

Desde `apps/web`: `npm install` (requiere Internet) y `npm run dev`. Abrir `http://localhost:5173/spikes/vision/`. Dar permiso a la cámara y hacer clic en **Encender cámara**. El video permanece en el navegador, sin grabación continua. Se dibujan landmarks y se calculan yaw/pitch. Los eventos se agrupan con `SeguimientoCondicion` y, al cerrarse, se descarga una captura JPEG y se registra un evento en la página. El botón de exportación genera `predictions.csv` por fotograma para medición, sin guardar imágenes continuamente.

### Modelo/recursos en origen local (obligatorio en kiosco)

1. Tras `npm install`, copiar los archivos de `apps/web/node_modules/@mediapipe/tasks-vision/wasm/` a `apps/web/public/mediapipe/wasm/`.
2. Descargar **con licencia y procedencia verificadas** el modelo oficial `face_landmarker.task` en `apps/web/public/mediapipe/face_landmarker.task`.
3. **No incluir el modelo en el repositorio.** Desde `apps/web`, ejecutar `npm run vision:prepare -- --model <ruta_local_al_task>` para copiar WASM y modelo. El script `tools/prepare_assets.mjs` copia los `.wasm` y, si recibe `--model <ruta_local>` copia el modelo instalado con autorización. Nunca usa CDN al rendir.

El modelo detecta la **orientación de cabeza**, aproximación imperfecta a la mirada ocular: mirar teclado/techo no implica fraude.

## Dataset (J1)

Ver `datasets/README.md`. El comando `python tools/dataset.py verificar` confirma que existen videos consentidos, hashes correctos y etiquetas. Este ZIP incluye solamente el manifiesto vacío y la procedencia honesta.

## Evaluación J2

1. Realizar clips con duración y etiquetas (`datasets/etiquetas/<id>.txt`).
2. Abrir `http://localhost:5173/spikes/vision/`, seleccionar el clip local `P01_01.mp4` en el selector de video. El reproductor procesa fotogramas con el mismo modelo y, al terminar, descarga automáticamente `P01_01.csv` usando `video.currentTime` como tiempo de referencia. Guardar este CSV en `datasets/predictions/` sin subirlo a GitHub.
3. Ejecutar desde `apps/web/spikes/vision`: `python tools/evaluate.py --predictions-dir datasets/predictions`.
4. La salida `results/evaluation.json` incluye matriz de confusión, accuracy y FPR por detector, con hash del manifiesto y de las predicciones. Mantener el conjunto final separado del calibrado.

> El evaluador aplica duración mínima y compara eventos por segundos; no inventa resultados si faltan muestras. Una validación formal de extremos requiere confirmar sincronía entre tiempo del clip y el `time_ms` de las predicciones.

## Umbrales iniciales (no validados)

| Detector | Umbral inicial | Duración mínima |
|---|---:|---:|
| mirada | 25° yaw | 3.000 ms |
| rostro ausente | 0 rostros | 5.000 ms |
| persona adicional | ≥2 rostros | 2.000 ms |

Meta: accuracy ≥80 % y FPR <20 % por detector, aún por comprobar con J1.

## Ajuste tras revisión del equipo (9 de octubre)

El prototipo configura `numFaces: 3` y ofrece el selector de
`min_faces` 2/3 antes de iniciar un clip o cámara. El CSV exportado incluye
`min_faces` para documentar el umbral ensayado. En la aplicación integrada el modelo es **dinámico**: si el
docente configura `min_faces: 3`, MediaPipe se inicializa con capacidad para 3
rostros o se amplía mediante `setOptions`. El máximo operativo explícito es 10:
un valor fuera de 2–10 produce un error de preparación visible en consola, no
una condición imposible que falle silenciosamente. El motor se importa con
`import('@mediapipe/tasks-vision')` cuando se prepara la cámara, y la página de
examen tiene carga diferida; el panel docente no necesita descargar ese módulo.

**Pendiente de validación experimental:** dataset real etiquetado, accuracy/FPR,
pruebas de `min_faces=3` con 3 voluntarios a la vez, y medición de rendimiento
en máquina de examen. Sin esas pruebas la SPEC no se declara cerrada.
