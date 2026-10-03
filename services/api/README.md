# `services/api` — API principal (FastAPI, arquitectura hexagonal)

**Responsable:** Silva Vega, Héctor (Project Manager)
**Backlog:** EN-005

Sesiones, exámenes, eventos, riesgo y decisiones. Genera URLs firmadas de Storage y encola trabajos
para el servicio de IA.

## Por qué hexagonal

La regla es una sola: **`adapters → application → domain`, nunca al revés.**

- `domain/` — entidades, value objects y reglas puras. **No importa ningún framework.** Ni FastAPI,
  ni Pydantic, ni Supabase, ni Redis.
- `application/ports/` — interfaces (`Protocol`): repositorios, almacenamiento, cola, notificador.
- `application/use_cases/` — un caso de uso por archivo. Recibe un DTO, orquesta puertos, devuelve
  un DTO. No sabe si hay HTTP detrás.
- `adapters/inbound/http/` — routers de FastAPI y schemas de Pydantic. Traducen HTTP a DTOs.
- `adapters/outbound/` — implementaciones concretas: `memory/`, `supabase/`, `redis_queue/`.

Esto **no es decoración**: `import-linter` lo verifica en el CI y un PR que lo rompa no entra. El
beneficio concreto es que cada caso de uso se prueba con adaptadores en memoria, sin levantar
Supabase ni Redis, y las pruebas corren en milisegundos.

## Estructura

```
services/api/
├── src/proctoring_api/
│   ├── domain/
│   │   ├── event.py              # EventType, ProctoringEvent (entidad + validaciones)
│   │   ├── severity.py           # default_severity(event_type, duration_ms) -> Severity
│   │   └── errors.py             # DomainError, InvalidEventError
│   ├── application/
│   │   ├── ports/                # EventRepository, Clock, JobQueue, EvidenceStorage
│   │   └── use_cases/            # RegisterEvent, ListSessionEvents, CreateEvidenceUploadUrl
│   ├── adapters/
│   │   ├── inbound/http/         # routers/, schemas.py, errors.py
│   │   └── outbound/
│   │       ├── memory/           # por defecto: sin dependencias externas
│   │       ├── supabase/         # EVENT_REPOSITORY=supabase
│   │       └── redis_queue/      # JOB_QUEUE=redis
│   ├── config.py                 # Settings (pydantic-settings)
│   └── main.py                   # create_app(): compone las dependencias
└── tests/
    ├── unit/{domain,application}/
    └── integration/http/
```

## Levantar

```bash
uv sync
```

```bash
uv run uvicorn proctoring_api.main:create_app --factory --reload --port 8000
```

`--factory` es necesario: la app se construye al arrancar, no al importar el módulo, para que
los adaptadores se elijan con las variables de entorno del proceso.

Swagger en <http://localhost:8000/docs>. Con la configuración por defecto
(`EVENT_REPOSITORY=memory`, `JOB_QUEUE=memory`) **no necesita Supabase ni Redis**: se levanta y
funciona con `uv sync` y nada más.

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/health` | estado, entorno y versión |
| `POST` | `/api/v1/events` | registra un evento → `201 {id, severity}` |
| `GET` | `/api/v1/sessions/{session_id}/events` | lista los eventos de una sesión (filtro `?student_id=`) |
| `POST` | `/api/v1/evidence/upload-url` | URL firmada para que el cliente suba la captura a Storage |

Códigos de error: **422** si el cuerpo no cumple el contrato (lo rechaza Pydantic), **400** si
cumple el contrato pero viola una regla de dominio (por ejemplo `gaze_away` sin `question_id`).

El contrato del cuerpo está en [`packages/contracts`](../../packages/contracts/), con un ejemplo
válido por cada `event_type`.

## Calidad: lo que el CI exige

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest && uv run lint-imports
```

`lint-imports` es la prueba de arquitectura. Si la rompes, el pipeline se pone rojo aunque los tests
pasen.

## Configuración

Todo por variables de entorno (ver [`.env.example`](../../.env.example) en la raíz). Las que
cambian el comportamiento:

| Variable | Valores | Efecto |
|---|---|---|
| `EVENT_REPOSITORY` | `memory` \| `supabase` | dónde se guardan los eventos |
| `JOB_QUEUE` | `memory` \| `redis` | dónde se encolan los análisis de audio |
| `EVIDENCE_STORAGE` | `memory` \| `supabase` | quién firma las URLs de subida |

Cambiar de memoria a producción es cambiar estas tres variables. Eso es el beneficio de los puertos.
