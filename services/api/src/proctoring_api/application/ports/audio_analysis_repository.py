"""Puerto de resultados del analisis de audio."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from proctoring_api.domain.audio_analysis import AudioAnalysis


class AudioAnalysisRepository(Protocol):
    """Guarda lo que el servicio de IA midio sobre un fragmento de audio.

    `event_id` es unico en la tabla: reintentar un trabajo **reemplaza** el
    resultado anterior en vez de acumular filas. RQ reintenta hasta tres veces.
    """

    def save(self, analysis: AudioAnalysis) -> None:
        """Crea o reemplaza el analisis de ese evento."""
        ...

    def find_by_event(self, event_id: UUID) -> AudioAnalysis | None:
        """El analisis de un evento, o `None` si todavia no se proceso."""
        ...

    def list_by_events(self, event_ids: Sequence[UUID]) -> Sequence[AudioAnalysis]:
        """Los analisis de varios eventos, en una sola consulta.

        Existe para la revision de un caso, que muestra todos los fragmentos de
        audio de un estudiante: pedirlos de uno en uno seria una consulta por
        evento en la pantalla donde el docente decide.
        """
        ...
