# ADR-0004 — Detección liviana en el cliente, pesada en el servidor, sin video continuo

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-10-03 |
| **Decide** | Silva Vega, Héctor (Project Manager) |

## Contexto

La tentación obvia es grabar la sesión completa y analizarla en el servidor. Eso haría el análisis
fácil, pero rompe tres cosas a la vez: el ancho de banda del estudiante (una hora de video son
cientos de megabytes), el presupuesto de almacenamiento (cero) y la privacidad.

El docente ya señaló en la reunión del 03/10/2026 que el coste computacional del envío en tiempo real
de video, capturas y audio es el riesgo principal del proyecto.

## Decisión

**No se graba ni se envía video continuo.** Nunca.

- En el **cliente** corre solo detección liviana: MediaPipe Face Landmarker sobre el `<video>` y
  Silero VAD sobre el micrófono. El video y el audio no salen de la máquina del estudiante.
- Cuando una condición se cumple el tiempo suficiente, el cliente emite **un evento** (JSON) y, si
  hace falta, **una captura** o **un fragmento de audio con habla**.
- Las capturas y el audio suben **directo a Storage** con una URL firmada que entrega la API. A la
  API solo le llega el evento, con el `evidence_path`.
- Lo caro (transcripción, similitud, voz sintética, verificación facial) ocurre en el **servidor**,
  fuera de la petición, por cola.

Todo evento queda ligado a `session_id`, `student_id`, `question_id` y hora.

Corolario de implementación: cada detección necesita **histéresis** (un temporizador por condición)
para emitir un evento con su `duration_ms` en lugar de uno por frame.

## Alternativas consideradas

- **Grabar todo y analizar después.** Inviable por ancho de banda, almacenamiento y privacidad.
- **Transmitir video en vivo al servidor para analizarlo ahí.** Mismo problema de ancho de banda,
  más un coste de CPU por estudiante concurrente que ningún plan gratuito aguanta.
- **Todo el análisis en el cliente, incluida la IA de audio.** La transcripción y el clasificador de
  voz sintética competirían con MediaPipe por la CPU del estudiante y harían el examen injugable en
  una laptop modesta.

## Consecuencias

**A favor:** el tráfico es de kilobytes, no de megabytes; cumple el presupuesto de almacenamiento;
es defendible en privacidad, que en un sistema de vigilancia académica no es un detalle menor; la API
no se bloquea nunca esperando a un modelo.

**En contra:** si el cliente falla o lo manipulan, perdemos la señal y no hay grabación a la que
recurrir después; no se puede re-analizar el pasado con un modelo mejor; cada detección hay que
calibrarla con cuidado porque no hay red de seguridad. Lo asumimos: encaja con que el sistema sea
**auditor y no juez**, y con la meta de FPR < 20 %.
