# Grabaciones propias para cerrar SP-007

Estado: dos audios propios de P01 evaluados con base y small. Referencias confirmadas por el participante tras escucharlos. Por decisión del responsable, esta entrega utiliza únicamente estos dos audios. Las voces de P02, P03 y P04 quedan como ampliación posterior.

## Qué vamos a comprobar

Evaluar la transcripción en español con voces del equipo y comparar `base` con `small` usando WER y tiempo de inferencia. Es una prueba exploratoria, no entrenamiento ni evaluación de detección de fraude.

Alcance de esta entrega: dos audios de P01. La propuesta inicial de ocho audios, dos por integrante, queda como ampliación posterior; el backlog no exige un número para SP-007. Los sesenta audios corresponden a TA-006, otra tarea.

El informe actual se presenta con los dos audios de Pierreluiggi; las instrucciones siguientes se conservan para una futura ampliación con el grupo. Identificadores: P01 para Pierreluiggi; asignen P02, P03 y P04 a los otros participantes y mantengan esa asignación. Cada integrante debe aceptar el uso académico de su grabación; registraremos ese permiso al incorporar sus audios.

## Primer paso: grabar

1. Usa la grabadora de tu computadora o del celular. Guarda cada lectura como un archivo separado de aproximadamente quince a veinticinco segundos, hablando a tu ritmo normal.
2. No digas tu nombre, correo ni datos personales. Lee únicamente el texto correspondiente.
3. Para el audio 01, busca un lugar tranquilo. Para el 02, usa tu ambiente normal de estudio y anota si se escuchaba ventilador, conversaciones u otro ruido. No agregues ruido artificial ni música.
4. Conserva el archivo original en WAV, M4A, MP3 o MP4 con audio, sin filtros ni recortes. Mantén su extensión real: cambiar el nombre de M4A a WAV no convierte el audio.
5. Guarda los archivos dentro de `audio/` con el identificador del participante: `P01_01.m4a`, `P01_02.m4a`, etc. Sustituye `.m4a` por la extensión que produzca tu grabadora.

No hace falta pronunciar a velocidad exacta ni repetir hasta conseguir una grabación perfecta. Si cambias o repites alguna palabra, la referencia debe reflejar lo dicho.

## Texto para el audio 01

Durante un examen virtual, el estudiante puede leer una pregunta en voz alta para comprenderla mejor. El sistema debe distinguir esa lectura de una consulta a un asistente y conservar la evidencia para que el docente revise lo ocurrido.

## Texto para el audio 02

¿Cuál es la diferencia entre una clave primaria y una clave foránea en una base de datos? Explica cómo se relacionan dos tablas y menciona un ejemplo sencillo. Luego, señala por qué una contraseña no debe guardarse como texto visible.

## Segundo paso: referencia correcta

En `references/`, los dos TXT de P01 ya contienen las referencias completas confirmadas. Los TXT de P02, P03 y P04 siguen vacíos como plantillas para la ampliación posterior. Por ejemplo, a `audio/P01_01.m4a` le corresponde `references/P01_01.txt`.

Escuchen cada grabación y escriban exactamente las palabras que se oyen. Pueden partir del texto de lectura, pero deben corregirlo si hubo omisiones, cambios o repeticiones. Conserven las tildes y la ñ. Revisen el texto con otro integrante cuando sea posible, antes de consultar la salida de los modelos. No usen automáticamente la transcripción de Whisper como referencia de Whisper.

Si una palabra es imposible de entender, indíquenlo para revisar ese caso; no inventen una palabra ni añadan etiquetas como `[inaudible]` a la referencia que se utilizará para WER.

Los TXT vacíos son plantillas para la ampliación futura, no referencias aprobadas. Un audio hablado nunca se evaluará como si su referencia estuviera vacía.

## Qué avisar cuando estén listos

Indica qué archivos guardaste y, para cada participante: fecha de grabación, computadora o celular usado, condiciones de los dos audios y si acepta su uso en el proyecto. No necesitamos su nombre completo. Confirma también qué referencias escucharon y revisaron.

El manifiesto ya contiene los dos audios de P01, sus referencias, hashes y observaciones. El participante confirmó en esta conversación que leyó exactamente los textos después de escuchar sus grabaciones, antes de evaluar los modelos. Las notas sobre la pausa y el ventilador están conservadas en `provenance.json`. No se inventaron dispositivo ni fecha exacta de grabación. Los datos de los otros participantes quedan fuera del alcance de esta entrega.

## Tercer paso: evaluar con el código existente

Para repetir la evaluación con los dos audios originales disponibles, desde `services/ai`:

```console
uv run python -m spikes.evaluate datasets/sp007_own/manifest.csv --models base small --output results/evaluation-own-repeat.json
```

La primera ejecución está en `results/evaluation-own.json`. La salida `evaluation-own-repeat.json` conserva esa evidencia y los resultados públicos originales. Los tiempos pueden variar entre ejecuciones. La fecha de evaluación corresponde al procesamiento, no necesariamente al momento de grabación.

## Qué se conserva

Los audios y TXT auxiliares quedan fuera de Git. Las referencias de P01 ya están incluidas en el manifiesto, junto con los hashes; el informe y los resultados JSON constituyen evidencia versionable. Mantengan una copia privada de los audios originales para que el equipo pueda repetir la evaluación.

Si estas grabaciones se reutilizan en TA-006, deben mantener su identificación y marcarse como datos exploratorios usados para elegir el modelo, no presentarse después como una prueba final independiente.

## Resultados de P01

Evaluación: 03/10/2026 21:06 (America/Lima). Dos audios, 34,344 segundos y 79 palabras de referencia.

- base: 14 errores; WER 17,72 %; inferencia total 2,86 s.
- small: 6 errores; WER 7,59 %; inferencia total 6,12 s.

Se mantiene small como recomendación inicial por su menor WER en esta muestra y en la muestra pública anterior. No se midió aún similitud semántica, detección de fraude ni latencia del sistema completo. La evaluación es exploratoria: un hablante y una pasada por modelo. El detalle está en `docs/SP-007-own-results.md`.
