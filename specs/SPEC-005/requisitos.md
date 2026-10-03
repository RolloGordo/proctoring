# SPEC-005 — Verificación de identidad por rostro

| | |
|---|---|
| **Responsable** | Jesús (Limay Capristan) |
| **Epica** | EN-008 |
| **Estado** | borrador |

## Historia de usuario

Antes de empezar el examen el sistema confirma que quien esta frente a la camara es el estudiante matriculado.

## Criterios de aceptacion

1. El estudiante registra un rostro de referencia que se guarda en `reference_faces`.
2. Al ingresar se compara el rostro en vivo con la referencia y se escribe un evento `identity_check`.
3. La verificacion responde con P90 por debajo de 500 ms (medido y documentado).
4. Accuracy >= 80 % y FPR < 20 % sobre el conjunto de prueba del equipo.
5. Si falla, el estudiante queda en estado pendiente y el docente lo admite a mano desde la sala de espera.

## Pendiente

El contenido completo (historias desglosadas y trazabilidad a tareas del backlog) se
pega desde Notion, que es la fuente de verdad del Product Backlog. Falta ademas
`diseno.md` y `tareas.md` en esta misma carpeta.
