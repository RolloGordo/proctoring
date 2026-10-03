# SPEC-009 — Riesgo, alertas en vivo y decisión del docente

| | |
|---|---|
| **Responsable** | Héctor (Silva Vega) |
| **Epica** | EN-009 |
| **Estado** | borrador |

## Historia de usuario

El sistema calcula riesgo desglosado por senal, avisa al docente en vivo y registra su decision justificada.

## Criterios de aceptacion

1. El riesgo se guarda en `risk_scores` **desglosado por senal**, no como un numero unico.
2. Las alertas llegan al docente por Supabase Realtime en menos de 5 s (menos de 10 s para IA por voz).
3. La pantalla de revision muestra cada senal con su evidencia y la hora.
4. El docente registra `confirmed`, `dismissed` o `retake` y la `justification` es obligatoria.
5. El sistema **nunca** anula un examen por su cuenta.
6. Los eventos son inmutables: se insertan y se leen, no se editan ni se borran.

## Pendiente

El contenido completo (historias desglosadas y trazabilidad a tareas del backlog) se
pega desde Notion, que es la fuente de verdad del Product Backlog. Falta ademas
`diseno.md` y `tareas.md` en esta misma carpeta.
