# Cómo abrir el sistema y tomar evidencia

Tres piezas: la **API**, la **web** y la **app de escritorio**. La web funciona
sola; la app de escritorio necesita a las otras dos porque carga la web dentro
de su ventana.

Todos los comandos se escriben en PowerShell, desde `C:\Users\Usuario\Desktop\proctoring`.

> PowerShell 5.1 no entiende `&&`. Si quieres encadenar, usa `;` o escribe un
> comando por línea.

## 1. La API

```powershell
docker compose up -d api
```

Comprueba que responde:

```powershell
curl http://localhost:8000/health
```

Debe decir `{"status":"ok","env":"local","version":"0.1.0","auth":"disabled"}`.
La documentación interactiva de los endpoints está en
<http://localhost:8000/docs> — sirve como evidencia de que la API existe y
funciona, sin tocar la web.

## 2. La web

```powershell
npm run dev --prefix apps/web
```

Se abre en <http://localhost:5173>.

## 3. La app de escritorio

### Antes de la primera vez: el binario de Electron

`npm install` descarga aparte un binario de ~100 MB. Si esa descarga falló, al
arrancar sale:

```
Error: Electron uninstall
    at getElectronPath (...)
```

No es un fallo del código: es que el binario no está. Se arregla con:

```powershell
node apps/desktop/node_modules/electron/install.js
```

Para comprobar que quedó bien, este archivo tiene que existir:
`apps/desktop/node_modules/electron/dist/electron.exe`.

### Hay dos servidores, y no sirven lo mismo

Esto confunde la primera vez. Al arrancar la app verás **dos** servidores:

| Puerto | Quién lo levanta | Qué sirve |
|---|---|---|
| **5173** | `npm run dev --prefix apps/web` | **El examen.** Es el que carga la ventana de la app. |
| **5180** | `npm run dev --prefix apps/desktop` | El panel local de eventos, la herramienta de diagnóstico. |

El 5173 está fijado con `strictPort`: si está ocupado, la web **falla** en vez
de mudarse al 5174 en silencio. Antes se mudaba, y como la app de escritorio
busca el examen en el 5173, la ventana acababa cargando otra cosa y el error
aparecía mucho después y en otro sitio.

Si te dice que el 5173 está ocupado, es que ya tienes una web corriendo: úsala,
o cierra la otra.

### Arrancarla

Necesita saber **qué examen** carga y **quién** lo rinde. Los dos son UUID que
salen de la base: el del examen lo ves en la URL cuando entras a un examen en la
web (`/sesiones/<este-uuid>`).

```powershell
$env:PROCTORING_SESSION_ID = "pega-aqui-el-uuid-del-examen"
$env:PROCTORING_STUDENT_ID = "00000000-0000-4000-8000-000000000002"
npm run dev --prefix apps/desktop
```

Se abre una ventana con el examen dentro. Sin `PROCTORING_SESSION_ID` se abre el
**panel local de eventos**, que no es el examen: es la herramienta de
diagnóstico para ver qué está detectando el proceso principal.

Para grabar evidencia de la ventana, ten en cuenta que está protegida contra
capturas a propósito: saldría en negro. Para que se vea:

```powershell
$env:PROCTORING_DISABLE_CONTENT_PROTECTION = "1"
```

Y al revés, para demostrar **que la protección funciona**, déjala puesta e
intenta capturar la ventana o compartir pantalla: tiene que verse en negro. Esa
es la evidencia del criterio de aceptación.

Para ver el modo kiosco en desarrollo: `$env:PROCTORING_KIOSK = "1"`.

## El recorrido completo, para grabarlo de una sola vez

### Como docente

1. <http://localhost:5173/sesiones> → **Crear examen**.
2. Pon título, fecha de inicio **en el pasado o en unos minutos** (si la pones
   mañana, el examen no se puede rendir hoy) y nivel de supervisión.
3. Al guardarlo aterrizas en el examen. Arriba a la derecha está el **código de
   acceso** y los botones **Preguntas** y **Sala de espera**.
4. **Preguntas** → añade al menos una de cada tipo. Sin preguntas el examen no
   se puede rendir.
5. Deja abierta la pantalla del examen: ahí llegan las alertas en vivo.

### Como estudiante

6. En otra ventana: <http://localhost:5173/examen> → escribe el código.
7. Lee qué se va a supervisar y marca **Acepto ser supervisado**. Ese es el
   consentimiento, y la API no entrega ni una pregunta sin él.
8. Te dirá que tu identidad no está verificada. Es correcto: todavía no existe
   la verificación facial.

### Otra vez como docente

9. **Sala de espera** → **Admitir**. Queda registrado que lo admitiste tú.

### Y de vuelta como estudiante

10. La pantalla de espera se actualiza sola y te deja entrar al examen.
11. Responde. Fíjate en el contador y en el aviso de **Guardado** arriba.
12. **Recarga la página a mitad**: las respuestas siguen ahí. Esa es la prueba
    de que el guardado automático funciona, y es buena evidencia.
13. **Entregar examen**.

### Para cerrar

14. Vuelve a la sala de espera del docente: aparece la hora de entrega.

## Dónde guardar las capturas

```
docs/evidencias/semana-<NN>/<tu-nombre>/
```

Con un `README.md` al lado explicando qué muestra cada archivo. Hay un ejemplo
en `docs/evidencias/semana-06/hector/`.

## Por qué no ves la pantalla de inicio de sesión

La web **tiene** login en `/login`, pero hoy se lo salta. El motivo está en
`apps/web/src/lib/supabase.ts`: si no hay proyecto de Supabase configurado, el
cliente es `null`, `authEnabled` queda en `false` y la web funciona sin pedir
credenciales — el mismo modo de desarrollo que la API con `AUTH_ENABLED=false`.
Por eso también se ven a la vez el menú del docente y el del estudiante: sin
sesión no hay rol que decidir, y así se puede recorrer todo el flujo sin crear
usuarios.

Para activarlo, en `apps/web/.env.local`:

```
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://uzuysjmymvtpoxfrdxnm.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<la clave publicable del proyecto>
```

La clave publicable está en el panel de Supabase, en **Project Settings → API
Keys**. Es segura en el navegador: RLS protege los datos en la base. La service
role key **nunca** va aquí.

Con eso, al recargar:

- `/login` pide correo y contraseña.
- El menú muestra solo lo que corresponde al rol de quien entró.
- Un docente que escriba `/examen` a mano acaba en `/sesiones`, y al revés.
- Las **alertas en vivo** empiezan a llegar por Supabase Realtime, que es lo que
  sostiene la meta de avisar en menos de 5 segundos. Sin Supabase configurado la
  pantalla del examen solo muestra lo ya registrado.

## Con el login ya encendido: hace falta un estudiante

En cuanto la web tiene Supabase configurado, **todas** las pantallas piden
sesión, incluida la que carga la app de escritorio. Y hoy en la base solo existe
un usuario, el docente. Hay que crear uno de estudiante.

En el panel de Supabase: **Authentication → Users → Add user**, con correo y
contraseña. No hace falta nada más: un disparador de la base crea su perfil y
**todo el que se registra entra como `student`** — los docentes se promueven a
mano, a propósito (`supabase/migrations/20261003120300_harden_signup_function.sql`).

Comprueba que quedó bien:

```sql
select email, role from public.profiles order by role;
```

Y que las dos mitades vayan de acuerdo: si la web pide sesión pero la API corre
con `AUTH_ENABLED=false`, la API ignora el token y trata a todo el mundo como el
mismo estudiante de desarrollo. Para que cada estudiante sea el suyo, en el
`.env` de la raíz:

```
AUTH_ENABLED=true
```

Y reinicia la API:

```powershell
docker compose up -d --force-recreate api
```

`curl http://localhost:8000/health` debe decir `"auth":"enabled"`.

Al revés también vale: si quieres recorrer el flujo sin crear usuarios, **vacía**
`VITE_SUPABASE_PUBLISHABLE_KEY` en `apps/web/.env.local` y las dos mitades
vuelven al modo sin autenticación. Lo que no conviene es dejarlas desparejas.
