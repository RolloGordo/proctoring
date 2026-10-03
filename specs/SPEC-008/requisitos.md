# SPEC-008 — Detección de asistente de IA por voz

| | |
|---|---|
| **Responsable** | Pierreluiggi (Zevallos Bocanegra) |
| **Epica** | EN-007 |
| **Estado** | borrador |

## Historia de usuario

El diferencial del proyecto: detectar que el estudiante le esta preguntando a un asistente de IA por voz.

## Criterios de aceptacion

1. El cliente detecta habla con VAD y sube solo el fragmento con voz, no audio continuo.
2. El servicio transcribe en espanol y calcula la similitud entre la transcripcion y el enunciado de la pregunta en curso.
3. Se detecta la presencia de una segunda voz sintetica respondiendo.
4. **Solo hay alerta si se cumplen las dos condiciones.** Leer la pregunta en voz alta sin respuesta sintetica NO genera alerta (caso negativo obligatorio en las pruebas).
5. La alerta llega al docente en menos de 10 s desde que termina el fragmento.
6. El resultado queda en `audio_analyses` con `transcript`, `similarity` y `synthetic_score`.
7. FPR < 20 % sobre el conjunto de prueba, con los umbrales documentados.

## Pendiente

El contenido completo (historias desglosadas y trazabilidad a tareas del backlog) se
pega desde Notion, que es la fuente de verdad del Product Backlog. Falta ademas
`diseno.md` y `tareas.md` en esta misma carpeta.
