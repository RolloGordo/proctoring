"""Verificación de identidad por rostro.

El servicio de IA **mide** la similitud entre la cara de referencia del estudiante
y la captura del momento; la API **decide** si eso basta, con el umbral de la
sesión. Igual que en el análisis de audio: la medida es del modelo, la decisión es
del sistema y vive en un solo sitio con pruebas.

Una verificación que falla **no expulsa a nadie**. El estudiante queda esperando y
el docente lo admite a mano desde su sala de espera. Un reconocimiento facial que
falla con mala luz, con lentes o con una cámara mala no puede costarle el examen a
nadie.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from proctoring_api.domain.errors import DomainError

#: Mismo valor que `DEFAULT_MODULE_SETTINGS[FACE_VERIFICATION]`. **Punto de
#: partida razonado, no medido:** calibrarlo con pares reales e impostores, y
#: reportar FAR/FRR, es parte del trabajo de SPEC-005.
DEFAULT_SIMILARITY_THRESHOLD = 0.45


class InvalidIdentityCheckError(DomainError):
    """El resultado de la verificación no es válido."""


class IdentityResult(StrEnum):
    """Qué concluyó la verificación."""

    MATCH = "match"
    NO_MATCH = "no_match"
    #: No se pudo decidir: no se detectó una cara, había varias, o la imagen no
    #: servía. **No es lo mismo que "no coincide"**, y el docente tiene que poder
    #: distinguirlo cuando revise.
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class IdentityCheck:
    """Lo que midió el modelo al comparar dos caras."""

    result: IdentityResult
    similarity: float | None
    threshold: float
    latency_ms: int | None
    model_version: str | None

    @classmethod
    def from_similarity(
        cls,
        similarity: float | None,
        *,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        latency_ms: int | None = None,
        model_version: str | None = None,
        inconclusive: bool = False,
    ) -> IdentityCheck:
        """Construye el resultado aplicando el umbral.

        `inconclusive=True` es para cuando el modelo no pudo medir (sin cara, o
        con varias). En ese caso `similarity` se ignora.

        Raises:
            InvalidIdentityCheckError: si la similitud o el umbral están fuera de
                [0, 1], o si la latencia es negativa.
        """
        if not 0.0 <= threshold <= 1.0:
            raise InvalidIdentityCheckError("El umbral debe estar entre 0 y 1")
        if similarity is not None and not 0.0 <= similarity <= 1.0:
            raise InvalidIdentityCheckError("La similitud debe estar entre 0 y 1")
        if latency_ms is not None and latency_ms < 0:
            raise InvalidIdentityCheckError("La latencia no puede ser negativa")

        if inconclusive or similarity is None:
            resultado = IdentityResult.INCONCLUSIVE
        elif similarity >= threshold:
            resultado = IdentityResult.MATCH
        else:
            resultado = IdentityResult.NO_MATCH

        return cls(
            result=resultado,
            similarity=similarity,
            threshold=threshold,
            latency_ms=latency_ms,
            model_version=model_version,
        )

    @property
    def verified(self) -> bool:
        """Solo `match` da por verificada la identidad.

        `inconclusive` **no** verifica: ante la duda, que mire el docente.
        """
        return self.result is IdentityResult.MATCH

    def as_metadata(self) -> dict[str, Any]:
        """Los números para la `metadata` del evento `identity_check`.

        Se guardan **todos**, también cuando la verificación pasa: son lo que
        después sostiene el informe de accuracy y de FAR/FRR.
        """
        return {
            "source": "services_ai",
            "result": self.result.value,
            "similarity": self.similarity,
            "threshold": self.threshold,
            "latency_ms": self.latency_ms,
            "model_version": self.model_version,
        }


def threshold_from_settings(settings: dict[str, Any] | None) -> float:
    """Lee el umbral de la configuración del módulo `face_verification`."""
    valor = (settings or {}).get("similarity_threshold")
    return float(valor) if isinstance(valor, (int, float)) else DEFAULT_SIMILARITY_THRESHOLD
