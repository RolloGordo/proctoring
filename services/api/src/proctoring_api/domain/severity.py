"""Severidad por defecto de un evento.

Regla **pura**: solo depende del tipo de evento y de cuanto duro. Es la semilla del
calculo de riesgo de SPEC-009, que mas adelante combinara varias senales y el
contexto de la sesion.

Los umbrales de aqui son un punto de partida razonado, no un resultado medido. La
meta del proyecto es accuracy >= 80 % y FPR < 20 % por modulo, y eso se consigue
calibrando estos numeros con datos reales. Por eso viven en un solo sitio, sin
frameworks y con pruebas propias: cambiarlos tiene que ser barato.
"""

from __future__ import annotations

from enum import StrEnum

from proctoring_api.domain.event import EventType

#: A partir de aqui, perder el foco deja de ser un despiste y pasa a ser relevante.
FOCUS_LOST_MEDIUM_MS = 5_000
#: Medio minuto fuera de la ventana ya es otra cosa.
FOCUS_LOST_HIGH_MS = 30_000
#: Ausencia de rostro tolerada antes de considerarla sostenida.
FACE_ABSENT_MEDIUM_MS = 5_000
FACE_ABSENT_HIGH_MS = 15_000
#: Mirar fuera de pantalla de forma sostenida.
GAZE_AWAY_MEDIUM_MS = 10_000


class Severity(StrEnum):
    """Severidad de una senal, de menor a mayor."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def default_severity(event_type: EventType, duration_ms: int) -> Severity:
    """Severidad inicial de un evento recien registrado.

    `speech_detected` es deliberadamente `LOW`: por si solo no significa nada.
    Hablar en voz alta mientras se rinde un examen es legitimo, y solo el analisis
    posterior del servicio de IA puede decidir si hubo consulta a un asistente
    (similitud con el enunciado **y** segunda voz sintetica). Elevarlo aqui seria
    acusar antes de tener la evidencia, y es la via mas rapida a un falso positivo.
    """
    match event_type:
        # Presencia de otra persona o de una herramienta de control remoto o de
        # captura: son senales inequivocas, no graduales.
        case EventType.EXTRA_PERSON | EventType.SUSPICIOUS_PROCESS | EventType.SCREEN_SHARE:
            return Severity.HIGH

        # Un monitor adicional es relevante, pero puede ser el entorno habitual
        # del estudiante. Lo decide el docente al revisar.
        case EventType.EXTRA_DISPLAY:
            return Severity.MEDIUM

        case EventType.FOCUS_LOST:
            if duration_ms >= FOCUS_LOST_HIGH_MS:
                return Severity.HIGH
            if duration_ms >= FOCUS_LOST_MEDIUM_MS:
                return Severity.MEDIUM
            return Severity.LOW

        case EventType.FACE_ABSENT:
            if duration_ms >= FACE_ABSENT_HIGH_MS:
                return Severity.HIGH
            if duration_ms >= FACE_ABSENT_MEDIUM_MS:
                return Severity.MEDIUM
            return Severity.LOW

        case EventType.GAZE_AWAY:
            if duration_ms >= GAZE_AWAY_MEDIUM_MS:
                return Severity.MEDIUM
            return Severity.LOW

        # speech_detected espera al servicio de IA; identity_check es informativo
        # (el resultado concreto viaja en metadata).
        case EventType.SPEECH_DETECTED | EventType.IDENTITY_CHECK:
            return Severity.LOW
