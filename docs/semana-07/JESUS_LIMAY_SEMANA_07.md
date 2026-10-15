# Jesús Limay — Semana 7: cámara y supervisión durante el examen

**Base usada para este paquete:** `Taller(1).zip`, árbol `develop` en commit `32b3fbf`.
No se consultó ni modificó GitHub; si `develop` avanzó después, integrar los cambios por diff, no reemplazar el directorio completo.

## Alcance implementado en el código

| Código | Función | Estado |
|---|---|---|
| TA-018 | Captura JPEG **una sola vez por condición sostenida**, subida por URL firmada/PUT y `evidence_path` en el evento | Código y pruebas unitarias escritos; **requiere validación real con Storage y docente** |
| TA-075 | Interfaz de registro de referencia y solicitud de verificación facial (HU-006 preexistente) conservada; cámara de supervisión con estado y reintento | **Requiere prueba real** de referencia, comparación, poca luz, lentes y ausencia de expulsión |
| TA-073 | Umbrales configurables desde sesión; no se cambian 25°, 3000 ms, 0,45 sin muestras | **Pendiente de calibración empírica** |
| TA-074 | Herramientas de dataset/evaluación preexistentes conservadas, instrucciones y validador de resultados | **Pendiente de grabar y etiquetar clips**; no se crean cifras ficticias |
| TA-065 | Pipeline/worker de verificación facial existente sin sobrescribir | **Pendiente de prueba genuino/impostor y P90 real** |
| HU-025 | Componente único de aviso para voz y cámara, sin acusar, flotante sin tapar enunciado y una vez por episodio | Código y pruebas, **pendiente comprobar módulos simultáneos** |

## Qué hace la cámara

1. `RendirExamen.tsx` obtiene los módulos activos de la sesión y usa `useSupervision`.
2. Tras el consentimiento, `abrirCamara()` solicita cámara **una sola vez**; se reutiliza el mismo `MediaStream` para MediaPipe, vista previa y monitoreo en vivo cuando el docente lo permite.
3. El indicador **Cámara activa** muestra la imagen local. Al entregarse el examen, desmontarse la pantalla o deshabilitarse supervisión, se detienen las pistas. Si el dispositivo se desconecta, hay mensaje y botón de reintento; ningún detector puede forzar que funcione una cámara físicamente desconectada.
4. MediaPipe `FaceLandmarker` detecta cantidad de rostros, yaw y pitch; la condición `gaze_away` mide **orientación de cabeza, NO seguimiento ocular exacto**. No existe en este paquete una detección fiable de movimiento físico de la cámara o de desenfoque óptico: hace falta diseñar, medir y calibrar esas condiciones antes de afirmar lo contrario.
5. `SeguimientoCondicion` conserva la regla de **un evento por episodio** y duración. `CapturasPorCondicion` captura un JPEG al alcanzar la duración mínima, durante la condición; `EmisorDeSenales` lo sube a Storage como `image` por `PUT` y envía la ruta como `evidence_path` cuando el episodio se cierra.
6. El componente `AvisoSupervision` muestra advertencias específicas de cabeza girada, cara ausente, persona adicional y voz. Es flotante, descartable y no bloquea el examen. **No acusa al estudiante**.

## Sobre la indicación del profesor: «solo MediaPipe»

**En cliente**, todas las detecciones visuales de este paquete usan solamente `@mediapipe/tasks-vision` / `FaceLandmarker`; no se agregó ninguna otra API de visión. Los cambios de esta semana **no** añaden InsightFace.

**En el backend previamente existente**, `services/ai/face_pipeline.py` utiliza InsightFace / ArcFace para obtener embeddings y decidir similitud facial. Esto significa que **la plataforma completa aún NO cumple** una exigencia literal de «únicamente MediaPipe para la verificación de identidad». FaceLandmarker da landmarks, presencia y orientación, pero **no proporciona embeddings de identidad fiables**. Sustituir ArcFace por una comparación simple de landmarks no sería una verificación segura y podría aceptar a la persona incorrecta. Esta discrepancia debe resolverse con el docente y el responsable de IA antes de considerar TA-065 aceptada. El paquete conserva el backend existente para no romper los contratos y la admisión manual.

## Modelo MediaPipe y despliegue

Este ZIP base **no contiene** `public/mediapipe/face_landmarker.task` ni `node_modules/@mediapipe/tasks-vision`. El `prebuild` actualizado ejecuta `vision:prepare`: copia los `.wasm` instalados y **falla explícitamente** si no se aportó el modelo local. No se inventaron binarios, hashes ni licencia. Se genera `provenance.json` con SHA-256 de los bytes reales una vez aportado el archivo del modelo. Verificar origen y licencia antes de distribuirlo.

En Windows / PowerShell, desde `apps/web`:

```powershell
npm ci
npm run vision:prepare -- --model "C:\\ruta\\autorizada\\face_landmarker.task"
npm run lint
npm test
npm run build
```

La URL de recursos es siempre local al origen de la app: `/mediapipe/wasm` y `/mediapipe/face_landmarker.task`. No se usa CDN al rendir.

## Seguridad y privacidad

- Cámara abierta después del consentimiento; se detiene tras finalizar el examen.
- **Sin grabación continua.** Solo captura por condición confirmada y audio acotado por el detector de voz ya existente.
- Evidencia en bucket privado `image`, URL firmada, `PUT`, ruta validada con sesión/estudiante. No se guarda imagen dentro del `metadata` ni se publica en Git.
- La imagen puede fallar al subirse: el emisor reintenta; para fallo de captura local la metadata incluye `capture_error` y puede producirse evento sin foto. Revisar logs durante integración.
- Las alertas no determinan fraude. Verificación facial fallida no expulsa al alumno; el docente decide.

## Pruebas comprobables

Se incorporaron `capturasVision.test.ts`, `imageUpload.test.ts`, `emisor.image.test.ts` y `avisos.test.ts`. Las pruebas visuales/end-to-end **no se han ejecutado** con cámara o Supabase en este entorno. La compilación de tipos y lint fueron revisadas con dependencias temporales simuladas porque el ZIP incluía librerías incompletas; realizar `npm ci` real en el equipo y repetir toda la suite.

No afirmar accuracy, FPR, FAR, FRR o P90 hasta tener resultados reales y un conjunto final separado del de calibración. Ver `PROTOCOLO_DE_PRUEBAS.md`.

## Archivos propios principales

- `apps/web/src/supervision/capturasVision.ts` y `imageUpload.ts` — TA-018
- `apps/web/src/supervision/useSupervision.ts`, `emisor.ts`, `tipos.ts` — conexión de captura y emisión
- `apps/web/src/supervision/avisos.ts`, `apps/web/src/components/AvisoSupervision.tsx`, `apps/web/src/styles/avisos-supervision.css` — HU-025
- `apps/web/src/pages/RendirExamen.tsx` — vista previa, avisos, reconexión
- `apps/web/spikes/vision/tools/prepare_assets.mjs`, `apps/web/package.json` — validación obligatoria de assets en build
- `apps/web/spikes/vision/tools/verificar_metricas.py` — lectura/validación sin fabricar resultados

### Comprobación previa de una cara en identidad (MediaPipe)

En `VerificacionFacialEspera.tsx` se llama `contarRostrosEnCamara()` de
`detectores/vision.ts` antes de capturar JPEG: requiere exactamente **un rostro**,
con feedback de iluminación o encuadre. No se confunde *una cara presente* con
*identidad confirmada*. Necesita el modelo MediaPipe local para operar.
