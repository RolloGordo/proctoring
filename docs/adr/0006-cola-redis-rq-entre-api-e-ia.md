# ADR-0006 — Cola Redis + RQ entre la API y el servicio de IA

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-10-03 |
| **Decide** | Silva Vega, Héctor (Project Manager) |

## Contexto

Transcribir un fragmento de audio y clasificar si hay voz sintética tarda segundos. Si eso pasa
dentro de la petición HTTP, el cliente del estudiante se queda esperando, la API se bloquea y un pico
de eventos la tumba. Hace falta desacoplar, pero el presupuesto de infraestructura es cero y el
presupuesto de latencia de la alerta son 10 s.

## Decisión

**Redis + RQ** como cola entre la API principal y el servicio de IA.

- La API expone un puerto `JobQueue` con `enqueue_audio_analysis(event_id)`.
- El caso de uso `RegisterEvent` encola cuando el evento es `speech_detected`, y responde 201 de
  inmediato sin esperar el análisis.
- Dos colas por prioridad: `audio` para el análisis de audio y `high` para la verificación facial,
  que sí tiene un usuario esperando (P90 < 500 ms).
- `Retry(max=3)` en los trabajos.
- Selección por variable de entorno: `JOB_QUEUE=memory|redis`. En memoria para pruebas y para
  desarrollo sin Redis; Redis en Docker y en producción (Upstash, plan gratuito).

En la cola solo viaja el `event_id`. El audio y las capturas se leen desde Storage.

## Alternativas consideradas

- **Celery.** Más potente y con más opciones de planificación, pero mucha configuración para lo que
  necesitamos.
- **Tareas en segundo plano de FastAPI (`BackgroundTasks`).** Cero infraestructura, pero corren en el
  mismo proceso: no aíslan la CPU pesada, no sobreviven a un reinicio y no escalan a otra máquina,
  que es justo el motivo de separar el servicio de IA (ADR-0001).
- **`pg_cron` o colas dentro de PostgreSQL.** Un servicio menos, pero PostgreSQL haciendo de cola de
  trabajos con reintentos es forzarlo, y el plan gratuito no quiere ese tráfico.
- **Cloud Tasks / SQS.** Bien resuelto, pero nos ata a un proveedor de pago.

## Consecuencias

**A favor:** la API responde en milisegundos aunque el análisis tarde segundos; un pico de eventos
se acumula en la cola en lugar de tumbar el servicio; el servicio de IA escala aparte (el motivo de
separarlo); Redis ya está en `docker-compose.yml` y el adaptador en memoria mantiene las pruebas
rápidas y sin dependencias.

**En contra:** una pieza más que desplegar y vigilar; el flujo deja de ser síncrono, así que hay que
pensar en trabajos perdidos y en idempotencia; en el plan gratuito de Upstash hay límite de comandos.
Mitigación: el `worker_stub.py` prueba el camino de punta a punta desde el primer día, y la prueba de
integración de la cola se salta sola si no hay Redis.
