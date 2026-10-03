# ADR-0007 — Alertas al docente por Supabase Realtime

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-10-03 |
| **Decide** | Silva Vega, Héctor (Project Manager) |

## Contexto

El docente tiene que ver las alertas mientras el examen ocurre, no al terminar. El presupuesto de
latencia es **menos de 5 s** para navegador y cámara, y **menos de 10 s** para IA por voz. Y puede
haber varios estudiantes en la misma sesión.

## Decisión

**Supabase Realtime.** La web del docente se suscribe a las inserciones de la tabla `alerts`
filtradas por `session_id`. Cuando la API o un worker insertan una alerta, llega al navegador por el
canal de Realtime, sin que la API tenga que notificar a nadie.

La notificación está igualmente detrás de un puerto en la aplicación, así que el caso de uso no sabe
que existe Supabase.

## Alternativas consideradas

- **Preguntar cada pocos segundos (polling).** Simple y funciona, pero gasta peticiones de todos
  los docentes abiertos todo el tiempo y la latencia es, en el mejor caso, el intervalo.
- **WebSocket propio en la API.** Control total, pero hay que mantener estado de conexiones en un
  servicio que se despliega en el plan gratuito de Render, donde los reinicios y el arranque en frío
  son habituales.
- **Server-Sent Events desde la API.** Más sencillo que WebSocket, pero el mismo problema de
  conexiones abiertas en un servicio que duerme.

## Consecuencias

**A favor:** latencia muy por debajo del presupuesto; cero infraestructura adicional (ya elegimos
Supabase en ADR-0003); la fuente de verdad es la tabla, así que si el docente recarga la página ve
exactamente lo mismo, sin un estado paralelo que pueda desincronizarse.

**En contra:** el navegador del docente habla directo con Supabase, así que la seguridad depende por
completo de que RLS esté bien escrito (un estudiante no puede suscribirse a las alertas de otro);
atamos una función visible del producto al proveedor; el plan gratuito limita conexiones concurrentes
de Realtime, suficiente para la demo pero no para un despliegue real.
