# Jesús Limay — Cierre de visión (TA-083, calibración, métricas y capturas)

**Base del paquete:** `Jesus_Limay_Semana_07_Proyecto_Completo.zip` aportado en la conversación. **No es una exportación certificada de la rama remota `develop` del 16/10**: antes de fusionar, comparar con `develop` actualizado. No reemplazar carpetas completas de otros integrantes ni `package.json`.

## 1. TA-083: cámara durante el examen

Se **reutiliza** el `MediaStream` de `useSupervision.ts` para inferencias y transmisión de monitoreo. Se observa la pista `ended` y se agrega un sondeo muy económico, cada 1 segundo, para advertir si:

- la pista dejó de estar activa;
- el reloj de video no avanza durante unos 4 segundos;
- la imagen capturada en una cuadrícula de 16 × 12 permanece casi negra durante unos 4 segundos.

La comprobación se hace en memoria y **no guarda las muestras de diagnóstico**. Baja iluminación, cámara tapada y flujo congelado son posibilidades, **no son evidencia de trampa**. Se muestra un mensaje de reintento con el **mismo componente de avisos** que utilizan las detecciones; nunca se expulsa automáticamente al estudiante. Los detectores dejan de analizar imágenes cuando la cámara se considera no disponible.

Se agregó estado por el **canal privado existente** de `monitoreo.ts` (`camera_status: active | interrupted | no_image`), propagado por presencia y broadcast. `CamaraEnVivo.tsx` lo muestra en la cuadrícula del docente, incluso si este se une después de la interrupción, cuando la presencia aún existe.

**Límite de alcance:** la señal de estado de cámara es **en vivo, no histórica**; todavía no es un evento persistido por la API. El panel que no monta `CamaraEnVivo` no observa el broadcast. Hace falta acordar con Héctor si se incorpora al contrato de eventos y migraciones una interrupción de cámara persistente. No se ha alterado el enum de eventos ni simulado un `face_absent` causado por hardware.

## 2. Calibración antes de rendir

`CalibracionMirada.tsx` añade un bloque **opcional** en `SalaDeEspera` para sesiones con módulo `gaze` y estudiante admitido. Con consentimiento previo, el alumno registra **cinco posiciones** (centro y cuatro esquinas); solo se almacenan ángulos aproximados de cabeza, **nunca imagen ni embeddings**. Si hay cero o varios rostros, la toma se rechaza.

`calibration.ts` conserva la calibración por pareja `(sessionId, studentId)` en `sessionStorage`, con caducidad de 24 h. En `RendirExamen.tsx` se aplica el centro como referencia y un umbral exploratorio limitado a 45° sin rebajar el mínimo establecido por el docente. En cada evento se registra `yaw_deg`, `yaw_baseline_deg`, `threshold_deg` y `calibration_status`. Cuando no se calibra, el detector usa el umbral predeterminado y `calibration_status: default`.

**Límites:** no es una calibración de seguimiento ocular (MediaPipe estima **orientación de cabeza**); se propone un umbral heurístico, pendiente de validar experimentalmente. `sessionStorage` **no sincroniza entre dispositivos** y puede perderse al cerrar sesión o borrar datos; guardarlo en Supabase exige una decisión de esquema/API y una migración nueva. Probar al menos dos personas y dos pantallas.

## 3. Objetivo SMART: accuracy, FPR y FNR

`tools/evaluate.py` informa matriz de confusión y calcula:

- `accuracy = (TP + TN) / (TP + TN + FP + FN)`;
- `FPR = FP / (FP + TN)`;
- `FNR = FN / (FN + TP)`.

Una tasa no calculable aparece como `null`, **nunca como 0 inventado**. `verificar_metricas.py` rechaza reportes sin FNR, muestras o `final_test` y exige accuracy ≥ 0.8 y FPR < 0.2 para aprobar. FNR se reporta, no se le asignó arbitrariamente una meta propia.

**NO HAY RESULTADOS EXPERIMENTALES NUEVOS:** el `manifest.csv` del ZIP base solo tiene el encabezado; no se adjuntaron videos consentidos ni predicciones del detector. El script Python se probó con conteos ficticios **únicamente para comprobar la fórmula**; esto no equivale a una evaluación de rendimiento.

## 4. Capturas TA-018

Se conserva el flujo ya implementado: `CapturasPorCondicion` → `capturarFotograma` (una imagen al cumplirse la duración, no por fotograma) → `imageUpload.ts` con URL firmada y PUT → `emisor.ts` con `evidence_path` → revisión del docente. **No se afirma que esa cadena haya sido vista de extremo a extremo en Supabase real**. Falta probar que el docente abre la imagen y guardar capturas de pantalla de la prueba.

## 5. Verificación manual que falta (web y Electron)

1. Actualizar `develop`; configurar entorno de pruebas Supabase, Redis y API; iniciar frontend y escritorio. Usar **cuentas autorizadas de prueba**, sin compartir secretos.
2. En la sala de espera, consentir, registrar referencia y solicitar verificación de identidad. Repetir con lentes, luz deficiente y contraluz. Si falla, el estudiante **espera la revisión docente**.
3. En un examen con `gaze` y `live_monitoring`, realizar la calibración (centro y esquinas); confirmar que el metadata incluye umbral, centro y estado calibrado.
4. Abrir el monitoreo docente; desenchufar la webcam USB a mitad del examen. Comprobar mensaje de reintento en el alumno, estado de cámara interrumpida en docente y recuperación al reconectar. Repetir en navegador y Electron.
5. Repetir con cámara tapada o fondo completamente oscuro durante más de 4 s; verificar **advertencia técnica**, no acusación, y no producir falsas capturas de conducta.
6. Generar `gaze_away`, `face_absent` y `extra_person` con una persona adicional **consentida**; confirmar un solo evento por episodio, una captura, `evidence_path` y apertura en revisión del docente.
7. Etiquetar clips de diferentes personas/condiciones. Separar calibración de prueba final, exportar predicciones, ejecutar evaluador y guardar `results/evaluation.json` auténtico.
8. Cerrar Electron inesperadamente durante una prueba controlada. Comprobar si el docente ve desconexión y si se recuperan las respuestas. El cierre abrupto y un evento histórico de interrupción **no están garantizados** por este paquete.

## 6. Validaciones locales realizadas aquí

- Revisión estática ESLint de los archivos afectados: sin errores reportados.
- TypeScript del proyecto: sin errores en los cambios usando *declaraciones temporales* para dos dependencias que no venían instaladas en el ZIP (NO son un build real con MediaPipe).
- Cinco pruebas `unittest` de los evaluadores Python: aprobadas.
- Cinco verificaciones funcionales de clases puras de cámara/calibración con Node: aprobadas.
- **No fue posible ejecutar Vitest / Vite build**: faltan binarios nativos Linux de Rollup en la instalación Windows incluida y los paquetes MediaPipe/VAD. Ejecutar en Windows `npm ci`, `npm run lint`, `npx tsc --noEmit`, `npm test`, `npm run build`.
- No se ejecutaron pruebas de cámara física, autenticación, Storage ni Supabase Realtime en este entorno.

## 7. Archivos técnicos principales

| Archivo | Papel |
| --- | --- |
| `apps/web/src/supervision/cameraHealth.ts` | Detección no incriminatoria de pista finalizada, reloj detenido o oscuridad prolongada |
| `apps/web/src/supervision/useSupervision.ts` | Integra diagnóstico en el bucle de supervisión y reutiliza avisos y reintento |
| `apps/web/src/supervision/monitoreo.ts` | Estado de cámara por canal privado Realtime, sin video histórico |
| `apps/web/src/components/CamaraEnVivo.tsx` | Etiqueta de fallo técnico para docente |
| `apps/web/src/components/CalibracionMirada.tsx` | Interfaz opcional de cinco puntos |
| `apps/web/src/supervision/calibration.ts` | Cálculo, guardado local y validación de calibración |
| `apps/web/src/pages/SalaDeEspera.tsx` | Muestra calibración antes del examen |
| `apps/web/src/pages/RendirExamen.tsx` | Ajustes efectivos de detector y estado de calibración |
| `apps/web/src/supervision/detectores/vision.ts` | Calibración de orientación y metadata |
| `apps/web/spikes/vision/tools/evaluate.py` | Métricas accuracy, FPR, FNR |
| `apps/web/spikes/vision/tools/verificar_metricas.py` | Verificador estricto de resultados experimentales finales |

**Privacidad:** no almacenar video continuo ni rostros de participantes en Git. **Regla del sistema:** el docente decide con justificación, no los detectores.
