# Rider · correcciones del primer examen real

Héctor rindió un examen completo contra el **sistema desplegado** el 16/10 y
anotó 19 cosas. Estas son las tuyas.

> **Contexto si pegas esto en un chat de IA:** plataforma de proctoring para
> exámenes remotos (UPAO, Taller Integrador 1). Monorepo: `apps/web` (React +
> TypeScript + Vite), `apps/desktop` (Electron), `services/api` (FastAPI
> hexagonal). **Código, identificadores y commits en inglés; la interfaz en
> español.** Lee `CLAUDE.md` en la raíz antes de tocar nada. Rama
> `feat/<codigo>-<descripcion>`, PR hacia `develop`.

```bash
git checkout develop && git pull && npm install --prefix apps/web
```

La web desplegada es **https://proctoring-brown.vercel.app** y la API
**https://proctoring-api-gbqk.onrender.com**. Puedes probar contra ellas.

---

## 1 · Alineaciones (puntos 2, 3, 4, 5, 8, 18) · 2 pt

Van juntas porque son el mismo tipo de arreglo y se ven en cuanto abres cada
pantalla:

- **Los cuadros de resumen del examen** (alertas altas / medias / señales /
  estudiantes) están desparejos entre sí.
- **El guión que apunta a «Banco de prueba»** no está alineado con su texto.
- **Los guiones de la lista «Qué se va a supervisar»** están desalineados: cada
  uno a una altura distinta respecto a su línea.
- **La casilla de «Acepto ser supervisado»** no está alineada con su texto.
- **Texto que se sale de su recuadro** (lo viste en la pantalla de rendir).

Cógelo con calma y revisa **todas** las pantallas, no solo las de las capturas:
si estas seis estaban así, hay más.

- [ ] Los guiones y casillas alineados con la **primera línea** de su texto, no con el centro del bloque
- [ ] Ningún texto se sale de su recuadro, tampoco con títulos largos
- [ ] Comprobado en una ventana estrecha, no solo a pantalla completa

## 2 · Volver al inicio y recargar (puntos 13 y 14) · 2 pt · **importante**

Dos cosas que dejan al estudiante atrapado:

- **Al terminar un examen, la única opción es cerrar la aplicación.** Debería
  poder volver a su panel y ver lo que entregó.
- **En medio del examen no se puede recargar la página.** Si algo se traba, no
  hay salida.

Lo segundo hay que pensarlo bien: recargar **no puede** ser una forma de
esquivar la supervisión ni de empezar el examen de nuevo. Lo que se recarga es
la pantalla; la matrícula, las respuestas guardadas y el tiempo siguen donde
estaban. Habla conmigo antes de implementarlo.

- [ ] Al entregar, un camino claro de vuelta al panel del estudiante
- [ ] Recargar durante el examen lo recupera donde estaba, sin perder respuestas
- [ ] Recargar **no** reinicia el tiempo ni limpia las señales registradas
- [ ] Probado recargando a mitad, con respuestas ya escritas

## 3 · Encontrar a un alumno (punto 17) · 2 pt

> «La gestión para encontrar a cada alumno es muy tediosa.»

Hoy, para llegar a un estudiante concreto hay que pasar por el examen, luego
resultados, luego revisar. Con 30 estudiantes eso no se sostiene.

Úsalo tú primero con un examen que tenga varios matriculados y anota dónde te
pierdes. Esa lista es la tarea.

- [ ] Buscar un estudiante por nombre o correo desde donde tenga sentido
- [ ] Desde la lista, llegar a su caso en **un** clic
- [ ] Probado con más de diez estudiantes, no con dos

## 4 · Vistas del estudiante (punto 1) · 2 pt

Ya está hecho `/estudiante/cursos/:id` (todos los exámenes de un curso, los
rendidos con su nota y enlace a sus respuestas). Héctor dice que sigue faltando.

Repásalo como estudiante y decide qué falta de verdad:

- [ ] Desde «Mis clases» se llega al curso y desde ahí a cada examen
- [ ] Un examen entregado muestra respuestas, nota y señales
- [ ] Probado con un estudiante que tenga varios cursos y varios exámenes

---

## Antes de subir

```bash
cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build
```

> Ojo: `npx tsc --noEmit` **no** comprueba lo mismo que el build. Usa
> `npm run build`, que corre `tsc -b`, antes de dar algo por bueno. Nos pasó.
