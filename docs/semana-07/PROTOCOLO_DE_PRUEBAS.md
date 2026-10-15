# Semana 7 — Protocolo reproducible de aceptación (sin datos inventados)

**Identificador:** Jesús Limay. **Fecha del sprint:** 12 al 16 de octubre de 2026.

## Preparación segura

- Sincronizar la rama antes de modificar; **no copiar archivos antiguos** directamente sobre otros cambios de Rider/Pierreluiggi.
- Iniciar API (`docker compose up -d --build api`) y web (`npm ci`, `npm run dev`) con `.env` local real y Supabase de pruebas.
- Preparar los recursos WASM y `face_landmarker.task` oficial con licencia y SHA-256 verificable.
- Utilizar solamente voluntarios del equipo con consentimiento escrito, sin publicar rostros, grabaciones, tokens ni bases de prueba.
- Disponer de un estudiante y un docente autenticados en una sesión con `gaze`, `extra_person`, `face_verification` y, si se desea, voz.

## TA-018 — captura y docente

1. Rendir como estudiante y comprobar vista previa local e indicador **Cámara activa**.
2. Mirar fuera más de 3 segundos y luego volver. Ver **un aviso** durante la condición y **un evento** al terminar con `duration_ms`, `yaw_deg` y `evidence_path`.
3. Desde el panel docente, abrir el evento y **ver la foto del instante de la condición**. Comprobar URL firmada y ruta privada sin 403.
4. Repetir con rostro ausente más de 5 segundos y dos personas más de 2 segundos; para `min_faces=3`, tres personas en cuadro.
5. Pasar solo 1 segundo o girar la cabeza brevemente: no debe haber alerta ni captura. La red caída debe producir reintento, no pérdida silenciosa.
6. Confirmar que al terminar el examen la cámara se apaga, y que al cortar físicamente la cámara se muestra la opción Reintentar.

Anotar para cada evento: ID, tipo, pregunta, comienzo, duración, datos de umbral, path, HTTP Storage, foto visible por docente, resultado.

## TA-075 — identidad navegador

1. Con el estudiante autenticado y en sala de espera, abrir la cámara, registrar fotografía de referencia por `PUT` y revisar respuesta `POST /me/reference-face`.
2. Tomar otra fotografía actual y llamar a `identity/check`. `202` significa **pendiente**, nunca `verified` inmediato.
3. Esperar Realtime y confirmar cambio en estudiante y docente.
4. Repetir con lentes, poca luz, contraluz, y con persona distinta (uso autorizado). Si falla, el alumno **permanece** en sala; el docente conserva admisión manual.
5. Capturar evidencia de cada paso solo con autorización. No subir las fotos personales ni secretos al repositorio.

## TA-073/TA-074 — calibrar y medir visión

1. Grabar **al menos 3–4 voluntarios consentidos** con mirada normal a pantalla, mirada al teclado, mirada fuera, ausencia, dos/tres personas, lentes y contraluz.
2. Guardar clips **solo localmente**, crear `datasets/etiquetas/<id>.txt` con intervalos y añadir clips al manifiesto con `python tools/dataset.py registrar ...` (SHA-256 automático).
3. **Separar** de antemano un conjunto de prueba final sin ajustar umbrales. Ajustar `yaw_degrees` y `min_duration_ms` solo en la parte de calibración. Documentar cada intento.
4. Exportar CSV de predicciones en la página del spike, ejecutar `python tools/evaluate.py --predictions-dir datasets/predictions --split final_test` con el conjunto reservado y guardar `results/evaluation.json`.
5. Ejecutar `python tools/verificar_metricas.py results/evaluation.json`. Revisar accuracy ≥0.80 y FPR <0.20 para **cada detector**; si faltan muestras, la tarea no está cerrada.
6. Cuando exista evidencia suficiente, actualizar `DEFAULT_MODULE_SETTINGS` en `services/api/src/proctoring_api/domain/exam_session.py` mediante PR coordinado y repetir las pruebas API. **No cambiar el 25° / 3000 ms / 0.45 por intuición.**

## TA-065 — identidad real y métricas

1. Con fotos originales consentidas (pares genuinos e impostores), ejecutar el script `services/ai/spikes/face_verify.py` en CPU.
2. Revisar FAR, FRR, comparación genuino/impostor, P90 y condiciones inconclusas; incluir hashes y muestras en el reporte, no los rostros.
3. Verificar worker → descarga Storage → comparación → callback a API → Realtime docente; comprobar procesamiento fallido/reintentos.
4. **Pendiente decisión de arquitectura:** el servicio actual usa InsightFace, y eso no cumple la regla estricta de «únicamente API MediaPipe» para identidad. MediaPipe FaceLandmarker no ofrece un sistema completo de reconocimiento de identidad. No confundir una detección de rostro con una coincidencia de identidad.

## HU-025 — aviso compartido

1. Durante un giro largo debe aparecer **solo un aviso** (no cada 3 segundos) y no tapar el enunciado.
2. Segunda persona y cara ausente muestran textos específicos y no acusatorios.
3. Comprobar emisión de voz a la vez que giro de cabeza; el mismo componente debe mostrar el último aviso sin duplicar ventanas.
4. El botón **Entendido, continuar** cierra el aviso, pero nunca detiene el examen.

## Registro de pruebas

| Código | Entorno | Pasos ejecutados | Captura / log ID | Resultado real | Observaciones |
|---|---|---|---|---|---|
| TA-018 | Pendiente |  |  | No medido |  |
| TA-075 | Pendiente |  |  | No medido |  |
| TA-073 | Pendiente |  |  | No medido |  |
| TA-074 | Pendiente |  |  | No medido |  |
| TA-065 | Pendiente |  |  | No medido |  |
| HU-025 | Pendiente |  |  | No medido |  |
