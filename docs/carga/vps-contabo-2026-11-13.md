# Capacidad medida en el VPS de Contabo (13/11/2026)

Prueba pedida en la revisión del 07/11: cuánto aguanta **el servidor que pagamos** (Contabo Cloud VPS 6:
6 vCPU compartidos, 12 GB), no el PC de desarrollo. Misma herramienta y mismos usuarios virtuales que
el ADR-0011 (`loadtests/`, Locust).

## Cómo se montó

Todo dentro del mismo VPS, a propósito:

```
Locust (fijado al núcleo 5) ──► nginx ──► api × N (1 CPU, 512 MB c/u) ──► Supabase local
                                              └──► Redis                  (Kong, PostgREST,
                                                                           Postgres, Auth)
```

- **Supabase local, no el de producción.** Los mil usuarios de prueba no pueden ir a la base real, y
  firmar sus tokens exige la clave de pruebas. Con `supabase db reset` se aplicaron las 22 migraciones.
- **Los puertos del entorno de carga no se ven desde internet.** Docker se salta `ufw`, así que se
  añadieron reglas en `DOCKER-USER` (IPv4 e IPv6) para 8080 y 54320-54329 antes de levantarlo.
- **La producción siguió encendida** (3 réplicas de la API, 2 workers de IA, Redis, Dokploy): la prueba
  compite con ella, igual que lo haría un examen real.
- **Locust corre en el mismo VPS**, fijado a un núcleo. Mide la capacidad del servidor, sin la latencia
  de internet de cada estudiante.

## Resultados

Cada estudiante entra con el código, espera en la sala, responde unos 4 minutos y entrega en el último
minuto, como en un examen real. p95 en milisegundos.

| Corrida | Estudiantes | Réplicas | Errores | p95 total | Ingreso | Guardar respuesta | Entrega |
|---|---:|---:|---:|---:|---:|---:|---:|
| Examen de 60 | 60 | 1 | 0 % | 1.600 | 2.300 | 270 | 430 |
| Examen de 60 | 60 | 3 | 0 % | 1.000 | 870 | 1.100 | 900 |
| 5 exámenes | 300 | 3 | 0,02 % | 3.000 | 3.300 | 3.900 | 470 |
| 9 exámenes | 540 | 3 | 0,01 % | 10.000 | 10.000 | 12.000 | 7.100 |
| 17 exámenes | 1.020 | 3 | 0,01 % | 14.000 | 13.000 | 17.000 | 13.000 |
| 17 exámenes | 1.020 | 4 | 0,12 % | 9.900 | 8.600 | 12.000 | 11.000 |

CPU media durante las corridas grandes (100 % = un núcleo):

| | 300 | 540 | 1.020 (3 réplicas) | 1.020 (4 réplicas) |
|---|---:|---:|---:|---:|
| API (todas las réplicas) | 115 | 191 | 243 | 237 |
| PostgREST + Kong + Postgres | 112 | 158 | 166 | 167 |

Con 1.020 estudiantes el servidor entero estaba entre el 86 % y el 96 % de CPU (`vmstat`), sin robo
de CPU del hipervisor.

## Lo que se concluye

1. **Un examen de 60, el caso que pide el proyecto, va holgado.** Sin errores, guardar una respuesta en
   p95 de 270 ms y entregar en 430 ms. En Render gratis las dos operaciones tardaban 10 s.
2. **El sistema no se cae: se pone lento.** Con mil estudiantes hubo 0,01 %–0,12 % de errores. Pasados
   los ~300 a la vez, las respuestas pasan de los 3 s.
3. **Más réplicas ayudan hasta que se acaba la máquina.** De 3 a 4 réplicas, el p95 de mil bajó de 14 s
   a 9,9 s. Más allá no hay a dónde crecer en un solo servidor de 6 vCPU: el escalado horizontal
   siguiente es un segundo nodo (Dokploy lo admite), no más réplicas en el mismo.
4. **El ingreso es lo más caro.** Entrar con el código y matricularse cuesta 5 a 10 veces más que guardar
   una respuesta, y todos entran a la vez. Es el primer punto a optimizar.
5. **En producción la base no vive en el VPS.** Está en Supabase Cloud, así que el VPS se ahorra el
   trabajo de PostgREST, Kong y Postgres (≈ 1,1–1,7 núcleos medidos aquí). Esta prueba es, por eso, el
   caso pesimista para el VPS. Pero en producción manda otro techo: **Supabase gratis admite 200
   conexiones Realtime**, y cada estudiante abre al menos una.

## Criterio de aceptación propuesto

Con este servidor:

- **Garantizado:** un examen de 60 con p95 < 500 ms al guardar y entregar, y 0 errores. Cumplido.
- **Soportado:** hasta ~300 estudiantes a la vez repartidos en varios exámenes, con p95 < 4 s y menos
  del 0,1 % de errores. Cumplido.
- **Fuera de alcance con un solo VPS:** 1.000 a la vez con p95 < 1 s. Requiere un segundo nodo y un plan
  de Supabase con más conexiones Realtime.

Datos crudos (CSV de Locust y CPU por contenedor): `vps-carga.tgz`, fuera del repositorio.
