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

| Método | Ruta | Auth | Qué hace |
|---|---|---|---|
| `GET` | `/health` | pública | estado, entorno, versión y si la auth está activa |
| `POST` | `/api/v1/events` | estudiante | registra un evento → `201 {id, severity}` |
| `GET` | `/api/v1/sessions/{session_id}/events` | estudiante / docente | lista los eventos (filtro `?student_id=`) |
| `POST` | `/api/v1/evidence/upload-url` | — | *(pendiente, Fase 6)* |

El contrato del cuerpo está en [`packages/contracts`](../../packages/contracts/), con un ejemplo
válido por cada `event_type`.

### Códigos de error

| Código | Significado |
|---|---|
| `400` | cumple el contrato pero viola una regla de dominio (`gaze_away` sin `question_id`) |
| `401` | falta el token, es inválido o venció |
| `403` | estás identificado pero no puedes hacer esto |
| `422` | el cuerpo no cumple el contrato (lo rechaza Pydantic antes del dominio) |

422 es "arregla el JSON", 400 es "arregla la lógica".

## Autenticación

Token de Supabase Auth en la cabecera:

```
Authorization: Bearer <access_token>
```

El proyecto usa **claves asimétricas ES256**: la API verifica la firma contra el JWKS público del
proyecto, así que no necesita ningún secreto compartido para autenticar.

El rol **no viene en el token** — ahí el claim `role` vale siempre `authenticated`, que es el rol
de PostgreSQL. El rol del sistema (`teacher` / `student`) se lee de `public.profiles`, con una
caché de 60 s para no meter una consulta extra en cada evento.

### Reglas

- Un **estudiante** solo registra eventos sobre sí mismo: el `student_id` del cuerpo tiene que
  coincidir con el del token. Y al listar, solo ve los suyos: si pide los de otro, el filtro se
  ignora.
- Un **docente** ve toda la sesión, y **no** puede registrar eventos (los reporta el cliente del
  estudiante).

**Por qué esto vive en la API y no en la base de datos:** RLS protege las escrituras directas desde
el cliente, pero la API usa la *service role key* y **omite RLS por completo**. Sin estas
comprobaciones, cualquiera con un token válido podría fabricar evidencia contra otro estudiante — y
esa evidencia termina delante de un docente que decide sobre una nota.

### Desarrollo sin autenticación

`AUTH_ENABLED=false` desactiva todo lo anterior, para que Rider y Jesús puedan mandar eventos antes
de tener su pantalla de login. Dos seguros:

1. La API **se niega a arrancar** con `AUTH_ENABLED=false` si `ENV` no es `local` ni `test`.
2. Si la variable no existe, la autenticación queda **activada**. Olvidarla en un despliegue
   protege, no abre.

`GET /health` informa de `"auth": "enabled" | "disabled"`, así que se ve de un vistazo.

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
| `AUTH_ENABLED` | `true` (por defecto) \| `false` | exige token y comprueba permisos |
| `EVENT_REPOSITORY` | `memory` \| `supabase` | dónde se guardan los eventos y se leen los perfiles |
| `JOB_QUEUE` | `memory` \| `redis` | dónde se encolan los análisis de audio |
| `EVIDENCE_STORAGE` | `memory` \| `supabase` | quién firma las URLs de subida |

Cambiar de memoria a producción es cambiar estas tres variables. Eso es el beneficio de los puertos.
