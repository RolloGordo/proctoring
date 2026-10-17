"""Análisis del audio de un evento `speech_detected`.

**Aquí vive la regla que define el proyecto.** Un estudiante que lee la pregunta
en voz alta para concentrarse no está haciendo nada malo, y un sistema que lo
acusa por eso es peor que no tener sistema. Por eso una consulta a un asistente
de IA solo se da por detectada cuando se cumplen **las dos** condiciones:

1. lo que se dijo **se parece al enunciado** de la pregunta en curso, y
2. hay una **segunda voz sintética** respondiendo.

La primera sola es leer en voz alta. La segunda sola puede ser un video, una
llamada o la televisión. Juntas son otra cosa.

La regla vive en la API y no en el servicio de IA a propósito: el worker **mide**
(transcribe, calcula similitud, puntúa la voz), y la API **decide**, con los
umbrales de la sesión y con pruebas. Así la decisión es una sola, está en un
sitio y se puede calibrar sin tocar el worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from proctoring_api.domain.errors import DomainError

#: Umbrales por defecto, los mismos que `DEFAULT_MODULE_SETTINGS[AI_VOICE]`.
#: **Son un punto de partida razonado, no un resultado medido:** calibrarlos con
#: datos reales es parte del trabajo de SPEC-008.
DEFAULT_SIMILARITY_THRESHOLD = 0.6
DEFAULT_SYNTHETIC_THRESHOLD = 0.5

MAX_TRANSCRIPT_LENGTH = 10_000


class InvalidAudioAnalysisError(DomainError):
    """El resultado del análisis no es válido."""


@dataclass(frozen=True, slots=True)
class AiVoiceThresholds:
    """Los dos umbrales que deciden si hubo consulta a una IA."""

    similarity: float = DEFAULT_SIMILARITY_THRESHOLD
    synthetic: float = DEFAULT_SYNTHETIC_THRESHOLD

    @classmethod
    def from_settings(cls, settings: dict[str, Any] | None) -> AiVoiceThresholds:
        """Lee los umbrales de la configuración del módulo `ai_voice`.

        Un valor ausente o con un tipo que no es un número usa el de por defecto:
        una sesión mal configurada no debe dejar el detector sin umbral.
        """

        def leer(clave: str, por_defecto: float) -> float:
            valor = (settings or {}).get(clave)
            return float(valor) if isinstance(valor, (int, float)) else por_defecto

        return cls(
            similarity=leer("similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD),
            synthetic=leer("synthetic_threshold", DEFAULT_SYNTHETIC_THRESHOLD),
        )


@dataclass(frozen=True, slots=True)
class AudioAnalysis:
    """Lo que el servicio de IA midió sobre un fragmento de audio.

    Todos los campos de medida son opcionales: un análisis puede fallar a medias
    (transcribe pero no logra puntuar la voz) y aun así lo medido es evidencia
    que vale la pena guardar.
    """

    id: UUID
    event_id: UUID
    transcript: str | None
    similarity: float | None
    synthetic_voice_score: float | None
    matched_question_id: UUID | None
    processing_ms: int | None
    #: Qué modelos y versiones produjeron esto. Sin esto, un número medido hoy no
    #: se puede comparar con el de la semana que viene.
    model_versions: dict[str, Any]
    processed_at: datetime

    @classmethod
    def create(
        cls,
        *,
        event_id: UUID,
        processed_at: datetime,
        transcript: str | None = None,
        similarity: float | None = None,
        synthetic_voice_score: float | None = None,
        matched_question_id: UUID | None = None,
        processing_ms: int | None = None,
        model_versions: dict[str, Any] | None = None,
        analysis_id: UUID | None = None,
    ) -> AudioAnalysis:
        """Crea un análisis validado.

        Raises:
            InvalidAudioAnalysisError: si una puntuación está fuera de [0, 1], si
                el tiempo de proceso es negativo, si la transcripción es enorme o
                si la fecha no trae zona horaria.
        """
        for nombre, valor in (
            ("similarity", similarity),
            ("synthetic_voice_score", synthetic_voice_score),
        ):
            if valor is not None and not 0.0 <= valor <= 1.0:
                raise InvalidAudioAnalysisError(f"{nombre} debe estar entre 0 y 1")

        if processing_ms is not None and processing_ms < 0:
            raise InvalidAudioAnalysisError("processing_ms no puede ser negativo")

        limpio = (transcript or "").strip() or None
        if limpio is not None and len(limpio) > MAX_TRANSCRIPT_LENGTH:
            raise InvalidAudioAnalysisError(
                f"La transcripcion supera los {MAX_TRANSCRIPT_LENGTH} caracteres"
            )

        if processed_at.tzinfo is None or processed_at.utcoffset() is None:
            raise InvalidAudioAnalysisError("processed_at debe traer zona horaria")

        return cls(
            id=analysis_id if analysis_id is not None else uuid4(),
            event_id=event_id,
            transcript=limpio,
            similarity=similarity,
            synthetic_voice_score=synthetic_voice_score,
            matched_question_id=matched_question_id,
            processing_ms=processing_ms,
            model_versions=dict(model_versions or {}),
            processed_at=processed_at,
        )

    def is_ai_consultation(self, thresholds: AiVoiceThresholds) -> bool:
        """Si esto es una consulta a un asistente de IA.

        **Hacen falta las dos condiciones.** Si falta cualquiera de las dos
        medidas, la respuesta es `False`: no se acusa a nadie con media
        evidencia.
        """
        if self.similarity is None or self.synthetic_voice_score is None:
            return False
        return (
            self.similarity >= thresholds.similarity
            and self.synthetic_voice_score >= thresholds.synthetic
        )

    def alert_reason(self) -> str:
        """El texto que lee el docente. Describe lo medido, no lo interpreta."""
        similitud = round((self.similarity or 0) * 100)
        sintetica = round((self.synthetic_voice_score or 0) * 100)
        return (
            f"Posible consulta a un asistente de IA: lo dicho coincide {similitud}% "
            f"con el enunciado y se detectó una segunda voz sintética ({sintetica}%)"
        )
