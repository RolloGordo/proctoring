# SPEC-004 — Rendición del examen y app de escritorio

| | |
|---|---|
| **Responsable** | Rider (Rodriguez Ruiz) |
| **Epica** | EN-002 |
| **Estado** | borrador |

## Historia de usuario

El estudiante rinde el examen dentro de una ventana de escritorio en modo kiosco y protegida.

## Criterios de aceptacion

1. La ventana abre en `kiosk: true` con `setContentProtection(true)`: no sale en capturas ni en screen share.
2. `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false` y CSP restrictiva (verificable en el codigo).
3. Copiar y pegar y las herramientas de desarrollo quedan bloqueados mientras el examen esta activo.
4. Las respuestas se guardan en `answers` a medida que el estudiante avanza, no solo al final.

## Pendiente

El contenido completo (historias desglosadas y trazabilidad a tareas del backlog) se
pega desde Notion, que es la fuente de verdad del Product Backlog. Falta ademas
`diseno.md` y `tareas.md` en esta misma carpeta.
