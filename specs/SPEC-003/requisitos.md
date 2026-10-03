# SPEC-003 — Banco de preguntas e importación QTI

| | |
|---|---|
| **Responsable** | Pierreluiggi (Zevallos Bocanegra) |
| **Epica** | EN-007 |
| **Estado** | borrador |

## Historia de usuario

El sistema aloja sus propias preguntas y permite importarlas desde un paquete QTI 2.1.

## Criterios de aceptacion

1. Se importa un `.zip` QTI 2.1 y se crean filas en `questions` y `question_options` con el orden correcto.
2. Las preguntas se muestran al estudiante una por una, en el orden de `position`.
3. El enunciado de la pregunta en curso queda disponible para el modulo de deteccion de IA por voz (es con lo que se compara la transcripcion).
4. No hay integracion LTI con Blackboard ni Canvas: solo importacion de archivos.

## Pendiente

El contenido completo (historias desglosadas y trazabilidad a tareas del backlog) se
pega desde Notion, que es la fuente de verdad del Product Backlog. Falta ademas
`diseno.md` y `tareas.md` en esta misma carpeta.
