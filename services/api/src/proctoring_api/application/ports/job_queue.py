"""Puerto de cola de trabajos.

Desacopla la API del servicio de IA. Transcribir audio y clasificar voz sintetica
tarda segundos; si eso pasara dentro de la peticion HTTP, el cliente del estudiante
se quedaria esperando y un pico de eventos tumbaria la API. Ver ADR-0006.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class JobQueue(Protocol):
    """Encola trabajos pesados para que los consuma `services/ai`."""

    def enqueue_audio_analysis(self, event_id: UUID) -> None:
        """Pide el analisis de audio del evento indicado.

        Solo viaja el `event_id`. El fragmento de audio se lee desde Storage con
        la ruta que guarda el evento en `evidence_path`.
        """
        ...
