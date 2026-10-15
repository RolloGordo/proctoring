# Rider · lo que falta para cerrar

**Fecha límite del equipo: jueves 15/10.** Estado del repo: `develop` al día, todo en verde.

> Si pegas esto en un chat de IA: el proyecto es una plataforma de proctoring para
> exámenes remotos (UPAO, Taller Integrador 1). Monorepo con `apps/web` (React +
> TypeScript + Vite), `apps/desktop` (Electron + TypeScript), `services/api`
> (FastAPI hexagonal) y `services/ai` (worker RQ). **Código, identificadores y
> commits en inglés; la interfaz en español.** Lee `CLAUDE.md` en la raíz antes de
> tocar nada. Ramas `feat/<codigo>-<descripcion>`, PR hacia `develop`.

## Antes de empezar

```bash
git checkout develop && git pull && npm install --prefix apps/web
```

---

## Lo que YA está hecho (no lo rehagas)

Revisé el repo antes de escribir esto. Esto ya está dentro y fusionado:

- **TA-076** — el examen solo se rinde en la app. `RequireDesktopExam` está puesto en `App.tsx:92`.
- **TA-077** — el título ya es `Proctoring`, neutro, en `apps/web/index.html:6`.
- **TA-080** — el importador de PDF existe: `apps/web/src/lib/extraer-pdf.ts`.
- **TA-081 / TA-082** — bancos por curso, fusionado en el PR #42.
- **HU-027** — las vistas del estudiante existen: `PanelEstudiante.tsx` y `DetalleExamenEstudiante.tsx`.
- **HU-029** — el temporizador existe: «Tiempo restante» en `RendirExamen.tsx:224`.

---

## 1. TA-015 + DO-004 · Las mediciones · 2 pt · **lo más urgente**

Siguen sin tomarse. En `apps/desktop/README.md`, líneas 189-195, **seis de siete
casillas están sin marcar**. Solo la de `npm run test/lint/build` está hecha.

**Nadie más puede hacer esto**: necesita Windows, cronómetro, un segundo monitor
y Zoom o AnyDesk instalado. La receta paso a paso está en
[`rider-paso-a-paso.md`](./rider-paso-a-paso.md); son unos 40 minutos.

- [ ] Kiosco y pantalla completa, con prueba manual registrada
- [ ] Alt+Tab genera **un solo** `focus_lost`; comparar `duration_ms` con cronómetro (meta ±200 ms)
- [ ] Segundo monitor → `extra_display` en menos de 5 s; anotar el tiempo real
- [ ] Abrir Zoom o AnyDesk → `suspicious_process` en menos de 15 s; anotar el tiempo
- [ ] Captura externa con protección activa: la ventana sale en negro
- [ ] Los eventos llegan a la API y responden `201`; guardar los logs

**Escribe los números medidos, no «cumple».** El objetivo SMART del proyecto es
alerta de navegador/cámara en menos de 5 s, y el profesor va a preguntar cuánto dio.

## 2. EN-011 + TA-060 · El instalador y el Release · 2 pt

`gh release list` sigue vacío. **Esto bloquea HU-028.**

> **No publiques el instalador todavía: habla conmigo primero.**
>
> `apps/desktop/src/main/web.ts:22` resuelve
> `process.env['PROCTORING_WEB_URL'] ?? 'http://localhost:5173'`, y **nada inyecta
> esa variable al empaquetar** — no hay `define` en `electron.vite.config.ts` ni
> `extraMetadata` en `electron-builder.yml`, y el `.env` está excluido del paquete.
> Un `.exe` publicado hoy apunta a `localhost:5173` en la máquina del estudiante.
>
> **Ese es el error que viste en la otra computadora, y no era culpa tuya.** Estoy
> haciendo que la URL se hornee al empaquetar y que el empaquetado falle si no
> está puesta. Cuando lo tenga, publicas. Detalle completo en
> [`despliegue-y-escritorio.md`](./despliegue-y-escritorio.md).

## 3. HU-028 · Descargar la app desde la portada · 1 pt

`apps/web/src/pages/Portada.tsx` no tiene de dónde bajarla. **Depende de TA-060.**

- [ ] Botón de descarga apuntando al GitHub Release
- [ ] Por qué hace falta: el examen se rinde ahí, no en el navegador
- [ ] Requisitos y permisos que va a pedir
- [ ] **Probado descargando desde otra máquina**

## 4. TA-063 · Prueba de humo: un examen entero · 2 pt · **bloquea el despliegue**

Es una de las tres pruebas de las que depende publicar. Un examen de principio a
fin en una máquina real, con cámara, micrófono y segundo monitor, y los cuatro
módulos activos.

- [ ] De principio a fin **sin que nadie intervenga a mitad**
- [ ] Los eventos de los cuatro módulos llegan al docente
- [ ] Probar también la **cuadrícula de cámaras** y que la **evidencia del caso** se abra
- [ ] Grabado

## 5. TA-014 · Cámara y micrófono dentro de la ventana · 1 pt

La política ya existe (`apps/desktop/src/main/permisos.ts`) y concede cámara y
micrófono **solo** al origen del examen. Falta **comprobar** que funciona.

- [ ] Dentro de la app no aparece diálogo de permiso
- [ ] Navegando a otro origen, se deniega

## 6. HU-026 · Que crear un examen y calificar se entienda · 2 pt

Lo más abierto. **Úsalo como si no lo hubieras construido tú** y anota dónde te
trabas; esa lista es la tarea. Lo que ya sabemos que molesta: crear examen pide
muchos datos de golpe sin marcar qué es obligatorio; banco y preguntas propias
son dos caminos para lo mismo sin explicar cuándo conviene cada uno; editar,
cancelar y borrar están juntos sin distinguir el peligroso; y la nota se calcula
sola pero el docente no ve de dónde sale.

- [ ] Un docente que no sea del equipo crea un examen **sin ayuda**. Ese es el criterio

---

## Antes de subir

```bash
cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build
```

```bash
cd apps/desktop && npm run lint && npm run typecheck && npm test && npm run build
```
