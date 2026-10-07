"""Sesion de examen: lo que el docente crea y el estudiante rinde.

Los enums reproducen exactamente los de PostgreSQL
(`supabase/migrations/20261003120000_initial_schema.sql`). Hay una prueba que lo
comprueba leyendo el SQL, asi que si divergen se nota en el pull request que los
separe y no en la demo.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from proctoring_api.domain.errors import DomainError

MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000


class InvalidExamSessionError(DomainError):
    """Una sesion de examen no cumple las reglas del dominio."""


class SessionStatus(StrEnum):
    """Estado de la sesion. Igual que el enum `session_status` de PostgreSQL."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


class EntryState(StrEnum):
    """En que punto esta la ventana de ingreso de un examen."""

    #: Todavia no empieza. El estudiante tiene que volver mas tarde.
    NOT_STARTED = "not_started"
    #: Se puede entrar ahora.
    OPEN = "open"
    #: Paso la tolerancia de ingreso, o el examen ya termino.
    CLOSED = "closed"


class SupervisionPreset(StrEnum):
    """Nivel de supervision. Igual que `supervision_preset` de PostgreSQL."""

    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"
    CUSTOM = "custom"


class SupervisionModule(StrEnum):
    """Modulos de deteccion. Igual que `supervision_module` de PostgreSQL."""

    FACE_VERIFICATION = "face_verification"
    FACE_REVERIFICATION = "face_reverification"
    FOCUS_LOSS = "focus_loss"
    COPY_PASTE_BLOCK = "copy_paste_block"
    MULTI_MONITOR = "multi_monitor"
    GAZE = "gaze"
    EXTRA_PERSON = "extra_person"
    OBJECTS = "objects"
    EXTERNAL_VOICES = "external_voices"
    AI_VOICE = "ai_voice"
    LIVE_MONITORING = "live_monitoring"
    SCREEN_CAPTURE = "screen_capture"


#: Que modulos activa cada preset.
#:
#: La progresion no es arbitraria: cada escalon anade vigilancia a cambio de
#: coste computacional en la maquina del estudiante y de riesgo de falsos
#: positivos. `basic` es lo minimo defendible (saber quien es y si se fue de la
#: ventana); `strict` incluye el diferencial del proyecto y el monitoreo en vivo,
#: que es el modulo mas caro de todos.
PRESET_MODULES: dict[SupervisionPreset, frozenset[SupervisionModule]] = {
    SupervisionPreset.BASIC: frozenset(
        {
            SupervisionModule.FACE_VERIFICATION,
            SupervisionModule.FOCUS_LOSS,
        }
    ),
    SupervisionPreset.STANDARD: frozenset(
        {
            SupervisionModule.FACE_VERIFICATION,
            SupervisionModule.FOCUS_LOSS,
            SupervisionModule.COPY_PASTE_BLOCK,
            SupervisionModule.MULTI_MONITOR,
            SupervisionModule.GAZE,
            SupervisionModule.EXTRA_PERSON,
        }
    ),
    SupervisionPreset.STRICT: frozenset(
        {
            SupervisionModule.FACE_VERIFICATION,
            SupervisionModule.FACE_REVERIFICATION,
            SupervisionModule.FOCUS_LOSS,
            SupervisionModule.COPY_PASTE_BLOCK,
            SupervisionModule.MULTI_MONITOR,
            SupervisionModule.GAZE,
            SupervisionModule.EXTRA_PERSON,
            SupervisionModule.EXTERNAL_VOICES,
            SupervisionModule.AI_VOICE,
            SupervisionModule.SCREEN_CAPTURE,
            SupervisionModule.LIVE_MONITORING,
        }
    ),
    #: `custom` no activa nada por si mismo: el docente elige modulo a modulo.
    SupervisionPreset.CUSTOM: frozenset(),
}


#: Umbrales por defecto de cada modulo, que van a `session_modules.settings`.
#:
#: Son el mismo contrato que usan la app de escritorio y el spike de vision para
#: decidir cuando emitir un evento. Vivir aqui, en un solo sitio, es lo que
#: permite calibrarlos con datos sin tocar tres clientes. Los valores son un
#: punto de partida razonado, no medido: la meta de accuracy >= 80 % y FPR < 20 %
#: se alcanza ajustandolos.
DEFAULT_MODULE_SETTINGS: dict[SupervisionModule, dict[str, Any]] = {
    SupervisionModule.FOCUS_LOSS: {"min_duration_ms": 5000},
    SupervisionModule.GAZE: {"yaw_degrees": 25, "min_duration_ms": 3000},
    SupervisionModule.EXTRA_PERSON: {"min_faces": 2},
    SupervisionModule.FACE_VERIFICATION: {"similarity_threshold": 0.45},
    SupervisionModule.FACE_REVERIFICATION: {"interval_minutes": 10},
    SupervisionModule.MULTI_MONITOR: {"max_displays": 1},
    SupervisionModule.AI_VOICE: {"similarity_threshold": 0.6, "synthetic_threshold": 0.5},
    SupervisionModule.EXTERNAL_VOICES: {"min_speakers": 2},
    SupervisionModule.SCREEN_CAPTURE: {"scan_interval_ms": 10000},
    SupervisionModule.OBJECTS: {},
    SupervisionModule.COPY_PASTE_BLOCK: {},
    SupervisionModule.LIVE_MONITORING: {},
}


#: Alfabeto del codigo de acceso.
#:
#: Sin 0/O ni 1/I/L: el estudiante lo teclea leyendolo de una pizarra o de un
#: chat, y confundir un cero con una o es la forma mas tonta de perder cinco
#: minutos al empezar un examen.
ACCESS_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ACCESS_CODE_LENGTH = 6


def generate_access_code(length: int = ACCESS_CODE_LENGTH) -> str:
    """Codigo de acceso aleatorio y legible.

    Usa `secrets` y no `random`: un codigo adivinable dejaria entrar a un examen
    a quien no esta matriculado.
    """
    return "".join(secrets.choice(ACCESS_CODE_ALPHABET) for _ in range(length))


def modules_for(preset: SupervisionPreset) -> dict[SupervisionModule, dict[str, Any]]:
    """Modulos activos de un preset, con sus umbrales por defecto."""
    return {
        module: dict(DEFAULT_MODULE_SETTINGS.get(module, {}))
        for module in sorted(PRESET_MODULES[preset])
    }


@dataclass(frozen=True, slots=True)
class ExamSession:
    """Un examen programado por un docente."""

    id: UUID
    teacher_id: UUID
    title: str
    starts_at: datetime
    duration_minutes: int
    access_code: str
    course_id: UUID | None = None
    description: str | None = None
    entry_tolerance_minutes: int = 10
    preset: SupervisionPreset = SupervisionPreset.STANDARD
    status: SessionStatus = SessionStatus.DRAFT
    max_attempts: int = 1
    shuffle_questions: bool = True
    #: Cuantas preguntas recibe cada estudiante de las disponibles. `None` es
    #: "todas". Solo tiene efecto con bancos atados: un examen con preguntas
    #: propias las usa todas.
    question_pool_size: int | None = None
    shuffle_options: bool = True
    allow_back_navigation: bool = True
    modules: dict[SupervisionModule, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        teacher_id: UUID,
        title: str,
        starts_at: datetime,
        duration_minutes: int,
        access_code: str | None = None,
        course_id: UUID | None = None,
        description: str | None = None,
        entry_tolerance_minutes: int = 10,
        preset: SupervisionPreset = SupervisionPreset.STANDARD,
        max_attempts: int = 1,
        shuffle_questions: bool = True,
        question_pool_size: int | None = None,
        shuffle_options: bool = True,
        allow_back_navigation: bool = True,
        modules: dict[SupervisionModule, dict[str, Any]] | None = None,
        session_id: UUID | None = None,
    ) -> ExamSession:
        """Crea una sesion validada.

        Raises:
            InvalidExamSessionError: si viola alguna regla del dominio.
        """
        clean_title = title.strip()
        if not clean_title:
            raise InvalidExamSessionError("El titulo no puede estar vacio")
        if len(clean_title) > MAX_TITLE_LENGTH:
            raise InvalidExamSessionError(f"El titulo supera los {MAX_TITLE_LENGTH} caracteres")

        if description is not None:
            description = description.strip() or None
            if description is not None and len(description) > MAX_DESCRIPTION_LENGTH:
                raise InvalidExamSessionError(
                    f"La descripcion supera los {MAX_DESCRIPTION_LENGTH} caracteres"
                )

        if duration_minutes <= 0:
            raise InvalidExamSessionError("La duracion debe ser mayor que cero")
        if entry_tolerance_minutes < 0:
            raise InvalidExamSessionError("La tolerancia de ingreso no puede ser negativa")
        if max_attempts <= 0:
            raise InvalidExamSessionError("El numero de intentos debe ser mayor que cero")

        if starts_at.tzinfo is None or starts_at.utcoffset() is None:
            raise InvalidExamSessionError("starts_at debe traer zona horaria; usa ISO-8601 en UTC")

        # Con `custom` el docente elige; con los demas, el preset manda. Permitir
        # un preset con modulos que no le corresponden dejaria `preset` mintiendo
        # sobre lo que la sesion hace de verdad.
        if preset is SupervisionPreset.CUSTOM:
            resolved = dict(modules or {})
            if not resolved:
                raise InvalidExamSessionError(
                    "Un examen con preset 'custom' tiene que activar al menos un modulo"
                )
        else:
            resolved = modules_for(preset)

        return cls(
            id=session_id if session_id is not None else uuid4(),
            teacher_id=teacher_id,
            title=clean_title,
            starts_at=starts_at,
            duration_minutes=duration_minutes,
            access_code=access_code or generate_access_code(),
            course_id=course_id,
            description=description,
            entry_tolerance_minutes=entry_tolerance_minutes,
            preset=preset,
            status=SessionStatus.SCHEDULED,
            max_attempts=max_attempts,
            shuffle_questions=shuffle_questions,
            question_pool_size=question_pool_size,
            shuffle_options=shuffle_options,
            allow_back_navigation=allow_back_navigation,
            modules=resolved,
        )

    @property
    def ends_at(self) -> datetime:
        return self.starts_at + timedelta(minutes=self.duration_minutes)

    def entry_state_at(self, moment: datetime) -> EntryState:
        """En que punto esta la ventana de ingreso.

        Devuelve **tres** estados y no un booleano porque "todavia no empieza" y
        "ya cerro" se parecen desde dentro y no se parecen en nada para quien
        espera: a uno hay que decirle que vuelva, al otro que hable con su
        docente. Con un booleano, el estudiante que llegaba pronto recibia
        "el plazo esta cerrado", que es lo contrario de lo que pasaba.
        """
        if moment < self.starts_at:
            return EntryState.NOT_STARTED

        limit = self.starts_at + timedelta(minutes=self.entry_tolerance_minutes)
        return EntryState.OPEN if moment <= min(limit, self.ends_at) else EntryState.CLOSED

    def accepts_entry_at(self, moment: datetime) -> bool:
        """Si un estudiante puede entrar en ese instante.

        Hay tolerancia al inicio porque llegar dos minutos tarde no deberia
        costar el examen, pero no se puede entrar una vez terminado.
        """
        return self.entry_state_at(moment) is EntryState.OPEN
