# SPEC-001 — Autenticación y roles

| | |
|---|---|
| **Responsable** | Héctor (Silva Vega) |
| **Epica** | EN-005 |
| **Estado** | borrador |

## Historia de usuario

El docente y el estudiante inician sesion con Supabase Auth y el sistema los distingue por rol.

## Criterios de aceptacion

1. Un usuario con `profiles.role = 'teacher'` entra al panel del docente y un `student` no puede entrar a ese panel (403).
2. El JWT de Supabase viaja en `Authorization: Bearer` y la API lo valida en cada endpoint protegido.
3. Un token invalido o vencido responde 401 con un mensaje claro.

## Pendiente

El contenido completo (historias desglosadas y trazabilidad a tareas del backlog) se
pega desde Notion, que es la fuente de verdad del Product Backlog. Falta ademas
`diseno.md` y `tareas.md` en esta misma carpeta.
