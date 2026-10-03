# Ejecutar SP-007: transcripción en español

Esta entrega es un experimento independiente. Todavía no es el servicio TA-007 conectado a la API, Redis o Supabase. La demostración muestra texto en la terminal y genera un JSON; no abre una interfaz gráfica.

## Preparación en otro equipo

Instale uv y use Python 3.12. Desde `services/ai`:

```console
uv sync --locked --python 3.12
uv run python -m spikes.download_sample --restore
uv run python -m spikes.demo
```

El repositorio conserva el manifiesto, las referencias y los hashes. `--restore` recupera exactamente los ocho audios registrados y verifica su SHA-256 sin reescribir el manifiesto ni la procedencia. Si ya están disponibles, solo los comprueba. Si encuentra un audio local modificado, se detiene y lo conserva.

El descargador recorre un archivo comprimido remoto; puede transferir hasta 582 MB aunque solo conserve ocho audios. La primera ejecución del modelo también requiere internet para descargar sus pesos. Los audios, los modelos y las herramientas locales permanecen fuera de Git.

Para seleccionar una muestra nueva, use otra carpeta; no sustituya el manifiesto de la evaluación original:

```console
uv run python -m spikes.download_sample --output datasets/otra_muestra --count 8
```

## Demo en Windows, Linux o macOS

Con los audios y el modelo ya descargados:

```console
uv run python -m spikes.demo --offline
```

En un entorno virtual ya instalado también puede ejecutar `python -m spikes.demo --offline`. La opción `--offline` evita descargas del modelo; no instala dependencias ni recupera audios faltantes.

La demo valida el manifiesto, muestra la referencia de la primera muestra, transcribe con `small` y guarda el resultado en `results/demo-local.json`. Así conserva `results/demo.json` y `results/evaluation.json` como evidencias de la ejecución original.

Alternativa `base` y audio propio con referencia UTF-8:

```console
uv run python -m spikes.demo --model base --offline
uv run python -m spikes.demo --audio muestra.wav --reference referencia.txt --output results/muestra.json
```

Sin `--reference`, un audio propio devuelve transcripción y tiempos, pero no WER. No hay captura de micrófono ni envío de audios a un proveedor: la inferencia es local.

## Acceso desde PowerShell

Desde `services/ai` se mantiene el comando existente:

```powershell
.\demo.ps1 -Offline
.\demo.ps1 -Model base -Offline
.\demo.ps1 -Audio 'C:\ruta\mi-audio.wav'
```

El script llama a la misma demo en Python y utiliza `.venv/Scripts/python.exe`. En este equipo hay además una copia local de uv en `.tools/bin/uv.exe`.

## Repetir la comparación

```console
uv run python -m spikes.evaluate datasets/mediaspeech_es/manifest.csv --models base small --output results/evaluation-local.json
```

El nombre de salida distinto conserva los números originales. Una nueva ejecución tendrá otros tiempos. Para reproducir el control de silencio, consulte `datasets/controls/README.md`.

Los tiempos de inferencia incluyen decodificación, VAD e iteración completa de los segmentos. Excluyen carga del modelo, escritura del JSON y cálculo posterior de WER. Una pasada no mide estabilidad ni concurrencia; el primer audio puede incluir calentamiento.

## Verificación

Los comandos del CI del servicio son:

```console
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Las 24 pruebas actuales usan dobles y evidencias de texto; no descargan modelos ni necesitan los audios. Incluyen restauración con hashes, demo portable y recálculo de WER a partir de las transcripciones registradas.

En la revisión local del 03/10/2026 pasaron las pruebas, lint y formato. La comprobación de tipos de SP-007 (`uv run mypy spikes tests`) pasó; `mypy .` sigue señalando las dependencias ausentes `redis` y `rq` de `worker_stub.py`. Su incorporación y la adaptación del Dockerfile corresponden al compañero encargado de esa integración.

## Cómo presentar el avance

1. Mostrar el audio, su referencia y la procedencia pública.
2. Ejecutar la demo y abrir `results/demo-local.json`: texto, segmentos, WER y tiempos.
3. Mostrar `results/evaluation.json`: ocho audios, 116 segundos y 318 palabras de referencia; WER de 21,70 % con `base` y 16,04 % con `small`.
4. Explicar que WER mide errores de palabras, no exactitud de detección de fraude.
5. Indicar que siguen pendientes las grabaciones propias de TA-006 y la integración, similitud semántica y clasificación de voz sintética de TA-007.

## Fuentes del experimento

- SYSTRAN, faster-whisper: https://github.com/SYSTRAN/faster-whisper
- MediaSpeech, datos y licencia: https://openslr.org/108/
- NTRLab, método y procedencia: https://github.com/NTRLab/MediaSpeech
