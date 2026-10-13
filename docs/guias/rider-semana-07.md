# Rider · semana 7

**Lunes 12/10 → viernes 16/10.** Revisión del sprint el sábado 17.

Esta semana te toca lo que más se nota: **que el sistema se entienda**. Hemos
construido mucho y cuidado poco cómo se usa.

**12 tareas, 16 puntos.** Vas cargado porque arrastras cuatro de la semana 6,
pero son baratas: medir y publicar, no construir. Si no entra todo, lo primero
que se mueve a la semana 8 es `HU-029` o `TA-077` — avisa y se mueve, no te lo
guardes.

## La regla de esta semana

**No des por funcionando nada que no hayas visto funcionar.** Tus dos pantallas
de la semana pasada (HU-023 y HU-015) están fusionadas y pasan pruebas, pero
**nadie las ha visto conectar de verdad**. Tú mismo lo escribiste en tu resumen y
tenías razón. Esta semana se prueban.

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

---

# Primero lo que arrastras

## TA-015 + DO-004 · Las mediciones · 2 pt

Siguen sin tomarse: los cinco criterios de `apps/desktop/README.md` están sin
marcar. **Nadie más puede hacerlo**: necesita Windows, cronómetro, segundo
monitor y Zoom.

La receta paso a paso está en [`rider-paso-a-paso.md`](./rider-paso-a-paso.md).
**Son 40 minutos con la app sola**, sin levantar nada más — eso era lo que te
había confundido.

## EN-011 + TA-060 · El instalador y el Release · 2 pt

`gh release list` sigue vacío. Y **esto bloquea `HU-028`** de esta semana (la
descarga desde la portada), así que hazlo pronto.

> **El error de la otra computadora no es culpa tuya.** `web.ts` apunta a
> `http://localhost:5173` cuando no hay variable de entorno, y en un `.exe`
> instalado esa variable no existe. Habla con Héctor **antes** de publicar: hay
> que construir el instalador apuntando a la web desplegada, o publicarás uno
> roto.

---

# Lo nuevo

## HU-026 · Que crear un examen y calificarlo se entienda · 2 pt

Es lo más abierto de tu semana y por eso va primero: **úsalo como si no lo
hubieras construido tú** y anota dónde te trabas. Esa lista es tu tarea.

Lo que ya sabemos que molesta:

- **Crear examen** pide muchos datos de golpe y no se ve qué es obligatorio.
- **Banco y preguntas propias** son dos caminos para lo mismo y no se explica
  cuándo conviene cada uno. *Si a Héctor no le queda claro, a un docente de
  verdad menos.*
- **Editar, cancelar y borrar** están juntos y no se distingue cuál es el
  peligroso.
- **La calificación** se calcula sola, pero el docente no ve de dónde sale la
  nota ni corrige lo de desarrollo cómodamente.

No hace falta rehacer nada. La mayoría se arregla con textos de ayuda, orden y
agrupación.

- [ ] Un docente que no sea del equipo crea un examen **sin ayuda**. Ese es el criterio

## HU-027 · Más vistas para el estudiante · 2 pt

Hoy solo puede entrar, rendir y ver su nota.

- [ ] Sus exámenes: los que vienen y los que ya rindió
- [ ] Detalle de uno rendido: qué respondió, qué nota sacó, qué se le marcó
- [ ] Antes de aceptar, qué se le va a supervisar — **es la pantalla del consentimiento y es lo que hace honesto al sistema**
- [ ] Probado con un estudiante que tenga varios exámenes, no solo uno

## HU-028 · Descargar la app desde la portada · 1 pt

`apps/web/src/pages/Portada.tsx` no tiene de dónde bajarla.

- [ ] Botón de descarga apuntando al GitHub Release
- [ ] Por qué hace falta: el examen se rinde ahí, no en el navegador
- [ ] Requisitos y permisos que va a pedir
- [ ] **Probado descargando desde otra máquina**

Depende de `TA-060`. Publica el Release primero.

## TA-076 · El examen solo se rinde en la aplicación · 1 pt

Hoy se puede rendir desde el navegador. Con la web publicada, cualquiera con el
enlace se saltaría la supervisión entera: sin kiosco, sin procesos, sin
monitores, sin protección de captura.

**Ya tienes el mecanismo.** En `AccesoExamen.tsx`, línea 11:

```ts
const enEscritorio = window.api !== undefined
```

`window.api` solo existe dentro de Electron, porque lo expone el preload.

- [ ] Bloqueadas las rutas de rendir y sala fuera de la aplicación
- [ ] El mensaje **no es un error**: dice que se rinde en la app y ofrece la descarga
- [ ] **El docente sigue usando la web para todo lo suyo** — bloquea las rutas del estudiante, no la web entera
- [ ] Probado en navegador normal y dentro de la app

## HU-029 · Mejorar el flujo al rendir · 2 pt

El examen va de una pregunta en una, pero al estudiante le falta saber dónde
está.

- [ ] **Cuánto tiempo le queda.** Hoy no lo ve en ninguna parte, y en un examen con tiempo es lo primero que uno busca
- [ ] En qué pregunta va y cuántas quedan sin responder
- [ ] Al entregar, confirmar diciendo cuántas van sin responder
- [ ] Si se cae la conexión, que lo sepa y sepa que lo suyo está guardado
- [ ] **Probado cortando la red a mitad de examen**

> Jesús y Pierreluiggi van a meter **avisos en vivo** durante el examen
> (`HU-025`). Conviven con tu pantalla: háblalo con ellos en la daily para que no
> te monten una caja encima del enunciado.

## TA-077 · «Panel del docente» en la app · 1 pt

En `apps/web/index.html`:

```html
<title>Proctoring — Panel del docente</title>
```

Ese título es global, así que la ventana donde hay un estudiante rindiendo dice
«Panel del docente». El estudiante lo ve.

- [ ] Título por ruta, o neutro
- [ ] Revisados los demás textos que suponen que quien mira es el docente
- [ ] Comprobado **dentro de la aplicación**, no solo en el navegador

---

## TA-063 · Prueba de humo: un examen entero · 2 pt

**Es la tarea que más riesgo quita de toda la semana**, y una de las tres de las
que depende el despliegue.

Un examen de principio a fin en una máquina real, con cámara, micrófono y segundo
monitor conectados, con los cuatro módulos activos.

- [ ] De principio a fin **sin que nadie intervenga a mitad**
- [ ] Los eventos de los cuatro módulos llegan al docente
- [ ] Probar también lo tuyo de la semana pasada: que la **cuadrícula de cámaras** conecte y que la **evidencia del caso** se abra
- [ ] Grabado

Hasta que esta esté en verde, no publicamos nada.

## TA-014 · Cámara y habla dentro de la ventana · 1 pt

La política de permisos de Electron ya concede cámara y micrófono solo al origen
del examen (`permisos.ts`). Lo que falta es **comprobar que funciona**: que
dentro de la app no aparezca un diálogo de permiso, y que fuera de ese origen se
deniegue.

- [ ] Comprobado dentro de la app y con una navegación a otro origen

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
