# Pruebas de carga

Comprueban que la API aguanta exámenes reales —uno de 60 estudiantes, y mil a la
vez repartidos en varios cursos— y que **escala en horizontal**: más réplicas
detrás de un balanceador, más capacidad. Decisión y resultados en
[ADR-0011](../docs/adr/0011-escalabilidad-horizontal.md) y
[docs/carga/](../docs/carga/).

La herramienta es [Locust](https://locust.io): Python, como el resto del backend,
y cada prueba es código revisable en un PR.

## Qué se monta

```
Locust ──► nginx (balanceador, :8080) ──► api × N réplicas ──► Supabase local
                                              │                 (Postgres, PostgREST,
                                              └──► Redis          Auth, Storage, Realtime)
                                                  (cola y límite de peticiones compartido)
```

- **Supabase local** (`supabase start`), nunca el proyecto de la nube: mil
  usuarios de prueba no deben acabar en la base real, y los límites del plan
  gratuito distorsionarían la medida. `preparar.py` se niega a correr si la URL
  no es local.
- **Cada réplica con 1 CPU y 512 MB**, como una instancia pequeña. Sin techo, una
  sola réplica usaría los núcleos de toda la máquina y no se vería el efecto de
  añadir réplicas.
- **Tokens ES256** firmados con la clave local, como los que emite Auth: la API
  los verifica por JWKS igual que en producción.

## Qué hace cada usuario virtual

Copia al cliente de verdad, no un bucle a todo gas:

| Quién | Qué | Ritmo |
|---|---|---|
| Estudiante | Entra con el código, se matricula y consiente | una vez, todos casi a la vez |
| | Sala de espera: pregunta si ya lo admitieron | cada 10 s (±20 % con `SONDEO_CON_MARGEN=1`) |
| | Descarga las preguntas | al ser admitido |
| | Guarda respuestas / manda una señal de supervisión | cada 8-15 s (70 % / 25 %) |
| | Entrega | todos en el último minuto: el pico |
| Docente (uno por examen) | Refresca la sala, admite a quien espera, mira alertas | cada 5 s |

## Correr

Una vez:

```bash
cd loadtests && uv sync
uv run python preparar.py clave      # clave ES256 de pruebas, fuera de git
npx -y supabase@2 start -x studio,imgproxy,edge-runtime,logflare,vector,supavisor,mailpit,postgres-meta
uv run python preparar.py env        # claves de Supabase local para las réplicas
docker compose -f docker-compose.carga.yml -p carga up -d --build
```

Cada corrida (escala, siembra datos nuevos, mide recursos y carga):

```bash
uv run python correr.py --nombre examen60-2r --examenes 1  --por-examen 60 --replicas 2
uv run python correr.py --nombre mil-4r      --examenes 17 --por-examen 60 --replicas 4
```

Deja en `resultados/` el CSV y el HTML de Locust y el CSV de CPU y memoria por
contenedor. Sale con código 1 si se rompe un presupuesto:

| Presupuesto | Valor | Variable |
|---|---|---|
| p95 por endpoint | 500 ms | `UMBRAL_P95_MS` |
| p95 de la entrega (califica) | 1500 ms | `UMBRAL_ENTREGA_P95_MS` |
| Errores | < 1 % | `UMBRAL_ERRORES` |

El CI corre el examen de 60 con dos réplicas en los PR a `main` que tocan la API
(`.github/workflows/carga.yml`).

**Ritmo de ingreso.** `--ingreso-por-segundo` (50 por defecto) es cuántos usuarios
arranca Locust por segundo. Para mil estudiantes en 17 cursos son unos 3 por
curso y segundo. En el CI, con un solo curso, se usa 20: los 60 entran en 3 s.
Con 50 entraban en 1,2 s, que en un aula no pasa (cada uno inicia sesión y teclea
el código dentro de la tolerancia de ingreso, que es de minutos), y el p95 de
«ingreso» medía sobre todo la cola de ese segundo: 400-560 ms con mínimos de
40 ms (18/11). 20/s sigue siendo mucho más duro que lo real. El presupuesto de
500 ms no se tocó: lo que bajó el p95 fue leer el examen con sus módulos en una
sola consulta y no leerlo en cada sondeo de la sala de espera (EN-034).

| CI, examen de 60, p95 | Antes (50/s) | EN-034 (50/s) | EN-034 (20/s, CI) |
|---|---:|---:|---:|
| ingreso: código | 500 ms | 360 ms | 130 ms |
| ingreso: matrícula | 530 ms | 270 ms | 98 ms |

Al terminar: `docker compose -f docker-compose.carga.yml -p carga down` y
`npx -y supabase@2 stop`.
