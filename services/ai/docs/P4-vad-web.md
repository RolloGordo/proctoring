# P4 · Silero VAD y evidencia de audio

6 h estimadas en la nueva guía; no horas registradas. Implementación local con
`@ricky0123/vad-web` 0.0.30 (Silero v5) y `onnxruntime-web` 1.22.0.

## Qué se cambió y por qué

- `apps/web/src/supervision/detectores/voz.ts`: usa la pista ya autorizada por
  la pantalla del examen. Silero detecta habla; MediaRecorder guarda WebM/Opus
  durante esos episodios. Descarta falsos arranques y el fragmento abierto al cerrar.
- `tipos.ts` y `useSupervision.ts`: pasan la pista y el envío al detector. El
  audio gestiona sus propios segmentos y no emite además un evento vacío.
  Los detectores de visión conservan su seguimiento existente.
- `audioUpload.ts`: pide una URL con JSON, sube el Blob directo a Storage con PUT,
  y devuelve la ruta. No envía el JWT de la API al Storage.
- `emisor.ts`: captura el identificador de pregunta al inicio del fragmento;
  conserva esa pregunta aunque la subida demore; no emite sin evidencia. Reutiliza
  una subida exitosa al reintentar el evento. Limita a tres audios pendientes.
- `scripts/prepare-vad.mjs`: copia modelo/worklet/WASM desde dependencias bloqueadas
  a `public/vad`, con hashes. No se solicitan modelos a un CDN durante el examen.

Hay cambios mínimos de conexión fuera de `voz.ts`: sin ellos la plantilla no
recibía la pista ni podía adjuntar `evidence_path`. El líder debe revisar estos
archivos al integrar con la web de Rider; no reemplazar toda su carpeta.

## Decisión sobre fragmentos largos

Se corta a los 10 s y reinicia el estado de Silero, incluido su búfer PCM. Así no
se retiene una intervención de varios minutos. Una intervención larga produce
varios fragmentos/eventos de audio, no eventos por fotograma. Es una adaptación
explícita de la regla de «un evento por condición» que debe revisar el líder.
Puede perderse un pequeño inicio al detectar voz o al reiniciar; se debe medir
su efecto en WER. Se permite una cola breve de silencio (400 ms) para cerrar habla.

## Ejecutar

Node >=22.12 (verificación realizada con 24.19.0):

```powershell
cd apps/web
npm ci
npm run dev
```

`predev` y `prebuild` preparan los assets. Los modelos/WASM y `node_modules` no
se distribuyen en el ZIP: se reconstruyen con las versiones de `package-lock.json`.
Vitest se actualizó a 4.1.11 para corregir los avisos de las herramientas de prueba.
No se cambió ninguna pantalla. Usar una sesión con ai_voice habilitado y el flujo
de consentimiento existente. Para el flujo completo hacen falta API y Storage
configurados; la subida a Storage simulado no demuestra una subida real.

## Validación y límites

Pruebas con dobles de MediaRecorder/Silero/fetch: silencio no graba; inicio/fin
envía un fragmento; misfire/cierre descartan; se limita duración; Storage recibe
audio y la API solo JSON; se conserva pregunta y no hay evento sin evidencia.
Se comprobó compilación, tipos y lint. Pendiente prueba con micrófono real,
permisos de navegador/Electron, CSP, eco, errores de red y llegada al docente.
No se ha medido accuracy/FPR del VAD. No se instala captura continua de audio.
