# ADR-0008 — El sistema aloja sus propios exámenes; sin integración con LMS

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-10-03 |
| **Decide** | Silva Vega, Héctor (Project Manager) |

## Contexto

El proyecto podría integrarse con Blackboard o Canvas por LTI y supervisar los exámenes que ya
existen ahí. Es lo que hacen los productos comerciales como Sumadi. Pero LTI 1.3 exige registro de
herramienta, claves y un administrador del LMS que nos dé acceso a una instancia real, y no tenemos
ninguna de las tres cosas.

## Decisión

**El sistema aloja sus propios exámenes.** Tiene sus tablas `questions` y `question_options`, su
pantalla de creación y su pantalla de rendición.

La única concesión a la interoperabilidad es **importar QTI 2.1**: se sube un `.zip`, se leen las
preguntas y se crean las filas. Nada más.

**No se implementa LTI** ni sincronización de notas con ningún LMS.

## Alternativas consideradas

- **Integración LTI 1.3 con Blackboard/Canvas.** Es lo correcto para un producto real, pero depende
  de que un administrador de LMS nos habilite una instancia. Es un bloqueo que no controlamos, y el
  semestre termina en la semana 15.
- **Raspar el LMS o un complemento de navegador.** Frágil y poco honesto técnicamente.
- **Solo importar QTI sin alojar exámenes.** No tendríamos dónde mostrarle la pregunta al estudiante,
  y sin la pregunta en curso no hay con qué comparar la transcripción, que es el núcleo de la
  detección de IA por voz.

## Consecuencias

**A favor:** controlamos el flujo completo de punta a punta y podemos demostrarlo sin depender de
nadie; tenemos el `question_id` y el enunciado en el momento exacto en que el estudiante responde,
que es **requisito** del módulo de detección de IA por voz; la importación QTI cubre el caso real de
un docente que ya tiene su banco de preguntas.

**En contra:** no es adoptable tal cual por una universidad que ya vive en su LMS; hay que construir
editor de exámenes y rendición, que es trabajo que no aporta al diferencial del proyecto; las notas se
quedan en nuestro sistema. La puerta queda abierta: el modelo de datos no impide añadir LTI después.
