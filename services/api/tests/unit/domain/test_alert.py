"""Reglas de la alerta."""

from __future__ import annotations

import pytest

from proctoring_api.domain.alert import alert_reason, should_alert
from proctoring_api.domain.event import EventType
from proctoring_api.domain.severity import Severity


class TestShouldAlert:
    def test_low_does_not_interrupt_the_teacher(self) -> None:
        """Un docente que recibe un aviso por cada parpadeo deja de mirarlos.

        Las senales `low` quedan como evidencia y se ven en la revision del caso,
        pero no generan aviso en vivo. Es la misma razon por la que el proyecto
        fija FPR < 20 %.
        """
        assert should_alert(Severity.LOW) is False

    @pytest.mark.parametrize("severity", [Severity.MEDIUM, Severity.HIGH])
    def test_medium_and_high_do(self, severity: Severity) -> None:
        assert should_alert(severity) is True


class TestAlertReason:
    def test_includes_the_duration_in_seconds(self) -> None:
        assert alert_reason(EventType.FOCUS_LOST, 8_400) == (
            "Salio de la ventana del examen durante 8 s"
        )

    def test_describes_without_accusing(self) -> None:
        # El sistema es un auditor, no un juez: describe lo observado y la
        # interpretacion la pone el docente.
        #
        # El veto a "copi" se escribio cuando no existia ningun evento de copia,
        # como atajo para "no digas que copio". Con `copy_attempt` ya no se
        # puede describir lo observado sin nombrar el atajo que se pulso, y
        # nombrarlo no es acusar: lo que no puede decir es que intentara copiar
        # el examen, porque pulsar Ctrl+C tambien puede ser un reflejo o copiar
        # la propia respuesta. Por eso la prohibicion sigue para todos los demas
        # y para este se comprueba que no interprete la intencion.
        for event_type in EventType:
            reason = alert_reason(event_type, 5_000)
            assert reason
            assert "trampa" not in reason.lower()
            if event_type is EventType.COPY_ATTEMPT:
                assert "intento copiar" not in reason.lower()
                assert "intento de copiar" not in reason.lower()
            else:
                assert "copi" not in reason.lower()

    def test_every_event_type_has_a_reason(self) -> None:
        # alerts.reason es NOT NULL en la base: si falta un caso, el match
        # devuelve None y el insert explota en produccion.
        for event_type in EventType:
            assert isinstance(alert_reason(event_type, 0), str)
