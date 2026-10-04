# Evaluación de audios propios de SP-007

Responsable: Zevallos Bocanegra Piereluiggi.
Evaluación: 03/10/2026 21:06 (America/Lima).
Estado: evaluación experimental completada para el alcance actual de dos audios propios de P01; ampliación grupal posterior.

## Resultado y recomendación

Se mantiene `small` como modelo recomendado para continuar la implementación: obtuvo menos errores que `base` en los mismos dos audios de P01. El tiempo de inferencia aumentó, pero siguió siendo inferior a la duración total de esos audios en este equipo. La muestra pública anterior también favoreció a `small` (WER 16,04 % frente a 21,70 %). Ambas muestras se informan por separado.

- `base`: 14 errores / 79 palabras; WER **17,72 %**; inferencia total **2,86 s**; factor de tiempo real 0,083. Carga del modelo: 2,73 s, medida por separado.
- `small`: 6 errores / 79 palabras; WER **7,59 %**; inferencia total **6,12 s**; factor de tiempo real 0,178. Carga del modelo: 1,75 s, medida por separado.

WER es el número de sustituciones, inserciones y omisiones dividido entre las palabras de referencia. Menor es mejor. No representa exactitud de detección de fraude.

## Datos y referencias

Se utilizaron dos MP4 originales, sin edición, de un participante: P01_01, de 16,660 segundos, y P01_02, de 17,684 segundos. Total: 34,344 segundos y 79 palabras tras la normalización de WER.

El usuario escuchó las grabaciones y confirmó que pronunció exactamente los dos textos de la guía, antes de ejecutar la comparación. Con esa confirmación se completaron los TXT y el manifiesto. Las referencias no se generaron a partir de la salida de los modelos; no se afirma que otro oyente las haya verificado.

Las notas originales del usuario se conservaron aparte: una pausa en «comprenderla» en P01_01 y ruido semejante a un ventilador en P01_02. No se trataron esas observaciones como palabras pronunciadas. No se proporcionaron el dispositivo ni el momento exacto de grabación.

## Configuración y medición

Se usó el código existente `spikes.evaluate`, con modelos descargados y `HF_HUB_OFFLINE=1`, CPU/int8, cuatro hilos, idioma español, VAD activado, beam size 5 y `condition_on_previous_text=false`. Una pasada por modelo, en orden base y small.

El tiempo de inferencia incluye decodificación, VAD y consumo completo de segmentos. La carga del modelo se registra por separado y no debe sumarse una vez por audio, porque cada modelo se carga una sola vez. No se midieron colas, red, concurrencia, similitud ni clasificación de voz sintética.

## Resultado por audio

- P01_01 con `base`: 10 errores / 39 palabras; WER 25,64 %; inferencia 1,64 s.

- P01_02 con `base`: 4 errores / 40 palabras; WER 10,00 %; inferencia 1,22 s.

- P01_01 con `small`: 3 errores / 39 palabras; WER 7,69 %; inferencia 3,01 s.

- P01_02 con `small`: 3 errores / 40 palabras; WER 7,50 %; inferencia 3,11 s.

## Transcripciones conservadas

### P01_01

**Referencia confirmada**

Durante un examen virtual, el estudiante puede leer una pregunta en voz alta para comprenderla mejor. El sistema debe distinguir esa lectura de una consulta a un asistente y conservar la evidencia para que el docente revise lo ocurrido.

**Salida de base**

Durante un examen virtual, el estudiante puede leer una pregunta en voz alta para comprenderla mejor. El sistema de vez distinguir esa lectura de una consulta a un existente y conservarla evidencia para aquí, docente, reviselo, ocurrir.

**Salida de small**

Durante un examen virtual, el estudiante puede leer una pregunta en voz alta para comprenderla mejor. El sistema debe distinguir esa lectura de una consulta a un existente y conservar la evidencia para que docente revise el ocurrido.

### P01_02

**Referencia confirmada**

¿Cuál es la diferencia entre una clave primaria y una clave foránea en una base de datos? Explica cómo se relacionan dos tablas y menciona un ejemplo sencillo. Luego, señala por qué una contraseña no debe guardarse como texto visible.

**Salida de base**

¿Cuál es la diferencia entre una clave primaria y una clave forana en una base de datos? Explica cómo se relacionan dos talgas y mencionan un ejemplo sencillo. Luego señala por qué una contracenión no debe guardarse como texto visible.

**Salida de small**

¿Cuál es la diferencia entre una clave primaria y una clave forana y una base de datos? Explica cómo se relacionan dos talgas y menciona un ejemplo sencillo. Luego señala por qué una contraseña no debe guardarse como texto visible.

## Archivos actualizados y su finalidad

- `datasets/sp007_own/references/P01_01.txt` y `P01_02.txt`: texto completo confirmado de cada grabación; permanecen fuera de Git como auxiliares.
- `datasets/sp007_own/manifest.csv`: contiene las referencias versionables, rutas, hashes, participante y notas, y permite validar los archivos antes de evaluar.
- `datasets/sp007_own/provenance.json`: conserva confirmación de referencias, observaciones originales, alcance y estado de la colección.
- `results/evaluation-own.json`: salida original completa, con configuración, entorno, segmentos, tiempos y WER.
- `datasets/sp007_own/README.md` y `docs/`: instrucciones y resultados actualizados.

Los audios originales siguen excluidos de Git. No se modificó el código del evaluador ni del transcriptor.

## Reproducción y comprobaciones

Desde `services/ai`, con los MP4 originales en su carpeta y las dependencias instaladas:

```console
uv run python -m spikes.evaluate datasets/sp007_own/manifest.csv --models base small --output results/evaluation-own-repeat.json
```

La ejecución original usó los modelos locales, con `HF_HUB_OFFLINE=1`; para repetirla sin red puede establecerse esa variable en la terminal. El nombre de salida distinto conserva la primera medición. Los hashes y el texto de cada referencia coinciden entre el manifiesto y los resultados. Se recalcularon WER y resúmenes desde las transcripciones para comprobar los valores guardados.

## Límites y trabajo pendiente

Esta es evidencia exploratoria con una sola voz y lecturas guiadas; no permite generalizar a otros hablantes o estimar robustez al ruido. El segundo audio tiene otro texto además del ruido informado, por lo que no aísla el efecto del ventilador.

Ya hay medición de WER con audios propios, resultados documentados y recomendación de modelo. Por decisión del responsable, esta entrega se presenta con los dos audios propios de P01. Las voces de P02, P03 y P04 quedan como ampliación posterior; los ocho audios inicialmente propuestos no son un requisito del backlog de SP-007. La integración definitiva requiere revisión del equipo y comprobar el CI remoto. Tras actualizar desde `develop` se instalaron las dependencias del worker que incorporó el compañero: las 24 pruebas y las comprobaciones locales de lint, formato y tipos del servicio pasan. TA-006 y TA-007 siguen siendo tareas separadas.
