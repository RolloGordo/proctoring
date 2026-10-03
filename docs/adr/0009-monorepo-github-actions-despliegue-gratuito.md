# ADR-0009 — Monorepo con GitHub Actions; despliegue en Vercel, Render y Hugging Face Spaces

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-10-03 |
| **Decide** | Silva Vega, Héctor (Project Manager) |

## Contexto

Cuatro integrantes, cuatro áreas técnicas (API, Electron, IA, base de datos y visión) y un contrato
de evento que las tres primeras tienen que respetar a la vez. Hay que decidir si va todo en un
repositorio o en varios, y dónde se despliega con presupuesto cero.

El docente evalúa el trabajo **individual** por commits, así que la trazabilidad por persona importa
tanto como la estructura.

## Decisión

**Un solo repositorio (monorepo)** con `apps/`, `services/`, `packages/`, `supabase/`, `specs/` y
`docs/`. El contrato compartido vive en `packages/contracts/event.schema.json` y es la única fuente de
verdad para la app, la API y el servicio de IA.

**CI en GitHub Actions** (`.github/workflows/ci.yml`), en cada push y pull request a `main` y
`develop`: lint, formato, tipos, pruebas y la **prueba de arquitectura** (`lint-imports`). Los
trabajos de `apps/web` y `apps/desktop` se saltan solos mientras no exista su `package.json`, para que
el CI no esté rojo mientras los compañeros arrancan.

`main` protegida (solo por pull request), `develop` de integración, ramas
`feat/<codigo-backlog>-<descripcion>`, commits en Conventional Commits.

**Despliegue, todo en planes gratuitos:** web en Vercel, API en Render, servicio de IA en Hugging Face
Spaces (Docker, que tolera imágenes grandes con modelos), Redis en Upstash, base de datos en Supabase
Cloud, e instalador de la app de escritorio en GitHub Releases.

## Alternativas consideradas

- **Un repositorio por componente.** Cada integrante con su espacio, pero el contrato de evento se
  duplicaría en tres sitios y se desincronizaría en la primera semana. También partiría el historial
  justo cuando la evaluación depende de verlo entero.
- **Monorepo con Nx o Turborepo.** Buena caché y buen grafo de tareas, pero está pensado para
  JavaScript y la mitad del proyecto es Python; la configuración costaría más de lo que ahorra.
- **Todo el despliegue en una sola plataforma.** Más simple, pero ninguna capa gratuita aguanta a la
  vez una web estática, una API y un contenedor con modelos de varios cientos de megabytes.

## Consecuencias

**A favor:** un `git clone` y los cuatro tienen el proyecto completo; un cambio en el contrato se ve
en el mismo pull request que los tres consumidores; el CI corre todo junto, así que una ruptura entre
componentes aparece al instante; cada plataforma de despliegue recibe el tipo de carga para la que su
capa gratuita está pensada.

**En contra:** el CI corre trabajos que no cambiaron (aceptable a esta escala, y mitigado con
`hashFiles`); los permisos son de todo o nada, así que no se puede dar acceso parcial; cuatro
plataformas de despliegue son cuatro paneles y cuatro juegos de secretos que mantener.
