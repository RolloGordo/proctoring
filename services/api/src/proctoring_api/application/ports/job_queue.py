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

    def enqueue_face_verification(self, participant_id: UUID, capture_path: str) -> None:
        """Pide comparar la captura con la cara de referencia del estudiante.

        Va en una cola aparte y de mayor prioridad: hay alguien esperando en la
        sala de espera, con un presupuesto de P90 < 500 ms. Si fuera detras de la
        cola de audio, un examen con mucho habla lo dejaria esperando minutos.
        """
        ...
