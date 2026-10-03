# ADR-0005 — Python en todo el backend

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-10-03 |
| **Decide** | Silva Vega, Héctor (Project Manager) |

## Contexto

Hay que elegir el lenguaje de la API principal. El servicio de IA prácticamente se elige solo:
faster-whisper, sentence-transformers e InsightFace son del ecosistema de Python. La pregunta real es
si la API principal va en Python también o en Node/TypeScript, que es lo que el equipo usa en el
frontend y en Electron.

## Decisión

**Python 3.12 + FastAPI** en los dos servicios backend, con `uv` como gestor de paquetes.

Herramientas comunes: `ruff` (lint y formato), `mypy` en modo estricto razonable, `pytest`,
`import-linter` para la regla hexagonal. Tipado en todo. Entidades con
`dataclass(frozen=True, slots=True)`.

TypeScript se queda en el frontend y en Electron, donde no hay alternativa.

## Alternativas consideradas

- **API en Node + TypeScript (NestJS o Fastify).** Un solo lenguaje con el frontend, pero habría
  que cruzar el límite a Python igual para la IA, con serialización y un salto de proceso de por
  medio en el camino más caliente.
- **Go para la API.** Mejor rendimiento y binarios de un solo archivo, pero nadie en el equipo lo
  conoce y el semestre es corto.
- **Django + DRF.** Trae ORM y panel de administración, pero su estructura empuja hacia el patrón
  MVC y pelea con la arquitectura hexagonal que ya decidimos (ADR-0001).

## Consecuencias

**A favor:** las dependencias de IA son nativas; un solo juego de herramientas de calidad para los
dos servicios, así que el CI y las convenciones se escriben una vez; FastAPI da OpenAPI y Swagger
gratis, que es justo la evidencia visible que el docente pidió; `Protocol` encaja de forma natural
con los puertos de la arquitectura.

**En contra:** el equipo cambia de lenguaje al pasar del frontend al backend; Python es más lento que
Go o Node en concurrencia pura (irrelevante a nuestra escala: los eventos son pequeños y lo pesado
está en la cola); hay que mantener los tipos del contrato en dos ecosistemas, y por eso el contrato
vive en `packages/contracts` como JSON Schema y no como clases de Python.
