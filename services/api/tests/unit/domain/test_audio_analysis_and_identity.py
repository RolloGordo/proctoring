"""La regla que define el proyecto, y la verificación de identidad.

Si una prueba de este archivo se vuelve incómoda, conviene releer el enunciado
antes de cambiarla: **leer la pregunta en voz alta para concentrarse no puede
generar una alerta.**
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from proctoring_api.domain.audio_analysis import (
    AiVoiceThresholds,
    AudioAnalysis,
    InvalidAudioAnalysisError,
)
from proctoring_api.domain.identity import (
    DEFAULT_SIMILARITY_THRESHOLD,
    IdentityCheck,
    IdentityResult,
    InvalidIdentityCheckError,
    threshold_from_settings,
)

NOW = datetime(2026, 10, 6, 15, 0, tzinfo=UTC)
UMBRALES = AiVoiceThresholds(similarity=0.6, synthetic=0.5)


def analisis(similitud: float | None, sintetica: float | None, **extra: object) -> AudioAnalysis:
    return AudioAnalysis.create(
        event_id=uuid4(),
        processed_at=NOW,
        similarity=similitud,
        synthetic_voice_score=sintetica,
        **extra,  # type: ignore[arg-type]
    )


class TestHacenFaltaLasDosCondiciones:
    def test_con_las_dos_es_una_consulta_a_una_ia(self) -> None:
        assert analisis(0.9, 0.8).is_ai_consultation(UMBRALES) is True

    def test_leer_la_pregunta_en_voz_alta_no_alerta(self) -> None:
        # Mucha similitud con el enunciado, pero ninguna voz sintetica: es alguien
        # leyendo para concentrarse. Es el falso positivo que el proyecto existe
        # para evitar.
        assert analisis(0.95, 0.05).is_ai_consultation(UMBRALES) is False

    def test_una_voz_sintetica_sola_tampoco_alerta(self) -> None:
        # Puede ser un video, una llamada o la television de fondo.
        assert analisis(0.1, 0.99).is_ai_consultation(UMBRALES) is False

    def test_ninguna_de_las_dos(self) -> None:
        assert analisis(0.2, 0.2).is_ai_consultation(UMBRALES) is False

    @pytest.mark.parametrize(
        ("similitud", "sintetica", "espera"),
        [
            (0.6, 0.5, True),  # justo en los dos umbrales: cuenta
            (0.6, 0.49, False),  # la voz se queda un pelo corta
            (0.59, 0.5, False),  # la similitud se queda un pelo corta
        ],
    )
    def test_los_umbrales_son_inclusivos(
        self, similitud: float, sintetica: float, espera: bool
    ) -> None:
        assert analisis(similitud, sintetica).is_ai_consultation(UMBRALES) is espera

    def test_con_media_medida_no_se_acusa_a_nadie(self) -> None:
        # El worker transcribio y comparo, pero no pudo puntuar la voz. Falta una
        # de las dos condiciones, asi que no hay alerta.
        assert analisis(0.99, None).is_ai_consultation(UMBRALES) is False
        assert analisis(None, 0.99).is_ai_consultation(UMBRALES) is False

    def test_umbrales_mas_exigentes_dejan_de_alertar(self) -> None:
        caso = analisis(0.7, 0.6)

        assert caso.is_ai_consultation(UMBRALES) is True
        assert caso.is_ai_consultation(AiVoiceThresholds(similarity=0.8, synthetic=0.5)) is False


class TestUmbralesDeLaSesion:
    def test_se_leen_de_la_configuracion_del_modulo(self) -> None:
        umbrales = AiVoiceThresholds.from_settings(
            {"similarity_threshold": 0.75, "synthetic_threshold": 0.4}
        )

        assert (umbrales.similarity, umbrales.synthetic) == (0.75, 0.4)

    @pytest.mark.parametrize("settings", [None, {}, {"similarity_threshold": "mucho"}])
    def test_una_sesion_mal_configurada_no_deja_el_detector_sin_umbral(
        self, settings: dict[str, object] | None
    ) -> None:
        umbrales = AiVoiceThresholds.from_settings(settings)

        assert umbrales.similarity == 0.6
        assert umbrales.synthetic == 0.5


class TestValidacionDelAnalisis:
    @pytest.mark.parametrize("valor", [-0.1, 1.1])
    def test_una_puntuacion_fuera_de_rango_se_rechaza(self, valor: float) -> None:
        with pytest.raises(InvalidAudioAnalysisError, match="entre 0 y 1"):
            analisis(valor, 0.5)

    def test_un_tiempo_de_proceso_negativo_se_rechaza(self) -> None:
        with pytest.raises(InvalidAudioAnalysisError, match="negativo"):
            analisis(0.5, 0.5, processing_ms=-1)

    def test_la_transcripcion_se_guarda_sin_espacios_de_sobra(self) -> None:
        assert analisis(0.5, 0.5, transcript="  hola  ").transcript == "hola"

    def test_una_transcripcion_vacia_queda_en_nulo(self) -> None:
        assert analisis(0.5, 0.5, transcript="   ").transcript is None

    def test_exige_zona_horaria(self) -> None:
        with pytest.raises(InvalidAudioAnalysisError, match="zona horaria"):
            AudioAnalysis.create(
                event_id=uuid4(),
                processed_at=datetime(2026, 10, 6, 15, 0),
            )

    def test_el_motivo_de_la_alerta_describe_lo_medido(self) -> None:
        motivo = analisis(0.82, 0.91).alert_reason()

        assert "82%" in motivo
        assert "91%" in motivo


class TestVerificacionDeIdentidad:
    def test_por_encima_del_umbral_coincide(self) -> None:
        check = IdentityCheck.from_similarity(0.7, threshold=0.45)

        assert check.result is IdentityResult.MATCH
        assert check.verified is True

    def test_justo_en_el_umbral_coincide(self) -> None:
        assert IdentityCheck.from_similarity(0.45, threshold=0.45).verified is True

    def test_por_debajo_no_coincide(self) -> None:
        check = IdentityCheck.from_similarity(0.2, threshold=0.45)

        assert check.result is IdentityResult.NO_MATCH
        assert check.verified is False

    def test_sin_poder_medir_es_inconcluso_y_no_verifica(self) -> None:
        # No es lo mismo que "no coincide": no habia cara, o habia varias. Ante la
        # duda, que mire el docente.
        check = IdentityCheck.from_similarity(None)

        assert check.result is IdentityResult.INCONCLUSIVE
        assert check.verified is False

    def test_inconcluso_ignora_la_similitud_que_llegue(self) -> None:
        check = IdentityCheck.from_similarity(0.99, inconclusive=True)

        assert check.result is IdentityResult.INCONCLUSIVE
        assert check.verified is False

    def test_los_numeros_quedan_como_evidencia_aunque_pase(self) -> None:
        # Es lo que despues sostiene el informe de accuracy y de FAR/FRR.
        metadata = IdentityCheck.from_similarity(
            0.8, threshold=0.45, latency_ms=120, model_version="arcface-1"
        ).as_metadata()

        assert metadata["result"] == "match"
        assert metadata["similarity"] == 0.8
        assert metadata["threshold"] == 0.45
        assert metadata["latency_ms"] == 120
        assert metadata["model_version"] == "arcface-1"

    @pytest.mark.parametrize(("similitud", "umbral"), [(1.5, 0.45), (0.5, 2.0)])
    def test_rechaza_valores_fuera_de_rango(self, similitud: float, umbral: float) -> None:
        with pytest.raises(InvalidIdentityCheckError, match="entre 0 y 1"):
            IdentityCheck.from_similarity(similitud, threshold=umbral)

    def test_rechaza_una_latencia_negativa(self) -> None:
        with pytest.raises(InvalidIdentityCheckError, match="negativa"):
            IdentityCheck.from_similarity(0.5, latency_ms=-1)

    def test_el_umbral_sale_de_la_sesion_y_cae_al_de_por_defecto(self) -> None:
        assert threshold_from_settings({"similarity_threshold": 0.6}) == 0.6
        assert threshold_from_settings(None) == DEFAULT_SIMILARITY_THRESHOLD
        assert threshold_from_settings({"otra_cosa": 1}) == DEFAULT_SIMILARITY_THRESHOLD
