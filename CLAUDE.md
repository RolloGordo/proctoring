# CLAUDE.md — Sistema Proctoring (Taller Integrador 1, UPAO)

Este archivo es el contexto permanente del repositorio. Léelo completo antes de cualquier tarea y respétalo siempre.

## 1. Qué es el proyecto

Plataforma de proctoring para exámenes remotos. El sistema **aloja sus propios exámenes** (no se integra con Blackboard ni Canvas) y supervisa al estudiante mientras los rinde:

- verifica su identidad por rostro al ingresar;
- detecta pérdida de foco de la ventana, monitores adicionales, procesos sospechosos (Zoom, AnyDesk, TeamViewer, OBS, máquinas virtuales);
- detecta mirada fuera de pantalla, rostro ausente y persona adicional;
- **diferencial del proyecto:** detecta la consulta a un asistente de IA por voz. Compara la transcripción de lo que el estudiante dice en voz alta con el enunciado de la pregunta en curso y detecta una segunda voz sintética que responde. Solo hay alerta si se cumplen ambas condiciones (leer en voz alta para concentrarse NO debe generar alerta).

El sistema es un **auditor, no un juez**: calcula un nivel de riesgo desglosado por señal y entrega evidencia; la decisión final la toma el docente, con justificación obligatoria.

**Usuarios:** docente (web) y estudiante (app de escritorio).

**Metas medibles (objetivo SMART):** 4 tipos de detección (identidad, foco de ventana, mirada, IA por voz) con accuracy ≥ 80 % y tasa de falsos positivos (FPR) < 20 % por módulo; alerta de navegador/cámara al docente en < 5 s; alerta de IA por voz en < 10 s; verificación facial P90 < 500 ms; despliegue con CI/CD hasta la semana 15.

## 2. Equipo y responsabilidades (no hagas el trabajo de otro integrante)

| Integrante | Rol Scrum | Área técnica | Carpeta principal |
|---|---|---|---|
| Silva Vega, Héctor | Project Manager | Arquitectura, backend (API hexagonal), infraestructura, CI/CD, riesgo y decisiones | `services/api`, `packages/contracts`, `.github/`, `docker-compose.yml`, `docs/` |
| Rodriguez Ruiz, Rider | Scrum Master | App de escritorio Electron (kiosco, foco, monitores, procesos, protección), frontend | `apps/desktop`, `apps/web` (UI) |
| Zevallos Bocanegra, Pierreluiggi | Desarrollo | Servicio de IA de audio (transcripción, similitud, voz sintética), importación QTI | `services/ai` |
| Limay Capristan, Jesús | Desarrollo | Base de datos (migraciones SQL), visión computacional (rostro, mirada) | `supabase/migrations`, `apps/web/spikes/vision` |

Product Owner y Portfolio Manager: docente Walter Cueva Chávez. El docente evalúa el trabajo **individual** por commits y evidencias: cuando trabajes para Héctor, no implementes los spikes de los demás; solo deja su carpeta preparada con un README.

## 3. Arquitectura

**Estilo:** monolito modular con **arquitectura hexagonal (puertos y adaptadores)** en la API principal + un **servicio de IA separado**, también hexagonal. Se separa la IA porque escala distinto (CPU pesada) y usa una cola.

**Clientes:**
- **Web del docente** (React + TypeScript + Vite): crear sesiones, elegir módulos, sala de espera, alertas en vivo, resultados, revisión de caso, decisión justificada.
- **App de escritorio del estudiante** (Electron + TypeScript) que carga la misma web en la ruta del examen, en una ventana en modo kiosco con `setContentProtection(true)`. El proceso main de Electron detecta monitores (`screen`), procesos y foco; el renderer (web) corre MediaPipe y la detección de habla (Silero VAD). Seguridad Electron: `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`, CSP restrictiva; la web solo usa funciones expuestas por el preload vía `contextBridge`.

**Backend:**
- **API principal** — Python 3.12 + FastAPI, hexagonal. Sesiones, exámenes, eventos, riesgo, decisiones. Genera URLs firmadas de Storage y encola trabajos.
- **Cola** — Redis + RQ. Desacopla el análisis de audio y la verificación facial.
- **Servicio de IA** — Python + FastAPI + workers RQ. faster-whisper (transcripción en español), sentence-transformers multilingüe (similitud con el enunciado), clasificador de voz sintética, InsightFace/ArcFace (verificación facial).

**Supabase:** PostgreSQL (datos + RLS), Auth (login y roles con JWT), Storage (capturas y audio con URLs firmadas), Realtime (alertas en vivo al docente).

**Reglas de flujo:**
- Detección liviana en el cliente; lo pesado en el servidor. **No se envía video continuo**: solo eventos, capturas y fragmentos de audio con habla.
- La app sube capturas y audio **directo a Storage** con URL firmada; a la API solo le envía el evento (JSON).
- Todo evento queda ligado a `session_id`, `student_id`, `question_id` y hora.
- Las alertas llegan al docente por Supabase Realtime (cambio en tabla).

**Ambientes:**
- **Local:** `docker compose up` (api, ai, redis) + Supabase CLI o un proyecto Supabase gratuito de desarrollo; web con Vite (`localhost:5173`); API `localhost:8000`; IA `localhost:8001`; Redis `localhost:6379`.
- **Producción:** web en Vercel, API en Render, IA en Hugging Face Spaces (Docker), Redis administrado (Upstash), Supabase Cloud, instalador de la app en GitHub Releases. Todo en planes gratuitos.

## 4. Estructura del repositorio (monorepo)

```
proctoring/
├── apps/
│   ├── web/                 # React + TS + Vite (docente y examen)
│   │   └── spikes/vision/   # spike de visión (Jesús)
│   └── desktop/             # Electron + TS (Rider)
│       ├── src/main/        # proceso principal: ventana, kiosco, protección, pantallas, procesos, protocolo
│       ├── src/preload/     # API mínima vía contextBridge
│       └── src/renderer/
├── services/
│   ├── api/                 # API principal, hexagonal (Héctor)
│   │   ├── src/proctoring_api/
│   │   │   ├── domain/              # entidades, value objects, reglas puras. SIN frameworks
│   │   │   ├── application/
│   │   │   │   ├── ports/           # interfaces (Protocol/ABC): repositorios, almacenamiento, cola, notificador
│   │   │   │   └── use_cases/       # un caso de uso por archivo
│   │   │   ├── adapters/
│   │   │   │   ├── inbound/http/    # routers FastAPI, schemas Pydantic de request/response
│   │   │   │   └── outbound/        # memory/, supabase/, redis_queue/
│   │   │   ├── config.py            # settings (pydantic-settings)
│   │   │   └── main.py              # composición de dependencias y app FastAPI
│   │   ├── tests/ (unit/, integration/)
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── ai/                  # servicio de IA (Pierreluiggi); misma estructura hexagonal
│       └── spikes/
├── packages/
│   └── contracts/           # event.schema.json y tipos compartidos
├── supabase/
│   └── migrations/          # SQL (Jesús). Tablas y columnas en inglés, snake_case
├── specs/                   # SPEC-001..009: requisitos.md, diseno.md, tareas.md
├── docs/
│   ├── adr/                 # decisiones de arquitectura
│   └── evidencias/          # capturas y videos por semana e integrante
├── .github/workflows/       # CI/CD
├── docker-compose.yml
├── .env.example
└── README.md
```

## 5. Convenciones obligatorias

- **Idioma del código:** identificadores, tablas, columnas, endpoints y mensajes de commit **en inglés**. Base de datos en **snake_case** (pedido explícito del docente). La interfaz de usuario en español.
- **Regla de dependencias hexagonal:** `adapters → application → domain`, nunca al revés. `domain` y `application` no importan `fastapi`, `pydantic` (salvo en adapters), `supabase`, `redis`, `rq`, `sqlalchemy`, `httpx`. Se verifica con **import-linter** en el CI.
- **Python:** 3.12, gestor `uv`, `ruff` (lint y formato), `mypy` en modo estricto razonable, `pytest`. Tipado en todo. Entidades con `dataclass(frozen=True)` o `slots=True`.
- **TypeScript:** estricto, ESLint + Prettier.
- **Git:** `main` protegida (solo por PR), `develop` de integración, ramas `feat/<codigo-backlog>-<descripcion>` (ej. `feat/EN-005-auth-roles`). Commits en Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `ci:`) y con el código del backlog cuando aplique.
- **Secretos:** nunca en el repo. `.env.example` con variables vacías. En CI, GitHub Secrets.
- **Pruebas:** todo caso de uso tiene prueba unitaria con adaptadores en memoria; todo endpoint, prueba con `TestClient`.
- **Definición de terminado:** código en PR a `develop`, CI en verde, prueba que cubre el criterio de aceptación, README o docstring actualizado y evidencia (captura o video) en `docs/evidencias/`.

## 6. Contrato de evento (compartido por app, API e IA)

```json
{
  "session_id": "uuid",
  "student_id": "uuid",
  "question_id": "uuid | null",
  "event_type": "focus_lost | gaze_away | face_absent | extra_person | extra_display | suspicious_process | screen_share | speech_detected | identity_check",
  "started_at": "ISO-8601 UTC",
  "duration_ms": 0,
  "metadata": {},
  "evidence_path": "storage path | null"
}
```

## 7. Modelo de datos de referencia (lo implementa Jesús en `supabase/migrations`)

`profiles` (id = auth user, full_name, role: teacher|student) · `courses` · `exam_sessions` (teacher_id, title, starts_at, duration_minutes, access_code, preset, settings jsonb) · `session_modules` · `questions` (session_id, statement, question_type, points, position) · `question_options` · `session_participants` (session_id, student_id, verification_status, consent_at) · `answers` · `events` (session_id, student_id, question_id, event_type, started_at, duration_ms, metadata, evidence_path) · `audio_analyses` (event_id, transcript, similarity, synthetic_score) · `alerts` (event_id, severity, reason) · `risk_scores` · `decisions` (session_id, student_id, teacher_id, decision: confirmed|dismissed|retake, justification NOT NULL, decided_at) · `reference_faces`. La API debe usar exactamente estos nombres.

## 8. Lo que NO se hace

- No grabar ni enviar video continuo.
- No anular exámenes automáticamente (decide el docente).
- No integrarse con Blackboard/Canvas (se importa QTI, nada más).
- No mezclar lógica de negocio en routers ni en adaptadores.
- No subir secretos, datasets pesados ni modelos al repo (usar `.gitignore`).
