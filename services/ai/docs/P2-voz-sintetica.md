# Semana 6 · P2 · Detector de voz sintética

Responsable: Pierreluiggi. Plan: 8 h estimadas; no horas reales certificadas.
Rama: `feat/SPEC-008-voz-sintetica`. Estado: implementación experimental, pendiente
de dataset real y evaluación de los modelos completos.

## Código y decisiones

`spikes/synthetic_voice.py` compara embeddings congelados de XLS-R 300M con
regresión logística frente a AASIST preentrenado, sin reentrenar AASIST. El
escalador y la regresión usan únicamente train. Se elige el umbral con calibration
y se informa EER interpolada, accuracy, FPR/FNR y conteos sobre test.

El reporte separa el motor reservado y las condiciones clean, speaker_mic y
mixed. Si una condición no tiene ambas clases, no se inventa un FPR: se informa
que faltan datos. Se comprueban duplicados, hashes y fugas de hablante, texto y
audio fuente. La partición debe fijarse ANTES de entrenar.

PyAV convierte a mono/16 kHz; se aceptan segmentos de 0.1 a 30 s. XLS-R promedia
los embeddings temporales de cada audio sin padding. AASIST usa ventanas de
64600 muestras y repetición para completar fragmentos cortos; se promedian las
puntuaciones sintéticas de todas las ventanas. Esta agregación es una decisión
experimental propia, que debe compararse con grabaciones mixtas reales.

AASIST original usa etiqueta 0 para spoof y 1 para voz real. Se toma softmax de
la clase 0 como score sintético, sin asumir que sea una probabilidad calibrada.
Los pesos se leen con `weights_only=True`. Solo cargar código oficial revisado.
No existe detector de segunda voz/diarización en esta entrega.

`tests/test_synthetic_voice.py` prueba métricas conocidas, empates, valores
inválidos y fugas de particiones. Esas puntuaciones artificiales son fixtures de
prueba, no evidencia de rendimiento sobre voces.

## Preparación del dataset

1. Obtener Common Voice español desde Mozilla Data Collective con cuenta y
   condiciones de acceso correspondientes. No se descargó ni aceptó condiciones
   en nombre del usuario. Registrar versión, licencia y procedencia de cada audio.
2. Grabar voces del equipo con consentimiento escrito y códigos anónimos. Usar
   voces diferentes para train, calibration y test si se quiere medir generalización.
3. Generar voces con Piper y edge-tts para desarrollo. Reservar XTTS exclusivamente
   para test; no usarlo para elegir modelo, hiperparámetros o umbral. Una voz de
   referencia para XTTS requiere autorización del dueño para esa síntesis.
4. Grabar TTS por parlante con el micrófono del examen. Incluir mezcla con voz
   humana, distintas distancias y ruido. Reproducir también voces humanas por el
   parlante: evita que el modelo confunda canal de reproducción con voz sintética.
5. Mantener todos los derivados de un audio, persona y texto en la misma partición.
   Varias grabaciones del mismo archivo no son muestras independientes.

Objetivo práctico inicial: al menos 120 segmentos balanceados, con 60 train,
30 calibration y 30 test. Es una propuesta de diseño, no una cifra ya recolectada
ni un requisito textual del backlog. En test debe haber suficientes reales para
que FPR tenga sentido y suficientes XTTS para informar el motor no visto.
Si no se logra, reportar el tamaño real y la incertidumbre; no duplicar audios.

## Formato de manifiesto

Crear `datasets/p2_voice/manifest.csv` con estas columnas:

```text
sample_id,audio_path,sha256,label,engine,split,speaker_id,source_id,text_id,condition,source,license,consent_id
```

En mezclas, listar TODOS los hablantes y fuentes separados por `|`; no asignar
un identificador nuevo que oculte componentes usados en otra partición.

`label`: real/synthetic. `engine`: human/piper/edge/xtts. `split`:
train/calibration/test. `condition`: clean/speaker_mic/mixed. `source_id` agrupa
el audio original y sus derivados; text_id agrupa el mismo texto. Para muestras
públicas, consent_id puede ser la referencia de autorización/licencia pública,
nunca un consentimiento personal inventado. Guardar ambiente, equipos, versiones
TTS y condiciones de generación en `provenance.json`.

No subir audios, modelos, consentimientos firmados ni voces de referencia a Git.
El manifiesto, procedencia y resultados sí se versionan.

## Ejecución

Desde `services/ai`, instalar `uv sync --locked --extra voice`. Obtener el código,
configuración y pesos del repositorio oficial AASIST, fijando su commit; guardar
fuera del repositorio o dentro de `models/` (ignorado). No usar un archivo de
modelo enviado por una fuente desconocida.

```powershell
uv run --extra voice python -m spikes.synthetic_voice datasets/p2_voice/manifest.csv --held-out-engine xtts --xlsr-revision 1a640f32ac3e39899438a2931f9924c02f080a54 --aasist-source models/aasist/models/AASIST.py --aasist-config models/aasist/config/AASIST.conf --aasist-weights models/aasist/models/weights/AASIST.pth --output results/synthetic_voice_01.json
```

La carga de XLS-R y AASIST y su inferencia se verificaron con un tono artificial,
sin atribuirle valor como evaluación de voces. El dataset sigue pendiente. Los
modelos grandes pueden consumir bastante memoria y exceder el presupuesto de
latencia; esa medición es parte del experimento, no una garantía del código.

## Fuentes consultadas el 08/10/2026

- https://huggingface.co/facebook/wav2vec2-xls-r-300m
  Para identificar el extractor multilingüe y fijar revisión exacta.
- https://github.com/clovaai/aasist
  Implementación y pesos oficiales; se revisaron `data_utils.py`, `main.py`,
  `models/AASIST.py` y `config/AASIST.conf` para entrada y orientación del score.
- https://github.com/OHF-Voice/piper1-gpl
  Motor local candidato. Registrar licencia del motor y de la voz elegida.
- https://github.com/rany2/edge-tts
  Motor candidato que utiliza un servicio remoto; no requiere clonar voces propias.
- https://huggingface.co/coqui/XTTS-v2
  Tercer motor propuesto, reservado para prueba final. Revisar licencia y permiso
  de la voz de referencia antes de generar.
- https://mozilladatacollective.com/
  Canal actual de acceso a datos públicos; queda pendiente obtener español.

## Límite de interpretación

Un motor no visto significa no usado en nuestro entrenamiento/calibración. No
podemos garantizar que sea ajeno al preentrenamiento de modelos de terceros.
Detectar contenido sintético tampoco demuestra consulta a IA ni una segunda voz:
la regla de alerta corresponde a la API y necesita evidencia del escenario real.
