# SPEC-007 — Detección de visión (mirada, rostro ausente, persona adicional)

| | |
|---|---|
| **Responsable** | Jesús (Limay Capristan) |
| **Epica** | EN-008 |
| **Estado** | borrador |

## Historia de usuario

Durante el examen el sistema detecta ausencia del rostro, presencia de otra persona y mirada fuera de pantalla.

## Criterios de aceptacion

1. Sin rostro por mas de 5 s continuos genera un unico `face_absent` con su `duration_ms`.
2. Mas de un rostro en cuadro genera `extra_person`.
3. Cabeza girada mas de 25 grados por mas de 3 s continuos genera un unico `gaze_away`; un giro breve no genera nada.
4. Cada evento guarda una captura del canvas, subida directo a Storage con URL firmada.
5. Accuracy >= 80 % y FPR < 20 % por deteccion, con la tabla de umbrales probados como respaldo.
6. No se graba ni se envia video continuo.

## Pendiente

El contenido completo (historias desglosadas y trazabilidad a tareas del backlog) se
pega desde Notion, que es la fuente de verdad del Product Backlog. Falta ademas
`diseno.md` y `tareas.md` en esta misma carpeta.
