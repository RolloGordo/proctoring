# SPEC-002 — Gestión de sesiones de examen

| | |
|---|---|
| **Responsable** | Héctor (Silva Vega) |
| **Epica** | EN-005 |
| **Estado** | borrador |

## Historia de usuario

El docente crea una sesion de examen, elige que modulos de deteccion se activan y obtiene un codigo de acceso.

## Criterios de aceptacion

1. El docente crea una sesion con titulo, fecha de inicio y duracion, y recibe un `access_code` unico.
2. El docente activa o desactiva cada modulo de deteccion y queda guardado en `session_modules`.
3. Un estudiante entra con el `access_code` y queda registrado en `session_participants`.
4. Un estudiante no puede entrar a una sesion que ya termino.

## Pendiente

El contenido completo (historias desglosadas y trazabilidad a tareas del backlog) se
pega desde Notion, que es la fuente de verdad del Product Backlog. Falta ademas
`diseno.md` y `tareas.md` en esta misma carpeta.
