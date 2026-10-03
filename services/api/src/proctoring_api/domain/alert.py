"""Alerta: la senal que llega al docente en vivo.

Una alerta es una fila en `public.alerts`, y esa tabla esta publicada en Supabase
Realtime. Insertar aqui es lo que hace que al docente le aparezca el aviso en su
pantalla sin que su navegador pregunte nada. Ver
[ADR-0007](../../../../docs/adr/0007-alertas-por-supabase-realtime.md).

El texto de `reason` va **en espanol**: lo lee una persona, y la convencion del
proyecto es codigo en ingles e interfaz en espanol.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from proctoring_api.domain.event import EventType, ProctoringEvent
from proctoring_api.domain.severity import Severity


@dataclass(frozen=True, slots=True)
class Alert:
    """Aviso al docente sobre una senal concreta."""

    id: UUID
    event_id: UUID
    session_id: UUID
    student_id: UUID
    severity: Severity
    reason: str
    created_at: datetime

    @classmethod
    def from_event(
        cls,
        event: ProctoringEvent,
        severity: Severity,
        created_at: datetime,
        alert_id: UUID | None = None,
    ) -> Alert:
        return cls(
            id=alert_id if alert_id is not None else uuid4(),
            event_id=event.id,
            session_id=event.session_id,
            student_id=event.student_id,
            severity=severity,
            reason=alert_reason(event.event_type, event.duration_ms),
            created_at=created_at,
        )


def should_alert(severity: Severity) -> bool:
    """Si esta senal merece interrumpir al docente.

    Solo `medium` y `high`. Las senales `low` quedan registradas como evidencia y
    se ven en la revision del caso, pero no generan aviso en vivo.

    El motivo no es tecnico: un docente que recibe un aviso por cada parpadeo deja
    de mirarlos, y entonces el sistema no sirve para nada. Es la misma razon por la
    que la meta del proyecto fija FPR < 20 %.

    Caso importante: `speech_detected` nace `low`, asi que **no** alerta al
    registrarse. La alerta por consulta a un asistente de IA la crea
    `services/ai` cuando confirma las dos condiciones (similitud con el enunciado
    y segunda voz sintetica). Alertar antes seria acusar a quien lee en voz alta.
    """
    return severity in (Severity.MEDIUM, Severity.HIGH)


def alert_reason(event_type: EventType, duration_ms: int) -> str:
    """Explicacion en espanol de por que se avisa, para la pantalla del docente.

    Describe lo observado, sin interpretarlo: el sistema es un auditor, no un juez.
    Dice "salio de la ventana", no "hizo trampa".
    """
    seconds = duration_ms / 1000

    match event_type:
        case EventType.FOCUS_LOST:
            return f"Salio de la ventana del examen durante {seconds:.0f} s"
        case EventType.GAZE_AWAY:
            return f"Mirada fuera de la pantalla durante {seconds:.0f} s"
        case EventType.FACE_ABSENT:
            return f"No se detecto su rostro durante {seconds:.0f} s"
        case EventType.EXTRA_PERSON:
            return "Se detecto a otra persona en camara"
        case EventType.EXTRA_DISPLAY:
            return "Se detecto un monitor adicional conectado"
        case EventType.SUSPICIOUS_PROCESS:
            return "Se detecto una aplicacion de control remoto o de captura en ejecucion"
        case EventType.SCREEN_SHARE:
            return "Se detecto que la pantalla se esta compartiendo"
        case EventType.SPEECH_DETECTED:
            return "Se detecto voz; pendiente de analisis"
        case EventType.IDENTITY_CHECK:
            return "Verificacion de identidad"
