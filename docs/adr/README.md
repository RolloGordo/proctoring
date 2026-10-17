# Decisiones de arquitectura (ADR)

Un archivo por decisión, en orden. Formato fijo: **Contexto**, **Decisión**, **Alternativas
consideradas**, **Consecuencias**. Las consecuencias incluyen siempre lo que perdemos, no solo lo
que ganamos — un ADR que solo tiene ventajas es publicidad, no una decisión.

Un ADR no se edita cuando cambiamos de opinión: se escribe uno nuevo que lo **sustituye**, y el
viejo pasa a estado `Sustituida por ADR-XXXX`. El historial es el valor.

| ADR | Decisión | Estado |
|---|---|---|
| [0001](0001-hexagonal-dos-servicios-backend.md) | Arquitectura hexagonal con dos servicios backend (API e IA) | Aceptada |
| [0002](0002-docente-web-estudiante-electron.md) | Docente en web, estudiante en app de escritorio Electron | Aceptada |
| [0003](0003-supabase-datos-auth-storage-realtime.md) | Supabase para datos, autenticación, almacenamiento y tiempo real | Aceptada |
| [0004](0004-deteccion-liviana-cliente-sin-video-continuo.md) | Detección liviana en el cliente, pesada en el servidor, sin video continuo | Aceptada |
| [0005](0005-python-en-todo-el-backend.md) | Python en todo el backend | Aceptada |
| [0006](0006-cola-redis-rq-entre-api-e-ia.md) | Cola Redis + RQ entre la API y el servicio de IA | Aceptada |
| [0007](0007-alertas-por-supabase-realtime.md) | Alertas al docente por Supabase Realtime | Aceptada |
| [0008](0008-examenes-propios-sin-integracion-lms.md) | El sistema aloja sus propios exámenes; sin integración con LMS | Aceptada |
| [0009](0009-monorepo-github-actions-despliegue-gratuito.md) | Monorepo con GitHub Actions; Vercel, Render y Hugging Face Spaces | Aceptada |
| [0010](0010-autenticacion-en-la-api-no-en-rls.md) | La autorización del estudiante vive en la API, no en RLS | Aceptada |

## Las dos restricciones que explican casi todo

Si lees un solo ADR, que sea el [0004](0004-deteccion-liviana-cliente-sin-video-continuo.md). Dos
restricciones atraviesan el diseño completo:

1. **Presupuesto cero.** Todo en planes gratuitos u open source. Eso descarta proveedores de cola
   de pago, almacenamiento de video y cualquier GPU.
2. **No se envía video continuo.** De aquí salen la detección en el cliente, las URLs firmadas de
   Storage, la cola de trabajos y el contrato de evento. No es una optimización: es la decisión de
   la que dependen las demás.
