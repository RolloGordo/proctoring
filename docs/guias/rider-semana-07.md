# Rider · semana 7

**Entrega: sábado 17/10.** Esa semana el sistema tiene que estar desplegado y
funcionando en público.

Esta semana te toca lo que más se nota: **que el sistema se entienda**. Hasta
ahora hemos construido mucho y cuidado poco cómo se usa. El docente tiene que
poder crear un examen sin que nadie le explique, y el estudiante tiene que saber
en todo momento qué hacer.

## Antes de nada

```bash
git checkout develop && git pull
```

```bash
npm install --prefix apps/web
```

```bash
docker compose up -d --build api
```

El `npm install` importa esta semana: cambió el `package.json` de la web.

Lo tuyo de la semana 6 ya está dentro: HU-023 y HU-015 fusionadas en el PR #37.

---

## 1. Que crear y calificar un examen se entienda

Es lo más abierto de tu semana y por eso va primero: **úsalo tú como si no lo
hubieras hecho** y anota dónde te trabas. Esa lista es tu tarea.

Puntos que ya sabemos que molestan:

- **Crear un examen** pide muchos datos de golpe y no se ve claro qué es
  obligatorio y qué no.
- **El banco de preguntas** y las preguntas del examen son dos caminos distintos
  para lo mismo, y no se explica cuándo conviene cada uno. Héctor tiene dudas
  sobre eso, así que si a él no le queda claro, a un docente de verdad menos.
- **Editar** funciona, pero las tres acciones —editar, cancelar, borrar— están
  juntas y no se distingue a simple vista cuál es la peligrosa.
- **La calificación** se calcula sola, pero el docente no ve de dónde sale la
  nota ni puede corregir lo de desarrollo cómodamente.

No hace falta rehacer nada. La mayoría se arregla con textos de ayuda, orden y
agrupación.

---

## 2. Vistas del estudiante

El estudiante tiene muy poco: entra, rinde y ve su nota. Falta lo obvio:

- Sus exámenes, los que vienen y los que ya rindió.
- El detalle de un examen rendido: qué respondió, qué nota sacó, qué se le marcó.
- Qué se le va a supervisar **antes** de aceptar. Algo hay en la sala, pero
  conviene que sea claro: es la pantalla del consentimiento y es lo que hace
  honesto al sistema.

---

## 3. Descargar la app desde la portada

La portada (`apps/web/src/pages/Portada.tsx`) no tiene de dónde bajar la
aplicación. Hace falta un apartado visible con:

- el botón de descarga, apuntando al **GitHub Release**
- para qué sirve y por qué hace falta (el examen se rinde ahí, no en el navegador)
- los requisitos: Windows, y qué permisos va a pedir

Esto depende de que exista el Release. **Publícalo primero** — era tu
EN-011/TA-060 de la semana pasada y `gh release list` sigue vacío.

---

## 4. El examen solo se rinde en la aplicación

Hoy se puede rendir desde el navegador. Cuando la web esté publicada, cualquiera
con el enlace podría saltarse la supervisión de escritorio entera: sin kiosco,
sin detección de procesos, sin monitores, sin protección de captura.

**Ya tienes el mecanismo hecho.** En `AccesoExamen.tsx`, línea 11:

```ts
const enEscritorio = window.api !== undefined
```

`window.api` solo existe dentro de Electron, porque lo expone el preload. En un
navegador normal es `undefined`.

Lo que falta es usarlo para **bloquear `/examen/:id/rendir`** (y probablemente
también `/sala`) cuando no estás en la app. Y que el mensaje sea útil: no un
error, sino «este examen se rinde en la aplicación» con el botón de descarga al
lado. Enlaza con el punto 3.

> Ojo con no pasarte: el docente **sí** usa la web para todo. Bloquea las rutas
> del estudiante que rinde, no la web entera.

---

## 5. La app dice «Panel del docente»

En `apps/web/index.html`:

```html
<title>Proctoring — Panel del docente</title>
```

Ese título es global, así que la ventana de la aplicación —donde hay un
estudiante rindiendo— dice «Panel del docente». Queda raro y el estudiante lo ve.

Ponlo por ruta, o déjalo neutro.

---

## 6. El flujo del estudiante al rendir

Ahora va de una pregunta en una. Lo que falta para que no dé inseguridad:

- Ver **en qué punto va** sin tener que contar: algo tipo «3 de 10», qué
  respondió y qué no.
- **Cuánto tiempo le queda.** Hoy no lo ve en ninguna parte, y en un examen con
  tiempo eso es lo primero que uno busca.
- Confirmar antes de entregar, diciéndole cuántas lleva sin responder.
- Que si se le cae la conexión, lo sepa y sepa que lo suyo está guardado.

Y una que te va a tocar coordinar: Jesús y Pierreluiggi van a meter **avisos en
vivo** durante el examen. Esos avisos conviven con tu pantalla. Habla con ellos
en la daily para que no te monten una caja encima del enunciado.

---

## Lo que arrastras de la semana 6

**Las mediciones (DO-004 + TA-015)** y **el Release (EN-011 + TA-060)** siguen
sin cerrar. La receta paso a paso está en
[`rider-paso-a-paso.md`](./rider-paso-a-paso.md) — las mediciones son 40 minutos
con la app sola, sin levantar nada más.

El Release además **bloquea el punto 3** de esta semana. Hazlo primero.

> Y lo del error en la otra computadora («falta conexión a internet»): **no es
> culpa tuya y no lo persigas**. `web.ts` apunta a `http://localhost:5173` cuando
> no hay variable de entorno, y en un `.exe` instalado esa variable no existe. Se
> arregla solo cuando Héctor despliegue la web y el instalador se construya
> apuntando ahí.

---

## Antes de subir

```bash
cd apps/web && npm run lint && npm test && npm run build
```

```bash
cd apps/desktop && npm run lint && npm run typecheck && npm test && npm run build
```

Rama `feat/<codigo>-<descripcion>`, commits en inglés con el código del backlog,
PR hacia `develop`.
