# `specs` — Especificaciones SPEC-001 .. SPEC-009

Una carpeta por especificación. Cada una tiene tres archivos:

| Archivo | Contenido |
|---|---|
| `requisitos.md` | historias de usuario y criterios de aceptación verificables |
| `diseno.md` | cómo se resuelve: entidades, puertos, endpoints, pantallas |
| `tareas.md` | desglose en tareas con su código de backlog y estimación |

Por ahora solo está `requisitos.md` con el título, el responsable y el criterio medible. El
contenido completo se pega desde Notion, que es la fuente de verdad del Product Backlog.

## Índice

| SPEC | Título | Responsable | Épica |
|---|---|---|---|
| [SPEC-001](SPEC-001/requisitos.md) | Autenticación y roles | Héctor | EN-005 |
| [SPEC-002](SPEC-002/requisitos.md) | Gestión de sesiones de examen | Héctor | EN-005 |
| [SPEC-003](SPEC-003/requisitos.md) | Banco de preguntas e importación QTI | Pierreluiggi | EN-007 |
| [SPEC-004](SPEC-004/requisitos.md) | Rendición del examen y app de escritorio | Rider | EN-002 |
| [SPEC-005](SPEC-005/requisitos.md) | Verificación de identidad por rostro | Jesús | EN-008 |
| [SPEC-006](SPEC-006/requisitos.md) | Detección de entorno (foco, monitores, procesos) | Rider | EN-002 |
| [SPEC-007](SPEC-007/requisitos.md) | Detección de visión (mirada, rostro, persona extra) | Jesús | EN-008 |
| [SPEC-008](SPEC-008/requisitos.md) | Detección de asistente de IA por voz | Pierreluiggi | EN-007 |
| [SPEC-009](SPEC-009/requisitos.md) | Riesgo, alertas en vivo y decisión del docente | Héctor | EN-009 |

## Trazabilidad

Cada criterio de aceptación de un `requisitos.md` tiene que poder señalar la prueba automatizada
que lo cubre. Es el punto 3 de la Definición de terminado del [README](../README.md) y lo que
convierte "lo investigué" en "lo demostré".
