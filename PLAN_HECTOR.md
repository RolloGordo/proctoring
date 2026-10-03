# PLAN — Tareas de Héctor (Project Manager / backend / infraestructura)

Lee primero `CLAUDE.md` (contexto, arquitectura, convenciones). Este plan es lo que hay que construir **hoy y esta semana**, en orden. Trabaja por fases; al terminar cada fase, corre las pruebas, haz commit y muéstrame un resumen antes de seguir.

## Contexto de urgencia

El docente (Product Owner) revisó el avance el 03/10/2026 y criticó que solo había investigación. Pide **código tangible hoy**: estructura real de carpetas del proyecto (backend, frontend, escritorio) y una API funcionando. Mi tarea es la base sobre la que trabajan los otros tres integrantes, por eso la Fase 1 debe quedar lista y subida en la primera hora para que ellos clonen el repo y empiecen.

Restricciones: todo gratuito u open source; Windows es el sistema principal del equipo (los comandos deben funcionar en PowerShell y en bash); cada integrante debe poder levantar todo en local.

---

## Fase 1 — Monorepo y estructura (≈ 1 h) · EN-004

1. Inicializa git en la carpeta actual con la estructura del punto 4 de `CLAUDE.md`. Crea las carpetas reales con un `README.md` en cada una explicando qué va ahí y quién es responsable.
2. Archivos raíz:
   - `README.md`: descripción del proyecto, diagrama de carpetas, requisitos (Python 3.12, uv, Node 20 LTS o superior, Docker Desktop), cómo levantar todo en local, flujo de ramas y Definición de terminado.
   - `.gitignore` combinado (Python, Node, Electron, `.env`, `*.wav`, `*.mp3`, `models/`, `datasets/`, `dist/`, `out/`).
   - `.env.example` con: `ENV=local`, `API_PORT=8000`, `EVENT_REPOSITORY=memory`, `SUPABASE_URL=`, `SUPABASE_SERVICE_ROLE_KEY=`, `SUPABASE_ANON_KEY=`, `REDIS_URL=redis://redis:6379/0`, `CORS_ORIGINS=http://localhost:5173`.
   - `.editorconfig`.
3. Carpetas de los compañeros, **solo con README** (no implementes su código). Cada README lleva el objetivo, los pasos y los criterios de aceptación:
   - `apps/desktop/README.md` (Rider): app Electron + TypeScript con electron-vite; detectar `blur`/`focus` de la ventana con duración, número de monitores (`screen.getAllDisplays()`, eventos `display-added/removed`), procesos sospechosos cada 10 s (`ps-list`: Zoom, AnyDesk, TeamViewer, OBS, Discord), `setContentProtection(true)`, `kiosk: true`, bloqueo de copiar/pegar; enviar eventos a `POST http://localhost:8000/api/v1/events` con el contrato de `packages/contracts`.
   - `services/ai/README.md` (Pierreluiggi): spikes en `services/ai/spikes/` — `transcribir.py` (faster-whisper `small`, español), `similitud.py` (sentence-transformers `paraphrase-multilingual-MiniLM-L12-v2`, alerta si > 0.6), `pipeline_vad.py` (Silero VAD continuo + tiempos), `qti_import.py` (QTI 2.1 → JSON de `questions`/`question_options`).
   - `apps/web/spikes/vision/README.md` (Jesús): Vite + TS + `@mediapipe/tasks-vision` Face Landmarker; rostro ausente > 5 s, más de un rostro, cabeza girada > 25° por > 3 s; captura del canvas por evento.
   - `supabase/`: YA EXISTE con 4 migraciones aplicadas y su README (lo hizo Héctor). Solo cópialo tal cual al repo y genera los tipos TypeScript con `npx supabase gen types typescript --project-id uzuysjmymvtpoxfrdxnm > packages/contracts/database.types.ts`.
4. `specs/` con una carpeta por SPEC-001..SPEC-009 y un `requisitos.md` mínimo con el título y el responsable (el contenido completo lo pegamos después).
5. `docs/adr/` con un archivo por decisión (formato: Contexto, Decisión, Alternativas, Consecuencias), estado "Aceptada":
   - 0001 Hexagonal con dos servicios backend (API e IA)
   - 0002 Docente en web, estudiante en Electron
   - 0003 Supabase para datos, auth, storage y tiempo real
   - 0004 Detección liviana en cliente, pesada en servidor, sin video continuo
   - 0005 Python en todo el backend
   - 0006 Cola Redis + RQ entre API e IA
   - 0007 Alertas por Supabase Realtime
   - 0008 El sistema aloja sus exámenes; sin integración LMS (se importa QTI)
   - 0009 Monorepo + GitHub Actions; Vercel, Render, Hugging Face Spaces
6. `docs/evidencias/semana-05/` y `semana-06/` con subcarpetas por integrante (`hector/`, `rider/`, `pierreluiggi/`, `jesus/`) y un `.gitkeep`.
7. Commit: `chore(EN-004): scaffold monorepo structure`. Dame los comandos para crear el repo en GitHub (`gh repo create proctoring --private --source=. --push`), crear la rama `develop`, proteger `main` y agregar a los colaboradores.

**Criterio de aceptación:** `tree -L 3` muestra la estructura; cada carpeta tiene README; el repo está en GitHub con `main` y `develop`.

---

## Fase 2 — Contrato compartido (≈ 30 min) · EN-003 (parte API)

1. `packages/contracts/event.schema.json` (JSON Schema draft 2020-12) con el contrato de `CLAUDE.md` §6: `event_type` como enum, `duration_ms` entero ≥ 0, UUIDs con formato, `started_at` date-time, `additionalProperties: false`.
2. `packages/contracts/README.md` con un ejemplo válido por cada `event_type`.
3. `packages/contracts/examples/*.json` (un archivo por tipo), que usaremos en pruebas y que Rider usará en la app.

---

## Fase 3 — API principal hexagonal funcionando (≈ 3 h) · EN-005 (base)

Ubicación: `services/api`. Gestor `uv` (`uv init --package`), paquete `proctoring_api` en `src/`.

Dependencias: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`. Desarrollo: `pytest`, `httpx`, `ruff`, `mypy`, `import-linter`. (Usa las versiones estables actuales.)

### Dominio (`domain/`) — sin imports de frameworks
- `event.py`: `EventType` (Enum con los valores del contrato) y entidad `ProctoringEvent` (`id`, `session_id`, `student_id`, `question_id | None`, `event_type`, `started_at` con zona UTC, `duration_ms`, `metadata: dict`, `evidence_path | None`). Validaciones en el constructor/fábrica: `duration_ms >= 0`; `started_at` con zona horaria; `question_id` obligatorio para `speech_detected` y `gaze_away`.
- `errors.py`: `DomainError`, `InvalidEventError`.
- `severity.py`: regla pura `default_severity(event_type, duration_ms) -> Severity` (low/medium/high) como semilla del cálculo de riesgo, por ejemplo `focus_lost` > 5000 ms = medium; `extra_person` = high; `speech_detected` = low hasta que la IA confirme.

### Aplicación (`application/`)
- `ports/event_repository.py`: `EventRepository` (Protocol) con `save(event)`, `list_by_session(session_id, student_id=None)`.
- `ports/clock.py`: `Clock` (Protocol) con `now()`.
- `ports/job_queue.py`: `JobQueue` (Protocol) con `enqueue_audio_analysis(event_id)` (implementación real en una fase posterior).
- `use_cases/register_event.py`: `RegisterEvent` recibe un DTO de entrada (dataclass), crea la entidad, la guarda, y si es `speech_detected` llama a `JobQueue.enqueue_audio_analysis`. Devuelve un DTO con `id` y `severity`.
- `use_cases/list_session_events.py`: `ListSessionEvents`.

### Adaptadores
- `adapters/outbound/memory/event_repository.py`: implementación en memoria (thread-safe con lock).
- `adapters/outbound/memory/job_queue.py`: cola falsa que registra los encolados (para pruebas y modo local sin Redis).
- `adapters/outbound/supabase/event_repository.py`: implementación con el cliente oficial `supabase` contra la tabla `events`. Déjala completa; se activa con `EVENT_REPOSITORY=supabase`. La tabla `events` ya existe en Supabase con las columnas de `CLAUDE.md` §7.
- `adapters/inbound/http/schemas.py`: modelos Pydantic de request/response alineados al contrato.
- `adapters/inbound/http/routers/health.py`: `GET /health` → `{"status":"ok","env":...,"version":...}`.
- `adapters/inbound/http/routers/events.py`:
  - `POST /api/v1/events` → 201 con `{id, severity}`; 422 si no cumple el contrato; 400 si viola reglas de dominio.
  - `GET /api/v1/sessions/{session_id}/events?student_id=` → lista.
- Manejo de errores: mapear `DomainError` a 400 con mensaje claro.

### Composición
- `config.py`: `Settings` con pydantic-settings leyendo `.env`.
- `main.py`: `create_app()` que arma dependencias según `EVENT_REPOSITORY` (memory|supabase), CORS desde `CORS_ORIGINS`, y documentación OpenAPI con título "Proctoring API".

### Pruebas (`tests/`)
- `unit/domain/`: validaciones de la entidad y `default_severity`.
- `unit/application/`: `RegisterEvent` con repo y cola en memoria (incluye que `speech_detected` encola y `focus_lost` no).
- `integration/http/`: `TestClient` para `/health`, POST válido (usar `packages/contracts/examples`), POST inválido (422), regla de dominio (400) y GET por sesión.
- Meta: todas pasan con `uv run pytest`.

### Arquitectura verificada
En `pyproject.toml`:
```toml
[tool.importlinter]
root_package = "proctoring_api"
include_external_packages = true

[[tool.importlinter.contracts]]
name = "Hexagonal layers"
type = "layers"
layers = ["proctoring_api.adapters", "proctoring_api.application", "proctoring_api.domain"]

[[tool.importlinter.contracts]]
name = "Core is framework-free"
type = "forbidden"
source_modules = ["proctoring_api.domain", "proctoring_api.application"]
forbidden_modules = ["fastapi", "pydantic", "supabase", "redis", "rq", "httpx", "starlette"]
```
`uv run lint-imports` debe pasar. Si algo no encaja con la versión instalada de import-linter, ajústalo y dime qué cambiaste.

### Docker
- `services/api/Dockerfile` multi-stage con uv, usuario no root, `uvicorn proctoring_api.main:app --host 0.0.0.0 --port 8000`.
- `docker-compose.yml` en la raíz con `api` (build, puerto 8000, env_file `.env`, healthcheck a `/health`) y `redis` (`redis:7-alpine`, puerto 6379). Deja comentado el servicio `ai` para Pierreluiggi.

**Criterio de aceptación:** `docker compose up --build` levanta la API; `http://localhost:8000/docs` muestra Swagger; un POST de ejemplo responde 201; `pytest`, `ruff check`, `mypy` y `lint-imports` pasan. Commit por bloque (`feat(EN-005): ...`, `test(EN-005): ...`).

---

## Fase 4 — CI en GitHub Actions (≈ 1 h) · EN-004

`.github/workflows/ci.yml`, en push y pull_request a `main` y `develop`:
- Job `api` (working-directory `services/api`): instalar uv, `uv sync`, `ruff check`, `ruff format --check`, `mypy src`, `pytest`, `lint-imports`.
- Job `contracts`: validar que todos los `packages/contracts/examples/*.json` cumplan `event.schema.json` (script Python con `jsonschema`, o `ajv-cli`).
- Jobs `desktop` y `web`: `npm ci && npm run lint && npm run build`, **solo si** existe su `package.json` (usa `if: hashFiles('apps/desktop/package.json') != ''`), para no romper el CI mientras los compañeros arrancan.
- Badge del CI en el README.

**Criterio:** el pipeline corre en verde en GitHub. Dame el enlace de la ejecución para la evidencia.

---

## Fase 5 — Cola real con Redis + RQ (≈ 1.5 h) · prepara TA-007 y la integración con IA

- `adapters/outbound/redis_queue/job_queue.py`: implementa `JobQueue` con RQ (`Queue("audio")` y `Queue("high")` para verificación facial), con `Retry(max=3)`.
- Selección por variable `JOB_QUEUE=memory|redis`.
- Prueba de integración que se salta automáticamente si no hay Redis disponible (`pytest.mark.skipif`).
- En `services/ai/`, deja **solo** un worker mínimo de ejemplo (`worker_stub.py`) que consume la cola `audio` e imprime el `event_id`, para demostrar el flujo de punta a punta. La lógica real de audio es de Pierreluiggi.
- Añade `ai-worker` al `docker-compose.yml` usando ese stub.

**Criterio:** con `docker compose up`, un POST de `speech_detected` aparece impreso en los logs del worker.

---

## Fase 6 — Integración con Supabase (≈ 1.5 h; la base ya está creada) · EN-006 parte

- Probar `EVENT_REPOSITORY=supabase` contra el proyecto de desarrollo (variables en `.env`, nunca en el repo).
- Endpoint `POST /api/v1/evidence/upload-url` que devuelve una URL firmada de subida a Storage (bucket `evidences`, ruta `{session_id}/{student_id}/{uuid}.jpg`) para que la app suba directo. Puerto `EvidenceStorage` + adaptador Supabase + versión en memoria.
- Pruebas con el adaptador en memoria.

---

## Entregables y evidencia de la semana (para `docs/evidencias/semana-05/hector/` y Notion)

1. Captura del árbol del repositorio y enlace al repo.
2. Captura de Swagger con el POST de un evento respondiendo 201.
3. Captura del pipeline de GitHub Actions en verde (incluida la prueba de arquitectura).
4. Captura de los logs del worker recibiendo un `speech_detected`.
5. Lista de PRs revisados de los compañeros.

Al terminar cada fase, dame: (a) qué se hizo, (b) cómo probarlo en 3 comandos, (c) el texto de evidencia para Notion con el código de la tarea y las horas aproximadas.
