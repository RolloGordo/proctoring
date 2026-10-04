# Informe de desarrollo del módulo de audio

Responsable: Zevallos Bocanegra Piereluiggi (rzecvallosb1@upao.edu.pe).
Fecha: 03/10/2026.
Tarea: SP-007, prueba de transcripción de voz en español.
Rama: `feat/SP-007-spanish-transcription`.

## Objetivo y estado actual

Se implementó y ejecutó una prueba local que recibe audio en español, produce transcripciones y mide WER y tiempos. Este avance permite demostrar transcripción funcional. No implementa todavía detección de fraude, clasificación de voz sintética ni el servicio TA-007.

La rama está actualizada desde `develop` hasta `bb265d3`, con los cambios integrados del equipo, incluidos `tasks.py`, `worker_stub.py`, las dependencias de la cola y el CI. La recomendación antigua de esperar esa base ya está satisfecha. Las correcciones de esta revisión se limitan a `services/ai/`.

## Archivos y motivos

- `pyproject.toml` y `uv.lock`: entorno Python 3.12 y dependencias reproducibles. Se fijó PyAV 16.1.0 por incompatibilidad observada de la versión 19 con faster-whisper. La excepción de mypy para `faster_whisper` reconoce que esa biblioteca no publica tipos; las comprobaciones del código propio siguen activas.
- `spikes/transcribe.py`: inferencia local con faster-whisper, CPU/int8, cuatro hilos, idioma español, VAD y beam size 5. Consume todo el generador de segmentos antes de detener el cronómetro; separa carga del modelo e inferencia.
- `spikes/metrics.py`: WER por distancia de edición entre palabras. Normaliza mayúsculas, puntuación, espacios y Unicode NFC, conservando tildes y ñ. Una referencia vacía produce WER nulo.
- `spikes/evaluate.py`: valida rutas, identificadores y hashes del manifiesto; evalúa cada modelo y agrega errores sobre el total de palabras. Guarda configuración, entorno, segmentos y métricas.
- `spikes/network.py`: usa los certificados del sistema para descargar modelos con TLS verificado.
- `spikes/download_sample.py`: selecciona ocho audios de MediaSpeech. La nueva opción `--restore` descarga exactamente los audios del manifiesto versionado, verifica sus hashes y conserva los metadatos originales. Sin ella, una copia nueva con manifiesto pero sin audios no podía prepararse.
- `spikes/demo.py`: nueva entrada portable para la demostración. Obtiene la referencia del CSV sin depender de archivos TXT ignorados y escribe por defecto `results/demo-local.json`.
- `demo.ps1`: acceso cómodo desde Windows; ahora delega la ejecución a la misma demo Python.
- `.gitignore`: permite versionar JSON de resultados, manifiestos CSV, procedencia JSON y README de datasets. Mantiene fuera los audios, modelos y herramientas. Se permiten los directorios intermedios para que las excepciones de Git funcionen.
- `.gitattributes`: conserva los bytes de los manifiestos CSV. El informe original contiene el SHA-256 del CSV con finales de línea CRLF; normalizarlo a LF al subirlo alteraría ese hash.
- `datasets/mediaspeech_es/manifest.csv` y `provenance.json`: identificadores, referencias, hashes, fuente, licencia y criterio de selección de la muestra medida.
- `datasets/controls/README.md`: receta exacta para regenerar el control de silencio y verificar su hash.
- `results/evaluation.json`, `demo.json` y `silence.json`: resultados reales originales, ahora visibles para Git. No se sustituyeron por nuevas mediciones.
- `tests/test_spike.py`: trece pruebas originales de métricas, validación de entradas y consumo completo del generador.
- `tests/test_reproducibility.py`: once pruebas adicionales para la demo, recuperación verificada de audios y consistencia de las evidencias. No requieren descargas ni modelos.
- `docs/`: guía de reproducción, registro del dataset e informe actualizado de implementación.
- `README.md`: solo se ajustó el formato de dos ejemplos Python para que pasen el formateador actual. Se conservó el contenido del compañero.
- Se eliminó `spikes/.gitkeep`, innecesario porque la carpeta ya contiene código.

## Evidencias reales

La muestra exploratoria pública contiene ocho audios, 116 segundos y 318 palabras de referencia.

- `base`: 69 errores de palabra; WER 21,70 %; inferencia total 9,01 segundos; factor de tiempo real 0,078.
- `small`: 51 errores de palabra; WER 16,04 %; inferencia total 27,16 segundos; factor de tiempo real 0,234.
- Control de tres segundos de silencio con `base`: transcripción vacía, cero palabras insertadas y WER nulo.

Son mediciones de una pasada local, registradas con faster-whisper 1.2.1, CTranslate2 4.8.2, Python 3.12.15 y Windows 11. El entorno concreto y la configuración figuran en los JSON.

Aplicar el factor agregado de `small` a diez segundos de audio da aproximadamente 2,34 segundos de inferencia. Es una estimación para orientar la elección del modelo; no demuestra que el sistema completo cumpla el presupuesto de diez segundos. Faltan transferencia, colas, similitud, clasificación, carga, concurrencia y variabilidad.

La recomendación inicial es continuar evaluando `small`. No se ha medido todavía si los errores de transcripción preservan la similitud semántica necesaria para el caso de uso.

## Verificación de las correcciones

- Las 24 pruebas locales pasan, incluidas las trece originales.
- Lint y formato del servicio pasan.
- La comprobación de tipos de todo el servicio (`mypy .`) pasa después de instalar las dependencias `rq` y `redis` que el compañero incorporó a `pyproject.toml` y `uv.lock`.
- Los tests verifican que el hash del manifiesto coincide con el registrado, que cada referencia y hash de audio coincide con la evaluación y que el WER se puede recalcular desde las transcripciones guardadas.
- Los tests de descarga utilizan archivos TAR en memoria: prueban recuperación correcta, rechazo de audio modificado, conservación de metadatos y entradas ausentes o con rutas distintas.

Los comandos y requisitos para repetir las comprobaciones están en `SP-007-guide.md`. Estas verificaciones locales no equivalen a un CI remoto aprobado.

## Pendientes y coordinación

TA-006 sigue pendiente: los dos audios propios de SP-007 todavía no completan el conjunto de sesenta audios con escenarios y etiquetas requerido por el backlog. La muestra pública no representa estudiantes de UPAO ni permite evaluar fraude.

TA-007 consiste en implementar el servicio que detecta fragmentos de habla, los transcribe en español y guarda texto y hora. La similitud con la pregunta corresponde a TA-009; el clasificador de voz sintética, a TA-010. La lectura legítima de la pregunta no debe generar por sí sola una alerta.

El compañero ya incorporó `rq` y `redis`; se sincronizó el entorno local con `uv.lock` para validar el servicio. La unificación del Dockerfile y la verificación con Supabase real corresponden al compañero que las asumió. No se modificaron esos componentes ni `services/api/`.

Antes de abordar foco de ventana, aclarar la discrepancia entre la asignación de HU-008 del CSV y la responsabilidad de Electron indicada en CLAUDE.md.

## Preparación de las grabaciones propias de SP-007

El backlog pide probar con audios propios en español. Se preparó `datasets/sp007_own/README.md` con el protocolo y dos textos de lectura, `audio/` para los originales, ocho TXT vacíos en `references/`, un manifiesto con cabecera y `provenance.json` con estado pendiente. La propuesta inicial era recoger dos audios por integrante, sin atribuir esa cantidad al backlog; se acordó presentar primero los dos audios de P01.

Después de esta preparación se recibieron y evaluaron dos audios originales de P01 (34,344 s). El participante escuchó ambos y confirmó que los textos leídos coinciden exactamente con la guía, antes de ejecutar los modelos. Se completaron las referencias y el manifiesto y se guardó la evaluación en `results/evaluation-own.json`, conservando las observaciones de pausa y ventilador en la procedencia. Base obtuvo WER 17,72 % y small 7,59 %. El detalle está en `docs/SP-007-own-results.md`. La evaluación experimental queda completada para el alcance actual de dos audios propios de P01. Las voces de los otros participantes quedan como ampliación posterior. La integración definitiva requiere la revisión del equipo y comprobar el CI remoto.

No se modificó el código de transcripción ni de evaluación para preparar y procesar estos audios propios. Se verificaron hashes, referencias y recálculo de métricas sobre los resultados reales.
