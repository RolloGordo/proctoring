# Registro y preparación del dataset de audio

Estado al 03/10/2026: se evaluaron ocho audios públicos de MediaSpeech, un control de silencio digital y dos audios propios de P01. TA-006, el conjunto de sesenta audios del proyecto, sigue pendiente.

La colección `datasets/sp007_own` ya contiene dos grabaciones originales de P01, con 34,344 segundos y 79 palabras de referencia. Los textos fueron confirmados por el participante tras escuchar las grabaciones, antes de evaluar. La salida es `results/evaluation-own.json`. La entrega actual se limita a estos dos audios por decisión del responsable. La propuesta inicial de ocho audios queda como ampliación posterior; esa cantidad no es una exigencia del backlog. Esta muestra no completa TA-006.

## Muestra utilizada en SP-007

- Fuente: MediaSpeech, OpenSLR 108, https://openslr.org/108/.
- Procedencia y atribución: Kolobov et al. (2021); archivo oficial `ES.tgz`. La URL, licencia y transformaciones se registran en `datasets/mediaspeech_es/provenance.json`.
- Licencia registrada: CC BY 4.0.
- Selección: primeros ocho archivos FLAC en el orden del archivo comprimido; no es una muestra aleatoria.
- Duración evaluada: 116 segundos. Referencias: 318 palabras tras la normalización del cálculo de WER.
- Transformación: subconjunto sin edición de audio; solo se recortaron espacios en los extremos de los textos de referencia.
- Limitaciones: habla de medios, no exámenes de estudiantes. No se verificó independencia por hablante. No contiene etiquetas de fraude ni valida un detector de voz sintética.

El CSV conserva identificador, ruta relativa, transcripción de referencia, SHA-256, fuente, licencia y partición `exploratory`. Las referencias proceden del dataset; no se afirma que el equipo las haya revisado manualmente.

## Archivos conservados en Git

`datasets/mediaspeech_es/manifest.csv` y `provenance.json` permiten identificar y recuperar la muestra. `results/evaluation.json`, `demo.json` y `silence.json` conservan las mediciones originales y las transcripciones obtenidas.

Los audios, sus TXT auxiliares, los modelos y las herramientas locales quedan fuera de Git. Las referencias necesarias ya están en el CSV. La regla de atributos preserva los bytes del manifiesto para mantener válido su hash entre Windows y Linux.

Desde `services/ai`, después de instalar las dependencias:

```console
uv run python -m spikes.download_sample --restore
```

El comando verifica audios existentes y recupera los que faltan desde la fuente original. Rechaza un hash distinto y no modifica el manifiesto ni la procedencia. Puede transferir hasta 582 MB al recorrer el archivo remoto; la recuperación depende de que la fuente siga disponible.

## Control de silencio

Se generó un WAV de tres segundos, mono, PCM de 16 bits y 16 kHz, con muestras de valor cero. Su receta y SHA-256 se conservan en `datasets/controls/README.md`.

Con `base` y VAD, la ejecución registrada produjo texto vacío. WER es nulo porque no hay palabras de referencia. Este control no representa ruido de aula ni demuestra comportamiento ante todos los silencios reales.

## Dataset propio pendiente: TA-006

El backlog requiere al menos 60 audios etiquetados: lecturas, consultas a un asistente con respuesta sintética y silencios. La muestra pública y el control no completan ese requisito.

Para cada grabación propia registrar identificador, ruta relativa, procedencia, fecha, autorización o licencia, hablante anónimo, idioma, duración, formato, frecuencia, escenario, pregunta, referencia revisada, etiqueta humana/sintética/desconocida y partición. Para voz sintética, incluir herramienta, modelo, versión disponible y condiciones de uso.

Separar entrenamiento, validación y prueba; evitar que el mismo audio o sus variantes aparezcan en varias particiones. Procurar separación por hablante. Ajustar umbrales con validación y reservar la prueba para evaluación final. No incluir nombres personales ni credenciales en las evidencias versionadas.

La evaluación futura debe comprobar similitud semántica y voz sintética por separado de WER. Una transcripción parecida a la pregunta, por sí sola, no justifica una alerta.
