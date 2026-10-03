"""Tareas que consume el worker de IA.

**Esto es un esqueleto.** Demuestra que el flujo completo funciona de punta a
punta —la app manda el evento, la API lo guarda y lo encola, el worker lo
recibe— pero no analiza nada todavia.

La implementacion real es de Pierreluiggi (ver `README.md` de esta carpeta):

1. descargar el fragmento de audio desde Storage con el `evidence_path` del evento
2. transcribirlo en espanol con faster-whisper
3. comparar la transcripcion con el enunciado de la pregunta en curso
   (sentence-transformers, umbral por calibrar alrededor de 0.6)
4. detectar si hay una segunda voz sintetica respondiendo
5. escribir el resultado en `audio_analyses` y, **solo si se cumplen las dos
   condiciones**, crear la alerta en `alerts`

El punto 5 es el que define el proyecto: leer la pregunta en voz alta para
concentrarse no puede generar alerta.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def analyze_audio(event_id: str) -> dict[str, str]:
    """Analiza el audio de un evento `speech_detected`.

    Args:
        event_id: identificador del evento en `public.events`. Es lo unico que
            viaja por la cola; el audio se lee desde Storage.

    Returns:
        Un resumen del trabajo. RQ lo guarda como resultado del job.
    """
    logger.info("Analisis de audio pendiente de implementar para el evento %s", event_id)
    return {"event_id": event_id, "status": "stub"}
