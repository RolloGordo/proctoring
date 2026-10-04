"""Configuracion de la API.

Todo por variables de entorno (ver `.env.example` en la raiz del repositorio).
Las tres variables de seleccion de adaptador son lo que hace util la arquitectura
hexagonal en la practica: pasar de desarrollo a produccion es cambiarlas, sin
tocar una linea de logica.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

RepositoryBackend = Literal["memory", "supabase"]
JobQueueBackend = Literal["memory", "redis"]
EvidenceStorageBackend = Literal["memory", "supabase"]

#: Unicos entornos donde se permite correr sin autenticacion. Ninguno es un
#: despliegue: `local` es la maquina de cada integrante y `test` la suite.
#: Cualquier otro valor de ENV hace que la API se niegue a arrancar con
#: AUTH_ENABLED=false.
ENVS_WITHOUT_AUTH = frozenset({"local", "test"})


class Settings(BaseSettings):
    """Ajustes del servicio."""

    model_config = SettingsConfigDict(
        # Se busca .env en services/api y, si no, en la raiz del monorepo: asi
        # funciona igual al correr `uv run` dentro del servicio que con docker compose.
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = "local"
    api_port: int = 8000

    # --- Seguridad ---
    #: Por defecto **activada**. Si la variable no existe, se protege: es el caso
    #: de un despliegue donde alguien olvido configurarla.
    #:
    #: Desactivarla solo se permite con ENV=local (lo comprueba `create_app`, que
    #: se niega a arrancar en cualquier otro entorno). Existe porque la app de
    #: escritorio y el spike de vision necesitan mandar eventos antes de que su
    #: pantalla de login este hecha.
    auth_enabled: bool = True

    #: Docente al que se atribuyen las sesiones cuando la autenticacion esta
    #: desactivada.
    #:
    #: Es configurable porque `exam_sessions.teacher_id` tiene clave foranea a
    #: `profiles`: con EVENT_REPOSITORY=supabase, el id ficticio por defecto no
    #: existe y el insert falla. Poniendo aqui el id de un docente real se puede
    #: probar el camino completo contra la base sin montar antes el login.
    #:
    #: Solo se usa con AUTH_ENABLED=false, que a su vez solo se permite con
    #: ENV local o test.
    dev_teacher_id: UUID = UUID("00000000-0000-4000-8000-000000000001")

    #: Estudiante al que se atribuyen las matriculas con la autenticacion
    #: desactivada. Sin esto, el flujo del estudiante es imposible de probar
    #: en local, que es justo el modo en el que trabaja el equipo.
    #:
    #: Con EVENT_REPOSITORY=supabase hay que poner el id de un estudiante real,
    #: porque session_participants.student_id tiene clave foranea a profiles.
    dev_student_id: UUID = UUID("00000000-0000-4000-8000-000000000002")

    #: Limitacion de peticiones. Activada por defecto: si la variable falta en un
    #: despliegue, se protege.
    #:
    #: Se desactiva en las pruebas de integracion, que hacen decenas de
    #: peticiones seguidas desde el mismo cliente y chocarian con el limite.
    rate_limit_enabled: bool = True

    # --- Seleccion de adaptadores ---
    event_repository: RepositoryBackend = "memory"
    job_queue: JobQueueBackend = "memory"
    evidence_storage: EvidenceStorageBackend = "memory"

    # --- Supabase ---
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    #: Omite RLS. Solo en el servidor, nunca en el cliente ni en el repositorio.
    supabase_service_role_key: str = ""
    supabase_evidence_bucket: str = "evidences"
    supabase_audio_bucket: str = "audio-segments"
    supabase_reference_faces_bucket: str = "reference-faces"

    # --- Cola ---
    redis_url: str = "redis://redis:6379/0"

    # --- Servicio de IA ---
    ai_service_url: str = "http://localhost:8001"

    # --- CORS ---
    # NoDecode desactiva el parseo JSON que pydantic-settings aplica por defecto a
    # los tipos complejos: sin el, `CORS_ORIGINS=http://localhost:5173` revienta
    # porque no es JSON valido. Con el, el validador de abajo decide el formato.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Acepta `CORS_ORIGINS` como lista separada por comas.

        Un `.env` solo guarda texto, y obligar a escribir JSON ahi para una lista
        de dos URLs es una fuente de errores tonta.
        """
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def require_supabase(self) -> tuple[str, str]:
        """URL y service role key, comprobando que esten configuradas.

        Raises:
            ValueError: si falta alguna. Se falla al arrancar y no en la primera
                peticion, que es cuando ya hay un estudiante rindiendo examen.
        """
        missing = [
            name
            for name, value in (
                ("SUPABASE_URL", self.supabase_url),
                ("SUPABASE_SERVICE_ROLE_KEY", self.supabase_service_role_key),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                f"Faltan variables de entorno para usar Supabase: {', '.join(missing)}. "
                "Copia .env.example a .env y rellenalas, o deja EVENT_REPOSITORY=memory."
            )
        return self.supabase_url, self.supabase_service_role_key

    def require_supabase_url(self) -> str:
        """URL del proyecto, necesaria para verificar tokens.

        Verificar firmas no necesita ningun secreto: las claves son asimetricas
        (ES256) y la parte publica se lee del JWKS del proyecto.
        """
        if not self.supabase_url:
            raise ValueError(
                "Falta SUPABASE_URL, necesaria para verificar los tokens. "
                "Rellenala en .env, o usa AUTH_ENABLED=false con ENV=local."
            )
        return self.supabase_url
