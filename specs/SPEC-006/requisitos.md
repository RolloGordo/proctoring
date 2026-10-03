# SPEC-006 — Detección de entorno (foco, monitores, procesos)

| | |
|---|---|
| **Responsable** | Rider (Rodriguez Ruiz) |
| **Epica** | EN-002 |
| **Estado** | borrador |

## Historia de usuario

El sistema detecta que el estudiante salio de la ventana, conecto otro monitor o abrio una aplicacion de control remoto.

## Criterios de aceptacion

1. Salir de la ventana y volver genera un unico evento `focus_lost` con `duration_ms` correcto (+/- 200 ms).
2. Se detecta tanto el cambio de pestana como el cambio a otra ventana de Windows.
3. Conectar un segundo monitor genera `extra_display` en menos de 5 s, con el detalle en `metadata`.
4. Abrir Zoom, AnyDesk, TeamViewer, OBS o Discord genera `suspicious_process` en menos de 15 s.
5. El sistema no cierra ni mata ningun proceso: solo registra.

## Pendiente

El contenido completo (historias desglosadas y trazabilidad a tareas del backlog) se
pega desde Notion, que es la fuente de verdad del Product Backlog. Falta ademas
`diseno.md` y `tareas.md` en esta misma carpeta.
