# P3 · Worker de audio · implementación local

Guía vigente: `pierreluiggi-ia-audio.md`, recibida del líder. P3 son 8 h estimadas,
no horas realizadas. El código está en una copia local `semana6-integracion`;
no se creó una rama nueva ni se publicó en Git.

## Flujo y archivos

- `tasks.py`, `analyze_audio`: valida UUID y token interno, pide el trabajo a la
  API, descarga a un directorio temporal, mide y envía el resultado. El temporal
  se elimina incluso al fallar. Devuelve la respuesta de la API, incluido `alerted`.
- `audio_runtime.py`: descarga privada de Storage, límite de 8 MB, sin redirecciones
  con credenciales; valida audio de 0,1 a 30 s; carga small/MiniLM una vez por proceso.
  Los modelos deben estar descargados: la inferencia no inicia descargas.
- `tests/test_audio_worker.py`: flujo, limpieza, error sin éxito ficticio, pregunta
  ausente, rutas rechazadas y detector desactivado como `null`, nunca como cero medido.

El worker no escribe en Supabase DB, no crea alertas ni aplica los umbrales.
Registra ambos umbrales en `model_versions`. Si no existe enunciado, similarity
queda en `null`. Si el texto excede el contexto de MiniLM se informa que esa
medida no está disponible; no se trunca para fabricar una coincidencia.

## Configuración local

Desde `services/ai`, Python 3.12 y `uv sync --locked --extra similarity --extra voice`.
Preparar small y la revisión MiniLM
`e8f8c211226b894fcb81acc59f3b34ba3efd5f42` en `models/` antes de arrancar.
Se pueden reutilizar las cachés locales previas; no están en el paquete.

Con conexión, para preparar explícitamente las dos cachés desde services/ai:

```powershell
uv run --extra similarity python -c "from spikes.transcribe import Transcriber; from spikes.similarity import SimilarityModel; Transcriber('small'); SimilarityModel('e8f8c211226b894fcb81acc59f3b34ba3efd5f42')"
```

Esta descarga es preparación, no se ejecuta dentro de un trabajo. El Dockerfile
heredado no está adaptado a estas dependencias/archivos; coordinarlo con Héctor.

Variables del servidor, nunca de la web:

```text
PROCTORING_API_URL=http://localhost:8000
INTERNAL_API_TOKEN=<secreto interno configurado por el equipo>
SUPABASE_URL=<URL de desarrollo>
SUPABASE_SERVICE_ROLE_KEY=<credencial privada del servidor>
AUDIO_BUCKET=audio-segments
AUDIO_SYNTHETIC_MODE=disabled
```

No guardar los valores reales en documentación. Exportar las variables en la
terminal: el código no carga `.env` automáticamente. Para un evento real:

```powershell
uv run --extra similarity --extra voice python -c "import tasks; print(tasks.analyze_audio('UUID-DEL-EVENTO'))"
```

Con `disabled`, se guarda la transcripción/similitud y el score sintético es
`null`. Por tanto la API no puede generar una alerta de IA con ese análisis.
Para experimentos supervisados se admite `AUDIO_SYNTHETIC_MODE=aasist-experimental`
y rutas `AASIST_SOURCE`, `AASIST_CONFIG`, `AASIST_WEIGHTS` a la copia oficial revisada.
Ese modo aún no está validado para un examen. AASIST mide indicios sintéticos,
no identifica una segunda persona ni demuestra consulta a una IA.

## Tiempos: qué se mide

`processing_ms` incluye pedir el trabajo, descargar, cargar modelos si están fríos,
decodificar, inferir y limpiar el temporal. Se calcula justo antes del POST.
El POST no puede incluir en su propio cuerpo cuánto tardará su respuesta:
`worker_total_ms` se registra después, incluyendo ese viaje de red.
Ninguno incluye espera en Redis, subida del cliente o llegada a la pantalla del docente.
La meta completa de menos de 10 s requiere medir esas etapas con un evento real.

La caché es por proceso. RQ puede crear un proceso nuevo por trabajo: no se asume
que siempre esté caliente. Hay que medir el arranque real antes de declarar la meta.

## Pendiente de aceptación

Dataset P2 y validación de segunda voz; evento real en Storage; fila real en
`audio_analyses`; alerta en pantalla con ambas condiciones; latencia del flujo.
Las pruebas locales no sustituyen esas evidencias. La plantilla facial de Jesús
se mantiene como estaba. No se modificaron la API, la base ni sus reglas.
