# Semana 7 · cerrar el Sprint 1 de verdad

**Lunes 12/10 → viernes 16/10.** Revisión del sprint el sábado 17.

Cada uno tiene su archivo:

- [Héctor](./hector-semana-07.md) — revisión, pruebas, correcciones y preparar el despliegue
- [Rider](./rider-semana-07.md) — que el sistema se entienda y se use
- [Jesús](./jesus-semana-07.md) — módulo de cámara
- [Pierreluiggi](./pierreluiggi-semana-07.md) — módulo de micrófono y voz

Backlog actualizado: `docs/Backlog_v6_real.csv`.

---

## La regla de esta semana

**No des por funcionando nada que no hayas visto funcionar.**

Tenemos mucho código que pasa pruebas automatizadas y que nadie ha visto correr
contra el sistema real. Eso no es lo mismo, y confundirlo es cómo se llega a una
demo que se rompe delante del profesor.

Esta semana, una tarea no está hecha cuando compila. Está hecha cuando:

1. La probaste **contra Supabase real**, con sesión iniciada, como la usaría una
   persona.
2. La probaste **cuando falla**: sin permiso, sin red, con mala luz, con el
   micrófono silenciado.
3. Tienes **una captura o un vídeo** de que funciona.

Si al probar encuentras que falta algo, eso también es tu tarea. «Mejorar y
añadir» es parte del trabajo, no una tarea aparte.

---

## El despliegue se prepara, no se publica

El profesor pidió el sistema desplegado en las semanas 7, 11 y 15. Pero publicar
algo que no está probado es enseñar una demo rota, así que esta semana:

- **TA-078** deja todo listo: cuentas, variables, CORS, CI/CD.
- **EN-012** (publicar) está en la semana 8 y **depende** de que las tres pruebas
  de aceptación estén en verde: `TA-063` (prueba de humo), `TA-064` (worker de
  audio) y `TA-065` (verificación facial).

Si las tres llegan a verde esta semana, se publica el viernes y llegamos a lo
que pidió. Si no, se publica en cuanto lleguen y **se dice por qué** — eso es
mejor que una demo que se cae.

---

## Lo que arreglé en el backlog

**Tres tareas decían «Sprint 2» con fechas del Sprint 1.** `HU-011`, `SP-010` y
`HU-015` tenían fechas 05/10→09/10 y Semana 6, pero el sprint puesto era el 2.
Cualquier conteo por sprint salía mal. Corregido.

**Lo que no se cerró en la semana 6 pasó a la 7**, con nota de que viene de
atrás: `DO-004`, `TA-015`, `EN-011`, `TA-060` (Rider) y `TA-062` (Pierreluiggi).
Dejarlas en la semana 6 habría escondido la deuda.

**Las ceremonias y la revisión del backlog pasan al Scrum Master.** El profesor
fue explícito: el que lleva la semana revisa el backlog **junto con** su equipo,
no cada uno por su lado.

---

## Lo que el profesor pidió y no es código

Esto es lo único donde dijo claramente que estamos mal, y no se arregla
programando.

**Las ceremonias.** Esperaba seis y encontró una, con «estudiante uno, uno, uno»
copiado y pegado. Pide **dos dailies por semana**, grabadas, **el vídeo en
Drive** (no en Notion, por el espacio) y **los acuerdos escritos en Notion** con
nombres reales.

**Los títulos del backlog.** «La integración con Supabase no es una historia de
usuario». Una historia necesita interacción de una persona; lo demás es
habilitador o tarea técnica.

---

## Decisiones tomadas

**Deepgram sustituye a faster-whisper** (`TA-070`), en el worker de
`services/ai`, no en el navegador. El profesor lo pidió por el peso del
instalador; el motivo real es otro y vale la pena saberlo: el modelo **no viaja
en el `.exe`**, corre en el servidor. Lo que pasa es que 1 GB no entra cómodo en
un Space gratuito, y sin eso no hay servicio de IA desplegado.

**El estudiante ve las alertas durante el examen, con detalle** (`HU-025`). Antes
las veía al terminar. Ahora se le dice la señal concreta: «se detectó una segunda
persona», no un genérico. Es lo más transparente y lo más defendible: el sistema
audita, no caza.

---

## Antes de empezar, los cuatro

```bash
git checkout develop && git pull
```

```bash
npm install --prefix apps/web
```

```bash
docker compose up -d --build api
```

El `npm install` importa esta semana: cambió el `package.json` de la web. El
`--build` del contenedor nunca es opcional — la API no recarga sola y el error
parece del código recién bajado.

---

## Carga de la semana

| Quién | Tareas | Puntos |
|---|---|---|
| Rider | 12 | 16 |
| Pierreluiggi | 7 | 12 |
| Jesús | 6 | 10 |
| Héctor | 6 | 9 |

Rider va cargado porque arrastra cuatro tareas de la semana 6, aunque son
baratas (medir y publicar, no construir). Si no entra todo, lo primero que se
mueve a la semana 8 es `HU-029` o `TA-077`.
