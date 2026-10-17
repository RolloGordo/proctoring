# Rider · paso a paso, sin saber nada de antemano

Esto es una receta. No explica el proyecto: dice qué escribir, qué vas a ver y
qué anotar. Si sigues los pasos en orden, terminas.

**Te quedan dos cosas.** Nada más:

- **A.** Medir cuatro tiempos en Windows (DO-004 + TA-015)
- **B.** Probar el instalador en otra computadora y publicarlo (EN-011 + TA-060)

HU-023 y HU-015 ya están entregadas y fusionadas. No tienes que volver a tocarlas.

---

## Tu duda: «¿tengo que hacer las pruebas con todo levantado?»

**No.** Esa es la buena noticia y por eso te habías atascado.

Para medir los cuatro tiempos **solo necesitas la app de escritorio**. Nada más.
Sin API, sin la web, sin Docker, sin iniciar sesión y sin crear un examen.

La app tiene un **panel de diagnóstico** que muestra cada evento con su hora y su
duración en pantalla. Eso es todo lo que necesitas para anotar los números.

Lo de «que los eventos lleguen a la API» es un criterio **aparte** y lo dejas
para el final (parte A5). Primero los números.

---

# PARTE A · Las cuatro mediciones

## A0. Lo que necesitas tener a mano

- [ ] Tu computadora con Windows
- [ ] Un **segundo monitor** (o un cable HDMI y una tele; sirve igual)
- [ ] **Zoom** o **AnyDesk** instalado (sin usarlo, solo instalado)
- [ ] El **cronómetro del celular**
- [ ] Algo para **grabar la pantalla** (Xbox Game Bar: tecla Windows + G)
- [ ] Papel o un bloc de notas para apuntar

## A1. Actualiza el repositorio

Abre **Git Bash** en la carpeta del proyecto y escribe:

```bash
git checkout develop && git pull
```

```bash
npm install --prefix apps/desktop
```

## A2. Arranca la app en modo panel

Abre **PowerShell** en la carpeta del proyecto. Copia esta línea entera y dale
Enter:

```powershell
$env:PROCTORING_PANEL=1; $env:PROCTORING_DISABLE_CONTENT_PROTECTION=1; npm run dev --prefix apps/desktop
```

**Qué hace cada cosa:**

- `PROCTORING_PANEL=1` → abre el panel de eventos en vez del examen. Es lo que te
  deja ver los números.
- `PROCTORING_DISABLE_CONTENT_PROTECTION=1` → apaga la protección de pantalla,
  para que la ventana **salga** en tu grabación. Sin esto grabarías un
  rectángulo negro.

**Qué deberías ver:** una ventana con una tabla vacía de eventos. Si la ves, ya
está todo listo. Deja esa ventana abierta todo el rato.

> Si no arranca, manda a Héctor lo que diga la terminal. No sigas adivinando.

## A3. Empieza a grabar

Tecla **Windows + G** → botón de grabar. Graba todo seguido, las cuatro pruebas
en un solo vídeo. Dura 2 o 3 minutos.

Di en voz alta lo que vas haciendo («prueba uno, intento uno»). Así el vídeo se
entiende solo.

---

## A4. Las cuatro pruebas

### Prueba 1 · Pérdida de foco (tres veces)

**Meta:** un solo evento por cada salida, y que la duración que mide la app se
parezca a tu cronómetro con menos de 200 ms de diferencia.

1. Pon el cronómetro listo.
2. Pulsa **Alt+Tab** y arranca el cronómetro **en el mismo momento**.
3. Espera unos 5 segundos.
4. Vuelve a la ventana de la app y **para el cronómetro** en el mismo momento.
5. Mira la tabla del panel: aparece una fila **«Salió de la ventana»** con una
   duración.
6. Anota las dos cifras.

| Intento | Tu cronómetro | Lo que dice la app | Diferencia | ¿Salió un solo evento? |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

> **Lo más importante de esta prueba no es la duración, es que salga UN evento.**
> Si de un solo Alt+Tab salen dos o tres filas, eso es un hallazgo y hay que
> anotarlo.

### Prueba 2 · Monitor adicional (tres veces)

**Meta:** menos de 5 segundos desde que lo conectas hasta que aparece el evento.

1. Con el segundo monitor **desconectado**, mira la hora exacta de tu celular.
   (Si lo dejas conectado al arrancar, la app lo detecta de entrada y no puedes
   medir el tiempo. Por eso se empieza desconectado.)
2. Conecta el cable y **anota la hora exacta** (con segundos).
3. Mira el panel: aparece una fila **«Monitor adicional»** con su hora.
4. Resta: hora del evento − hora en que lo conectaste.
5. Desconecta, espera 10 segundos y repite.

| Intento | Hora en que conecté | Hora del evento | Diferencia |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |

### Prueba 3 · Proceso sospechoso (tres veces)

**Meta:** menos de 15 segundos desde que abres Zoom o AnyDesk.

1. Asegúrate de que Zoom (o AnyDesk) está **cerrado del todo**. Mira la bandeja
   junto al reloj: si está ahí, ciérralo desde ahí.
2. Mira la hora exacta y **abre Zoom**. Anota la hora.
3. Mira el panel: aparece **«Proceso sospechoso»** con su hora.
4. Resta.
5. Cierra Zoom del todo, espera 20 segundos y repite.

| Intento | Hora en que abrí Zoom | Hora del evento | Diferencia |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |

### Prueba 4 · Protección de captura (esta es distinta)

**Para esta prueba hay que arrancar la app SIN la variable de protección.**

1. Cierra la ventana de la app.
2. En PowerShell, para el proceso con **Ctrl+C**.
3. **Cierra PowerShell entero y ábrelo de nuevo.** Es la forma segura de que la
   variable desaparezca.
4. Arranca así, **sin** la variable de protección:

   ```powershell
   $env:PROCTORING_PANEL=1; npm run dev --prefix apps/desktop
   ```

5. Con la ventana de la app visible, haz una captura: tecla **ImprPant**, o la
   **Herramienta de Recortes** (Windows + Shift + S).
6. Pega la captura en Paint y mira.

**Qué debe pasar:** donde estaba la ventana de la app se ve **negro**. Esa imagen
en negro **es** la evidencia. Guárdala.

| ¿Salió negro? | Con qué herramienta lo intenté |
|---|---|
| | |

> Si **no** sale negro, anótalo igual. Un resultado que no cumple es un hallazgo,
> y vale más que un número bonito inventado.

**Para la grabación:** esta cuarta prueba grábala aparte, porque con la
protección activada la ventana saldrá negra también en el vídeo. Es lo esperado
y conviene que se vea.

---

## A5. (Opcional, al final) Que los eventos lleguen a la API

Esto **ya no es medir tiempos**. Es solo enseñar que los eventos llegan al
servidor. Déjalo para cuando tengas los números de arriba.

Necesitas tres terminales abiertas a la vez:

**Terminal 1** — la API:

```bash
docker compose up -d --build api
```

**Terminal 2** — la web:

```bash
npm run dev --prefix apps/web
```

**Terminal 3** — la app, ahora **sin** `PROCTORING_PANEL`:

```powershell
npm run dev --prefix apps/desktop
```

Después:

1. En la app, inicia sesión con una cuenta de **estudiante**.
2. Pídele a Héctor un código de examen con el estudiante ya admitido.
3. Entra al examen y llega a la pantalla de **rendir**.
4. Haz un Alt+Tab.
5. En la Terminal 1, mira los registros:

   ```bash
   docker compose logs -f api
   ```

   Busca una línea con `POST /api/v1/events` y **201**. Esa captura es la
   evidencia.

> Los eventos solo salen hacia la API cuando estás **dentro del examen**
> (`/rendir`). En el panel de diagnóstico se ven en pantalla pero no se envían:
> es a propósito.
>
> Si esta parte se te complica, **no la pelees sola a las 2 de la mañana**.
> Dile a Héctor que te monte el examen. Lo importante son las cuatro medidas.

---

## A6. Escribir los resultados

Abre **`apps/desktop/README.md`** y busca dos sitios:

**Sitio 1 — «Criterios de aceptación».** Cambia `- [ ]` por `- [x]` **solo** en
los que de verdad mediste. Si no hiciste uno, lo dejas sin marcar.

**Sitio 2 — la tabla «SPEC-006: estado de mediciones».** Donde dice
*«Pendiente…»*, escribe lo que observaste. Así:

| Medición | Estado | Cómo registrar el resultado |
|---|---|---|
| Pérdida de foco | **Medido: 185 ms, 192 ms, 201 ms de error. Un solo evento en los tres intentos.** | … |
| Monitor adicional | **Medido: 2 s, 3 s, 2 s. Cumple (<5 s).** | … |
| Proceso sospechoso | **Medido: 9 s, 11 s, 10 s. Cumple (<15 s).** | … |
| Protección de captura | **Comprobado: la ventana sale en negro con ImprPant y con Recortes.** | … |
| Vídeo de evidencia | **Grabado el 10/10, subido al Notion.** | … |

Pon **los números que te salieron**, no los de este ejemplo.

## A7. Subirlo

```bash
git checkout -b docs/TA-015-mediciones
```

```bash
git add apps/desktop/README.md
```

```bash
git commit -m "docs(TA-015): record the measured desktop alert latencies"
```

```bash
git push -u origin docs/TA-015-mediciones
```

```bash
gh pr create --base develop --fill
```

**El vídeo NO va al repositorio.** Va al Notion de Héctor.

---

# PARTE B · El instalador y el Release

## B1. Genera el instalador

```powershell
npm run build:win --prefix apps/desktop
```

Ese comando ya compila y empaqueta: no hace falta nada antes. Tarda un rato.

Queda en `apps/desktop/dist/`, un archivo que termina en `-setup.exe`.

## B2. Pruébalo en OTRA computadora

Esta parte no se puede hacer en la tuya. El punto es comprobar que funciona
donde **no** está Node ni el repositorio, que es la situación real de un
estudiante.

Copia el `.exe` a una USB o mándatelo por WhatsApp, y en la otra máquina:

| Qué comprobar | ¿Pasó? |
|---|---|
| Instala sin pedir nada raro | |
| Arranca y abre la ventana a pantalla completa | |
| Llega a la pantalla del código de acceso | |
| Al cerrarla, **no queda el proceso colgado** (míralo en el Administrador de tareas) | |

**Anota qué versión de Windows tiene esa computadora.** (Configuración → Sistema
→ Información.)

Saca una foto o captura de la app corriendo en esa máquina. Esa es la evidencia.

## B3. Publícalo

Desde la carpeta del proyecto en tu máquina:

```bash
gh release create v1.0.0 apps/desktop/dist/desktop-1.0.0-setup.exe --title "Proctoring Desktop 1.0.0" --notes "Primera version instalable. Kiosco, proteccion de contenido, deteccion de foco, monitores y procesos."
```

**Si el nombre del archivo no es exactamente ese**, míralo primero:

```bash
ls apps/desktop/dist/
```

y usa el nombre que te salga.

**Si `gh` dice que no tienes permisos**, díselo a Héctor: hay que ajustar el
token. No es culpa tuya.

**Qué deberías ver:** una URL que termina en `/releases/tag/v1.0.0`. Ábrela: ahí
está tu instalador descargable. Esa pantalla es la evidencia.

---

# Resumen de qué entregar

| Qué | Dónde va |
|---|---|
| Los números de las 4 medidas | `apps/desktop/README.md`, en un PR |
| Vídeo de 2–3 min con las 4 pruebas | Notion de Héctor |
| Captura de la pantalla en negro | Notion de Héctor |
| Captura del Release publicado | Notion de Héctor |
| Foto de la app en la otra computadora | Notion de Héctor |
| Captura del `201` de la API (si llegas) | Notion de Héctor |

---

# Si algo sale mal

| Lo que pasa | Qué hacer |
|---|---|
| La app no arranca | `npm install --prefix apps/desktop` y vuelve a intentar. Si sigue, manda a Héctor lo que dice la terminal **entero**. |
| No aparece ningún evento en el panel | Comprueba que escribiste `PROCTORING_PANEL=1`. Sin eso se abre el examen, no el panel. |
| La ventana sale negra en mi grabación | Te faltó `PROCTORING_DISABLE_CONTENT_PROTECTION=1`. Es la variable larga. |
| La captura **no** sale negra en la prueba 4 | Está bien que lo descubras: anótalo tal cual y dilo. Es un hallazgo. |
| Un número no cumple la meta | **Anótalo igual.** No lo ajustes. Un número que no cumple es un resultado. |
| Me perdí | Vuelve a A2 y empieza de nuevo. No se rompe nada. |

---

**Una cosa, para que no dudes:** llevas 13 puntos cerrados esta semana, por
encima del objetivo. Lo que falta no es que hagas más cosas, es **medir las que
ya hiciste**. Son 40 minutos de pruebas y un vídeo.
