# Ejecutar la primera prueba de audio

Esta entrega implementa SP-007 como experimento independiente. No es todavía el servicio TA-007 conectado a la API, Redis o Supabase.

## Demostración en este equipo

Abra en VS Code una terminal PowerShell en services/ai y ejecute:

```powershell
.\demo.ps1
```

El script muestra la referencia de la primera muestra pública, transcribe el audio con small y guarda texto, segmentos, WER y tiempos en results/demo.json. Para probar la alternativa base:

```powershell
.\demo.ps1 -Model base
```

Para un archivo propio:

```powershell
.\demo.ps1 -Audio 'C:\ruta\mi-audio.wav'
```

No hay captura de micrófono ni envío de audios a un proveedor: la inferencia corre localmente. La primera carga de un modelo sí necesita internet para descargar sus pesos.

## Instalación reproducible para otro equipo

Instale uv y use Python 3.12. Desde services/ai:

```powershell
uv sync --frozen --python 3.12
uv run python -m spikes.download_sample
uv run python -m spikes.evaluate datasets/mediaspeech_es/manifest.csv --models base small
```

El descargador guarda ocho muestras y las referencias. Aunque retiene pocos archivos, debe recorrer el archivo comprimido y puede transferir hasta 582 MB. No sobrescribe un manifiesto existente. Los datos quedan ignorados por Git. En este equipo también hay una copia local de uv en .tools/bin/uv.exe.

## Prueba de un solo audio con referencia

```powershell
uv run python -m spikes.transcribe muestra.wav --model base --reference referencia.txt --output results/muestra.json
```

La referencia debe ser texto UTF-8 fiel a lo que realmente se escucha. Si no hay referencia, se devuelve la transcripción, pero no WER.

## Verificaciones

```powershell
uv run pytest -q -p no:cacheprovider
uv run ruff check spikes tests
uv run ruff format --check spikes tests
```

## Cómo explicar la demostración

1. Mostrar el archivo de audio y su referencia pública, identificando la fuente.
2. Ejecutar demo.ps1 y enseñar la transcripción obtenida en ese momento.
3. Abrir results/demo.json: explicar segmentos, duración, tiempo de carga e inferencia.
4. Mostrar el informe comparativo y explicar WER: errores de palabras divididos entre palabras de referencia. Menor es mejor; no equivale a accuracy de detección de fraude.
5. Explicar el límite: aún faltan similitud con la pregunta, clasificación de voz sintética e integración.

Los tiempos incluyen decodificación, VAD e iteración completa de los segmentos, pero excluyen la carga del modelo, escritura del JSON y cálculo posterior de WER. Una única pasada no constituye una prueba de rendimiento estable ni de concurrencia. El primer audio puede incluir calentamiento.

## Fuentes técnicas

- SYSTRAN, faster-whisper: https://github.com/SYSTRAN/faster-whisper
- MediaSpeech, datos y licencia: https://openslr.org/108/
- NTRLab, método y procedencia: https://github.com/NTRLab/MediaSpeech

## Datos propios pendientes

TA-006 sigue pendiente. Esta muestra pública no representa estudiantes de UPAO ni contiene etiquetas para evaluar fraude. Cuando se registren grabaciones propias, anotar autorización, hablante anónimo, escenario, pregunta, referencia, origen de la voz sintética y partición; mantener aparte los datos usados para ajustar y los de evaluación final.

Con los modelos ya descargados puede ejecutar .\demo.ps1 -Offline para una demostración sin consultas de descarga.

Comprobación adicional de tipos: uv run mypy spikes --ignore-missing-imports --follow-imports=silent.
