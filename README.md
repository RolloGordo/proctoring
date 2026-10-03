# Proctoring — Supervisión de exámenes remotos

> Taller Integrador 1 — Universidad Privada Antenor Orrego (UPAO)
> Product Owner / Portfolio Manager: Walter Cueva Chávez

Plataforma de proctoring que **aloja sus propios exámenes** (no se integra con Blackboard ni
Canvas) y supervisa al estudiante mientras los rinde. El sistema es un **auditor, no un juez**:
calcula un nivel de riesgo desglosado por señal y entrega evidencia; la decisión final la toma
el docente, con justificación obligatoria.

## Detecciones

| Señal | Dónde corre | Responsable |
|---|---|---|
| Verificación de identidad por rostro | cliente + API (InsightFace/ArcFace) | Jesús / Héctor |
| Pérdida de foco de ventana, monitores extra, procesos sospechosos | proceso main de Electron | Rider |
| Mirada fuera de pantalla, rostro ausente, persona adicional | renderer con MediaPipe | Jesús |
| **Consulta a un asistente de IA por voz** (diferencial) | cliente (VAD) + servicio de IA | Pierreluiggi |

La detección de IA por voz solo alerta si se cumplen **ambas** condiciones: la transcripción de
lo que el estudiante dice se parece al enunciado de la pregunta en curso **y** se detecta una
segunda voz sintética respondiendo. Leer en voz alta para concentrarse NO genera alerta.

## Metas medibles (SMART)

- 4 tipos de detección con accuracy ≥ 80 % y FPR < 20 % por módulo.
- Alerta de navegador/cámara al docente en < 5 s; alerta de IA por voz en < 10 s.
- Verificación facial P90 < 500 ms.
- Despliegue con CI/CD hasta la semana 15.

## Arquitectura

Monolito modular con **arquitectura hexagonal (puertos y adaptadores)** en la API principal, más
un **servicio de IA separado**, también hexagonal (escala distinto: CPU pesada y cola de trabajos).

```
App de escritorio (Electron)        Web del docente (React)
  detección local liviana              alertas en vivo
            |                                  ^
            | eventos JSON                     | Supabase Realtime
            v                                  |
      API principal (FastAPI, hexagonal)  -->  Supabase (PostgreSQL + Auth + Storage)
            |
            | Redis + RQ
            v
      Servicio de IA (FastAPI + workers RQ)
```

**No se envía video continuo.** Solo eventos, capturas y fragmentos de audio con habla. Las
capturas y el audio suben **directo a Storage** con URL firmada; a la API solo llega el evento.

Decisiones detalladas en [`docs/adr/`](docs/adr/).

## Estructura del repositorio

```
proctoring/
├── apps/
│   ├── web/                 # React + TS + Vite (docente y examen)      -> Rider / Jesús
│   │   └── spikes/vision/   # spike de visión por computadora           -> Jesús
│   └── desktop/             # Electron + TS (kiosco del estudiante)     -> Rider
│       ├── src/main/        # ventana, kiosco, protección, pantallas, procesos
│       ├── src/preload/     # API mínima vía contextBridge
│       └── src/renderer/
├── services/
│   ├── api/                 # API principal hexagonal                   -> Héctor
│   │   ├── src/proctoring_api/
│   │   │   ├── domain/              # entidades, value objects, reglas puras. SIN frameworks
│   │   │   ├── application/
│   │   │   │   ├── ports/           # interfaces (Protocol): repos, storage, cola, notificador
│   │   │   │   └── use_cases/       # un caso de uso por archivo
│   │   │   ├── adapters/
│   │   │   │   ├── inbound/http/    # routers FastAPI, schemas Pydantic
│   │   │   │   └── outbound/        # memory/, supabase/, redis_queue/
│   │   │   ├── config.py            # settings (pydantic-settings)
│   │   │   └── main.py              # composición de dependencias y app FastAPI
│   │   └── tests/ (unit/, integration/)
│   └── ai/                  # servicio de IA, misma estructura           -> Pierreluiggi
│       └── spikes/
├── packages/
│   └── contracts/           # event.schema.json y ejemplos compartidos
├── supabase/
│   └── migrations/          # SQL en inglés, snake_case (ya aplicado)    -> Héctor / Jesús
├── specs/                   # SPEC-001..009: requisitos, diseño, tareas
├── docs/
│   ├── adr/                 # decisiones de arquitectura
│   └── evidencias/          # capturas y videos por semana e integrante
├── .github/workflows/       # CI/CD
├── docker-compose.yml
└── .env.example
```

## Requisitos

| Herramienta | Versión | Para qué |
|---|---|---|
| [Python](https://www.python.org/) | 3.12 | API e IA |
| [uv](https://docs.astral.sh/uv/) | >= 0.4 | gestor de paquetes de Python |
| [Node.js](https://nodejs.org/) | 20 LTS o superior | web y app de escritorio |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | reciente | levantar api + redis |
| [Git](https://git-scm.com/) | 2.40+ | control de versiones |

Si no tienes Python 3.12, `uv` lo descarga por ti:

```bash
uv python install 3.12
```

## Levantar todo en local

### Opción A — Docker (recomendada: API + Redis + worker de IA)

```bash
cp .env.example .env && docker compose up --build
```

En PowerShell el primer comando es `Copy-Item .env.example .env`.

- API: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs>
- Redis: `localhost:6379`

### Opción B — Solo la API, sin Docker

```bash
cd services/api && uv sync && uv run uvicorn proctoring_api.main:create_app --factory --reload --port 8000
```

Arranca con adaptadores en memoria, así que **no necesita Supabase ni Redis** para
funcionar: `uv sync` y listo.

### Comprobar que funciona

```bash
curl http://localhost:8000/health
```

Responde `{"status":"ok","env":"local","version":"0.1.0","auth":"disabled"}`. Ese `auth` es
intencional: en local la autenticación viene desactivada para que los clientes puedan mandar
eventos antes de tener su pantalla de login. **La API se niega a arrancar sin autenticación en
cualquier entorno que no sea `local` o `test`**, y si la variable no existe, la autenticación queda
activada.

```bash
curl -X POST http://localhost:8000/api/v1/events -H "Content-Type: application/json" --data-binary @packages/contracts/examples/focus_lost.json
```

### Web del docente

```bash
cd apps/web && npm install && npm run dev
```

## Calidad: lo que exige el CI

Desde `services/api`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest && uv run lint-imports
```

`lint-imports` verifica la **regla de dependencias hexagonal** (`adapters → application → domain`,
nunca al revés) y que `domain` y `application` no importen ningún framework. Si esa prueba falla,
el PR no entra.

## Flujo de ramas

- `main` — protegida, solo por Pull Request. Es lo que se despliega.
- `develop` — rama de integración. Todo PR apunta aquí.
- `feat/<codigo-backlog>-<descripcion>` — por ejemplo `feat/EN-005-auth-roles`.
- También `fix/`, `test/`, `docs/`, `chore/`, `ci/`.

Commits en [Conventional Commits](https://www.conventionalcommits.org/) y con el código del
backlog cuando aplique:

```
feat(EN-005): add register event use case
test(EN-005): cover speech_detected enqueue
```

## Definición de terminado

Una tarea está terminada cuando cumple **todo** esto:

1. Código en un Pull Request hacia `develop`.
2. CI en verde (lint, formato, tipos, pruebas y prueba de arquitectura).
3. Prueba automatizada que cubre el criterio de aceptación de la tarea.
4. README o docstring actualizado.
5. Evidencia (captura o video) en `docs/evidencias/semana-XX/<integrante>/`.

## Convenciones

- **Código en inglés** (identificadores, tablas, columnas, endpoints, mensajes de commit).
  **Interfaz de usuario en español.** Base de datos en `snake_case`.
- Python: `ruff` (lint y formato), `mypy` estricto razonable, `pytest`, tipado en todo.
  Entidades con `dataclass(frozen=True, slots=True)`.
- TypeScript: modo estricto, ESLint + Prettier.
- Secretos: nunca en el repo. En local `.env`; en CI, GitHub Secrets.

## Equipo

| Integrante | Rol Scrum | Área técnica |
|---|---|---|
| Silva Vega, Héctor | Project Manager | Arquitectura, backend, infraestructura, CI/CD |
| Rodriguez Ruiz, Rider | Scrum Master | App de escritorio Electron, frontend |
| Zevallos Bocanegra, Pierreluiggi | Desarrollo | Servicio de IA de audio, importación QTI |
| Limay Capristan, Jesús | Desarrollo | Visión computacional; mantenimiento de la base de datos |

## Lo que NO se hace

- No grabar ni enviar video continuo.
- No anular exámenes automáticamente (decide el docente).
- No integrarse con Blackboard/Canvas (se importa QTI, nada más).
- No mezclar lógica de negocio en routers ni en adaptadores.
- No subir secretos, datasets pesados ni modelos al repo.
