# Qué pasa con la app de escritorio si desplegamos la web

Respuesta corta: **la mayoría de los cambios le llegan solos, sin reinstalar
nada.** Pero hay una variable que se congela al publicar el instalador, y hoy
está sin resolver — es el fallo que vio Rider en la otra computadora.

## Por qué le llegan solos

La app **no reimplementa el examen**. Carga la misma web, en la ruta del examen,
dentro de una ventana en kiosco con la protección de contenido puesta. Está
escrito en `apps/desktop/src/main/web.ts`:

> «Tener dos exámenes distintos —uno en React y otro en Electron— sería tener
> dos sitios donde arreglar cada cosa.»

Así que la app es una carcasa. Si desplegamos la web en Vercel y la app apunta
ahí, entonces:

| Cambia esto | Llega a la app instalada |
|---|---|
| Cualquier pantalla de la web (rendir, sala, avisos, prueba de micrófono) | **Sí**, al recargar la ventana |
| Cualquier cosa de la API | **Sí**, es la misma API |
| Esquema de Supabase, RLS, Realtime | **Sí** |
| El worker de IA | **Sí**, no lo toca la app |
| Kiosco, monitores, procesos, foco, permisos, protección de captura, enlace `proctoring://` | **No.** Eso es el proceso principal y vive dentro del `.exe` |

Dicho de otra forma: lo de Jesús y Pierreluiggi —cámara, mirada, micrófono,
avisos— corre en el *renderer*, o sea en la web. Les llega solo. Lo de Rider en
`src/main/` no.

## Lo que sí exige volver a instalar

Todo lo de `apps/desktop/src/main/`. Y **no hay actualización automática**: no
existe código de `autoUpdater` en el proyecto, y `electron-builder.yml` todavía
trae el marcador que viene con la plantilla:

```yaml
publish:
  provider: generic
  url: https://example.com/auto-updates
```

Esa URL no es nuestra, es el ejemplo del andamio. Mientras siga así, cada cambio
del proceso principal significa publicar un instalador nuevo y que los
estudiantes lo vuelvan a descargar.

## El problema de verdad: la URL se congela

`webBaseUrl()` es una sola línea y de ella cuelga todo:

```ts
return (process.env['PROCTORING_WEB_URL'] ?? 'http://localhost:5173').replace(/\/$/, '')
```

De esa variable salen cuatro cosas, no una:

1. **qué carga** la ventana (`examUrl`);
2. **a dónde puede navegar** (`restrictNavigation`);
3. **a qué origen se le conceden cámara y micrófono** (`applyPermissionPolicy`);
4. **qué origen se acepta** en el enlace `proctoring://` (`liveExamSessionId`).

Que las cuatro deriven de la misma variable está bien hecho: apuntarla a la web
desplegada basta, no hay que tocar nada más ni hay ningún `localhost` escrito a
mano en las políticas.

**El problema es cómo llega esa variable a un `.exe` instalado: hoy no llega.**
Nada la inyecta al empaquetar — no hay `define` en `electron.vite.config.ts` ni
`extraMetadata` en `electron-builder.yml`, y el `.env` está explícitamente
excluido del paquete (línea 10 de `electron-builder.yml`). Se lee de
`process.env` en tiempo de ejecución, o sea del entorno del estudiante, que no
la tiene.

Resultado: un instalador publicado hoy apunta a `http://localhost:5173` en la
máquina del estudiante. No hay nada ahí, así que la ventana se queda
reintentando. Hay una prueba que lo documenta (`src/main/web.test.ts`): sin la
variable, `webBaseUrl()` devuelve el servidor de desarrollo.

**Eso es exactamente el error de la otra computadora. No era culpa de Rider.**

### Cómo lo arreglo

Lo bueno es que no se arregla con documentación, se arregla haciéndolo
imposible: hornear la URL al empaquetar y **que el empaquetado falle** si no
está puesta. Así nadie puede publicar un instalador que apunte a localhost, en
vez de confiar en que se acuerde.

No requiere saber todavía el dominio de Vercel; el dominio se pone cuando exista
la cuenta. Lo que no puede quedar es el mecanismo sin hacer, porque bloquea
`EN-011`/`TA-060` (publicar el Release) y eso bloquea `HU-028` (la descarga
desde la portada).

## Orden correcto para desplegar

El orden importa, porque cada paso necesita la URL del anterior:

1. **API en Render.** Da la URL de la API.
2. **Web en Vercel**, con `VITE_API_URL`, `VITE_SUPABASE_URL` y
   `VITE_SUPABASE_PUBLISHABLE_KEY`. Las variables `VITE_*` se hornean **al
   construir**, no se leen en el navegador: cambiarlas obliga a reconstruir la
   web, no solo a reiniciarla. Esto da el dominio.
3. **`CORS_ORIGINS` de la API** con el dominio de Vercel. Sin esto el navegador
   bloquea todo y parece un fallo del código. Las URL de redirección de Supabase
   Auth, igual.
4. **Worker de IA** en Hugging Face Spaces, con Redis administrado.
5. **Y solo entonces el instalador**, construido apuntando al dominio de Vercel,
   y publicado como Release.

Publicar el `.exe` antes del paso 2 es publicar uno roto.

## Lo que se puede seguir cambiando con la web desplegada

Sí, se puede. Es la pregunta que hicieron los chicos y la respuesta es que sí,
con dos matices:

- **La web y la API se redespliegan en cada push**, así que sus cambios llegan
  sin tocar la app.
- **El instalador no.** Cada cambio del proceso principal pide un Release nuevo.

Por eso conviene cerrar primero lo de `src/main/` —mediciones, kiosco, permisos—
y publicar el instalador cuando eso esté quieto. Lo que siga moviéndose después
puede vivir en la web sin molestar a nadie.
