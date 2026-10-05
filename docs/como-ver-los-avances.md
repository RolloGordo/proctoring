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

Debe decir `{"status":"ok","env":"local","version":"0.1.0","auth":"enabled"}`.
La documentación interactiva de los endpoints está en
<http://localhost:8000/docs> — sirve como evidencia de que la API existe y
funciona, sin tocar la web.

## 2. La web

```powershell
npm run dev --prefix apps/web
```

Se abre en <http://localhost:5173>.

Lo primero que ves es la **portada**, que explica qué es el sistema. Desde ahí:

| Entras como | Llegas a |
|---|---|
| Docente | `/docente`: el panel, con la barra lateral |
| Estudiante | `/estudiante`: el panel, con la barra lateral |

Sin cuentas configuradas (modo desarrollo) la barra lateral trae **"Ver como
estudiante" / "Ver como docente"** para saltar de un lado al otro sin login.

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

```powershell
npm run dev --prefix apps/desktop
```

Se abre una ventana con la web del examen. **No hay que configurar nada a mano**:
el estudiante inicia sesión, escribe su código y el examen sale de ahí.

Cómo se conecta con la web, que es lo que conviene entender:

1. La web corre **dentro** de la ventana de Electron. Al iniciar sesión, le
   entrega el token al proceso principal de la app (`window.api.setAuthSession`).
   De ese token sale **quién** rinde; la API lo verifica y rechaza cualquier
   evento cuyo estudiante no coincida con el del token.
2. **La supervisión empieza al llegar a `/rendir`, no al abrir la app.** El
   consentimiento se da en `/sala`: antes de aceptar, la app no manda nada.
3. Al llegar a `/rendir`, la app revisa de nuevo monitores y procesos como si
   fuera el inicio del examen. Si AnyDesk ya estaba abierto, se avisa en ese
   momento; sin esto el aviso se habría emitido antes de haber examen y se
   habría perdido.
4. Si el estudiante cierra sesión, la app olvida quién era.

En la terminal de la app verás `[examen] supervision iniciada para la sesion …`
cuando eso ocurre, y `[event] …` por cada señal.

Opciones útiles (`$env:NOMBRE = "valor"` antes de arrancar):

| Variable | Para qué |
|---|---|
| `PROCTORING_PANEL=1` | Abre el **panel local de eventos** en vez del examen. Es la herramienta de diagnóstico del proceso principal. |
| `PROCTORING_SESSION_ID=<uuid>` | Abre directo la sala de ese examen, saltándose la pantalla del código. |
| `PROCTORING_KIOSK=1` | Modo kiosco en desarrollo. |
| `PROCTORING_DISABLE_CONTENT_PROTECTION=1` | La ventana sale en capturas (ver abajo). |

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

14. Vuelve a la sala de espera del docente: aparece la hora de entrega y la **nota**.
15. **Revisa el caso:** en la sala de espera, **Revisar** abre la evidencia del estudiante: el riesgo con
    su desglose por señal y la línea de tiempo. Para tener algo que ver, abre AnyDesk o Discord, cambia de
    ventana con Alt+Tab o conecta otro monitor mientras el estudiante rinde.
16. **Decide.** Elige confirmar, descartar o repetir el examen y escribe una **justificación de al menos
    10 caracteres**. Sin ella el botón no se activa. La decisión se registra y no se edita; si cambias de
    parecer, registras otra y el historial queda.

### Opcional: con un curso

Antes del paso 1 puedes crear un curso (**Mis cursos → Crear curso**), matricular al estudiante **por su
correo** (tiene que haberse registrado antes) y asociarlo al crear el examen. El estudiante verá la clase
y la fecha del examen en su panel. **Para rendirlo sigue necesitando el código de acceso.**

### La nota

Al entregar se califican solas las preguntas de opción múltiple, verdadero o falso, numéricas y de
completar. **Los desarrollos no**: esa nota es del docente, y mientras tanto el estudiante ve una nota
parcial con el aviso *Faltan desarrollos por calificar*. Para ver una nota completa, no uses desarrollos.

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

## Las dos cuentas de prueba

Con el login encendido **todo** pide sesión, incluida la ventana de la app de
escritorio. Hacen falta dos cuentas: un docente y un estudiante.

Las cuentas **no se pueden crear desde el código**: viven en Supabase Auth, que
es un servicio aparte, y se crean en su panel.

### Docente

Ya existe: `hfsv123456@gmail.com`, con rol `teacher`. Si no recuerdas su
contraseña, en el panel de Supabase: **Authentication → Users**, los tres puntos
de esa fila → **Send password recovery**, o **Reset password**.

### Estudiante

En el panel de Supabase: **Authentication → Users → Add user → Create new user**.

- **Email:** uno distinto del docente. Con Gmail sirve un alias que llega a tu
  misma bandeja, por ejemplo `hfsv123456+estudiante@gmail.com`.
- **Password:** la que quieras.
- **Marca `Auto Confirm User`.** Si no, el login responde *"Falta confirmar el
  correo"* y no puedes entrar.

No hace falta nada más: un disparador de la base crea su perfil, y **todo el que
se registra entra como `student`**. Los docentes se promueven a mano, a propósito
(`supabase/migrations/20261003120300_harden_signup_function.sql`).

Comprueba que quedó bien:

```sql
select p.email, p.role, u.email_confirmed_at is not null as confirmado
from public.profiles p join auth.users u on u.id = p.id
order by p.role;
```

Tienen que salir dos filas: una `teacher` y una `student`, las dos confirmadas.

### Que las dos mitades vayan de acuerdo

La web pide sesión cuando `apps/web/.env.local` trae la clave de Supabase, y la
API la exige cuando el `.env` de la raíz dice `AUTH_ENABLED=true`. Tienen que ir
juntas: si la API tiene `false`, ignora el token y trata a todos como el mismo
estudiante de desarrollo.

```powershell
curl http://localhost:8000/health
```

Debe decir `"auth":"enabled"`. Para volver al modo sin cuentas, vacía
`VITE_SUPABASE_PUBLISHABLE_KEY` y pon `AUTH_ENABLED=false`, y reinicia la API
con `docker compose up -d --force-recreate api`.

## Navegar con las dos cuentas a la vez

Hacen falta **dos sesiones distintas**, y un mismo navegador comparte la sesión
entre pestañas. Lo más cómodo:

| Quién | Dónde |
|---|---|
| **Docente** | Tu navegador normal, en <http://localhost:5173> |
| **Estudiante** | La **app de escritorio** (`npm run dev --prefix apps/desktop`) |

Así ves exactamente lo que pide el proyecto: el docente en la web y el
estudiante en la app, y cómo las alertas del segundo llegan al primero.

1. **Docente (navegador):** entra, crea un examen con fecha de inicio **ya
   pasada** o en unos minutos, añade preguntas y copia el código de acceso.
   Deja abierta la pantalla del examen: ahí aparecen las alertas.
2. **Estudiante (app):** entra con la cuenta de estudiante → escribe el código →
   lee la supervisión y acepta.
3. **Docente:** *Sala de espera* → **Admitir**.
4. **Estudiante:** la pantalla se actualiza sola y deja entrar. A partir de aquí
   empieza la supervisión.
5. **Provoca señales:** cambia de ventana con Alt+Tab y vuelve (`focus_lost`),
   abre AnyDesk o Discord (`suspicious_process`), conecta otro monitor
   (`extra_display`).
6. **Docente:** las alertas aparecen en la pantalla del examen en segundos.
7. **Estudiante:** responde, recarga para ver que se conserva y entrega.

Si no tienes forma de abrir dos sesiones a la vez, usa una ventana de incógnito
para la segunda cuenta.
