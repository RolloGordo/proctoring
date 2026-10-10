"""Analisis de audio en memoria."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from uuid import UUID

from proctoring_api.domain.audio_analysis import AudioAnalysis


class InMemoryAudioAnalysisRepository:
    """Implementacion de `AudioAnalysisRepository` sobre un diccionario."""

    def __init__(self) -> None:
        #: event_id -> analisis. Clave unica, igual que la tabla: reprocesar
        #: reemplaza.
        self._analyses: dict[UUID, AudioAnalysis] = {}
        self._lock = threading.Lock()

    def save(self, analysis: AudioAnalysis) -> None:
        with self._lock:
            self._analyses[analysis.event_id] = analysis

    def find_by_event(self, event_id: UUID) -> AudioAnalysis | None:
        with self._lock:
            return self._analyses.get(event_id)

    def list_by_events(self, event_ids: Sequence[UUID]) -> Sequence[AudioAnalysis]:
        with self._lock:
            return [self._analyses[i] for i in event_ids if i in self._analyses]
