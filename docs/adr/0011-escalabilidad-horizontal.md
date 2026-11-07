# ADR-0011 — La API escala en horizontal: réplicas sin estado detrás de un balanceador

| | |
|---|---|
| **Estado** | Aceptada (arquitectura). La parte de producción queda **propuesta** (sección 4) |
| **Fecha** | 2026-11-06 |
| **Decide** | Silva Vega, Héctor (Project Manager) |

## Contexto

El Product Owner pidió que el sistema siga funcionando con cargas fuertes —un examen de 60
estudiantes, mil rindiendo a la vez en varios cursos— sin perder rendimiento, y que eso esté **probado
y justificado**. La web (Vercel) y la app de escritorio cargan archivos estáticos desde un CDN, así que
la carga real cae sobre la **API**: cada estudiante entra con su código, espera en la sala, guarda
respuestas, manda señales de supervisión y entrega.

Hasta ahora la API era una sola instancia y guardaba estado en su memoria: el límite de peticiones
contaba por proceso y, detrás de un proxy, todos los clientes anónimos parecían la misma IP.

## Decisión

**La API escala añadiendo réplicas idénticas y sin estado detrás de un balanceador.** Todo lo que deba
ser común a las réplicas vive fuera de ellas:

| Estado | Dónde |
|---|---|
| Datos, sesiones, eventos | Supabase (Postgres) |
| Cola de trabajos de IA | Redis (RQ) |
| Límite de peticiones | **Redis**: ventana deslizante atómica (Lua, reloj de Redis); `RATE_LIMIT_BACKEND=redis` |
| Identidad | El token (ES256, verificado por JWKS en cada réplica) |

Además:

- **IP real detrás del balanceador** (`TRUSTED_PROXIES`): se usa `X-Forwarded-For` solo si la petición
  viene de un proxy de confianza, y la última IP que añadió nuestro proxy. No se puede falsificar.
- **Procesos por réplica** con `WEB_CONCURRENCY` (uvicorn). Escalar dentro de una máquina y entre
  máquinas usa el mismo mecanismo.
- **Balanceo `least_conn`** (nginx en la prueba): una entrega tarda más que guardar una respuesta, y por
  turno las rápidas esperarían detrás de las lentas. Solo se reintenta en otra réplica lo que falló
  al conectar, nunca un POST que pudo llegar.
- **Optimizaciones que salieron de medir** (no de suponer): el rol del usuario se recuerda 60 s por
  proceso (era la primera de cuatro consultas seguidas), 40 conexiones reutilizables hacia Supabase
  (una por hilo), reintento cuando la conexión no llegó a abrirse, sondeo de la sala de espera con
  ±20 % de margen y Realtime filtrado por la fila del propio estudiante.

## Cómo se probó

Locust (`loadtests/`), con exámenes completos simulados contra **Supabase local** (las 46 migraciones)
y réplicas de 1 CPU y 512 MB detrás de nginx. Presupuestos: p95 < 500 ms por endpoint, entrega
< 1,5 s, errores < 1 %. Resultados completos en `docs/carga/informe-carga.pdf` (se entrega aparte) y
cifras clave aquí:

| Mil estudiantes a la vez | p50 | p95 | Errores |
|---|---:|---:|---:|
| 1 réplica | 3,9 s | 8,6 s | 0 de 25.134 |
| 2 réplicas | 460 ms | 2,5 s | 0 de 30.701 |
| 4 réplicas | 56 ms | 270 ms | 0 de 32.494 |

Con una réplica, su CPU estaba saturada y la base de datos tenía margen: el caso en que añadir réplicas
funciona, y funcionó. El CI repite el examen de 60 con 2 réplicas en cada PR a `main` que toque la API
(`.github/workflows/carga.yml`).

## 4. Producción (propuesta)

**El plan gratuito de Render no lo sostiene.** Su instancia gratuita tiene 0,1 CPU, no admite réplicas
y se duerme a los 15 minutos. Con una réplica limitada a 0,1 CPU, un solo examen de 60 estudiantes tuvo
un p95 de 10,0 s, y guardar una respuesta tardó 10,0 s.

Se propone desplegar **la misma pila probada** (nginx + réplicas + Redis) en una VM de **Oracle Cloud
Always Free**, la única opción gratuita sin cobro por uso con CPU suficiente, y dejar Render como
respaldo. Requiere verificar la cuenta con tarjeta (no cobra lo Always Free) y administrar el servidor.
Si el equipo no lo acepta, la API se queda en Render con el límite medido declarado y despertándola antes
de cada examen. Vercel (web) y Supabase (datos) no cambian.

**Estado (06/11/2026).** Oracle respondió «Out of host capacity» en São Paulo durante más de una hora
de reintentos automáticos (26 intentos, uno cada 2 minutos). Mientras no haya capacidad, producción
sigue en Render. Los archivos de Oracle quedan listos en `deploy/oci/`.

### 4.1 El worker de IA en Render: perfil `ligero`

La transcripción ahora es 100 % local (faster-whisper, trabajo de Pierreluiggi), y la imagen completa
(Whisper `small` + torch + insightface) necesita unos 1,7 GB. Render gratis da 512 MB. El Dockerfile de
`services/ai` tiene un perfil `ligero` (`PERFIL=ligero` en el panel de Render):

| Pieza | Completo | Ligero |
|---|---|---|
| Transcripción | Whisper `small` | Whisper `tiny` |
| Similitud con el enunciado | MiniLM con torch | el mismo MiniLM en ONNX int8, vocabulario es/en (57 MB), exportado al construir |
| Verificación facial | insightface | OpenCV YuNet + SFace (trabajo de Jesús) |
| torch / insightface en la imagen | sí | no |

Medido con la imagen ligera construida (1,29 GB), en un contenedor sin red y con `--memory 512m`,
cargando los tres modelos y transcribiendo una pregunta hablada de 5 s:

| CPU del contenedor | Carga de modelos | Transcripción | Pico de memoria |
|---|---|---|---|
| 1 CPU | 2,9 s | 2,3 s | 435 MiB |
| 0,1 CPU (Render gratis) | 24,0 s | 38,4 s | 435 MiB |

Cabe en 512 MB con unos 77 MiB de margen, y Whisper `tiny` transcribió la frase exacta (similitud 1,0).
El CI construye esta imagen en cada PR y carga los modelos sin red con `--memory 512m`.

Lo que cuesta: `tiny` se equivoca más que `small` con audio ruidoso, y **con los 0,1 CPU de Render la
alerta de IA por voz tarda unos 40 s, cuatro veces el objetivo de 10 s**. Con 1 CPU tarda 2,3 s. El
objetivo se cumple en local o en Oracle, no en el plan gratuito de Render, y así se reporta.

## Alternativas consideradas

- **Escalar en vertical** (una instancia más grande). Más simple, pero tiene techo y deja un único punto
  de fallo; el horizontal no impide crecer en vertical cada réplica.
- **Límite de peticiones en el balanceador** (nginx `limit_req`). Cuenta por IP, y en una universidad
  todos los estudiantes comparten IP de salida: castigaría a todos por uno. El límite por persona
  necesita leer el token, y eso lo hace la API.
- **Google Cloud Run** (escala solo). Exige cuenta de facturación y cobra lo que pase de la cuota.
- **JMeter** en lugar de Locust. Requiere Java y sus planes son XML; Locust es Python, como el backend,
  y cada prueba es código revisable.

## Consecuencias

- Añadir capacidad es configuración (número de réplicas, `WEB_CONCURRENCY`), no código.
- Redis pasa a ser necesario para el límite de peticiones con más de una réplica. Si cae, cada réplica
  cuenta por su lado y nadie se queda sin examen.
- El rol de una persona tarda hasta un minuto en cambiar tras ascenderla a docente.
- **Riesgos que esta prueba no cubre:** la base gratuita de Supabase (compartida; en la prueba tuvo la
  máquina entera), el límite de 200 conexiones de Realtime (la sala de espera sigue por sondeo) y la
  latencia de internet entre la API y Supabase.
