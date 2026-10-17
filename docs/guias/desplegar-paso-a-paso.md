# Desplegar, paso a paso

Para alguien que no ha desplegado nunca. **Sigue el orden**: cada paso necesita
una dirección que te da el anterior.

Vas a abrir cuatro webs y crear cuatro cosas. Todo en plan gratuito.

| | Qué es | Dónde |
|---|---|---|
| 1 | Redis (la cola) | upstash.com |
| 2 | La API | render.com |
| 3 | El worker de IA | render.com (otra vez) |
| 4 | La web | vercel.com |

Antes de empezar, ten a mano dos cosas del panel de Supabase
(**Settings → API**): la **Project URL** y la **service_role key**. Esa clave
abre toda la base: no la pegues en ningún chat ni en ningún archivo del repo.

---

## 0. Un secreto que vas a necesitar

La API y el worker se hablan con un secreto compartido. Invéntalo ahora, una
sola vez, y úsalo igual en los dos sitios.

**Hazlo en PowerShell, no en `cmd`.** En la ventana negra de `cmd` el PATH es
distinto y `python` no se reconoce. Abre PowerShell (botón de inicio, escribe
«PowerShell») y pega:

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"
```

Si prefieres no depender de nada instalado, esto usa solo Windows:

```bash
$b=[byte[]]::new(32); $r=[System.Security.Cryptography.RNGCryptoServiceProvider]::new(); $r.GetBytes($b); $r.Dispose(); [Convert]::ToBase64String($b).TrimEnd('=').Replace('+','-').Replace('/','_')
```

Cualquiera de las dos da 43 caracteres sin símbolos raros, que es lo que hace
falta para que viaje bien en una variable de entorno.

> No copies un ejemplo de internet ni uses algo como `secreto123`. Ese token es
> lo único que impide que alguien de fuera escriba análisis y alertas en la API.

Guárdalo donde guardes tus contraseñas. Lo llamaremos **INTERNAL_API_TOKEN**, y
va igual en Render (paso 2) y en el Space (paso 3): si no coinciden, el worker
no puede entregar lo que mide y los trabajos fallan en silencio.

---

## 1. Redis en Upstash

1. Entra en upstash.com → **Sign up** con GitHub.
2. **Create Database**. Nombre: `proctoring`. Región: la más cercana a donde
   pongas la API (si eliges Oregon en Render, elige `us-west-1` aquí).
3. Cuando se cree, busca el apartado **REST / Connect**. Copia la cadena que
   empieza por `rediss://`. Esa es tu **REDIS_URL**.

> Que empiece por `rediss` con dos eses es correcto: es Redis sobre TLS.

---

## 2. La API en Render

1. Entra en render.com → **Get Started** con GitHub y autoriza el acceso al
   repositorio `proctoring`.
2. **New +** → **Web Service** → elige el repositorio.
3. Rellena:
   - **Name:** `proctoring-api`
   - **Language / Runtime:** `Docker`
   - **Branch:** `develop`
   - **Root Directory:** `services/api` ← **importante**, si no, no encuentra el Dockerfile
   - **Instance Type:** `Free`
4. Abre **Advanced → Add Environment Variable** y añade estas, una por una:

   | Clave | Valor |
   |---|---|
   | `ENV` | `production` |
   | `AUTH_ENABLED` | `true` |
   | `INTERNAL_API_TOKEN` | el secreto del paso 0 |
   | `EVENT_REPOSITORY` | `supabase` |
   | `EVIDENCE_STORAGE` | `supabase` |
   | `JOB_QUEUE` | `redis` |
   | `REDIS_URL` | la del paso 1 |
   | `SUPABASE_URL` | **solo el dominio**: `https://xxxx.supabase.co`, sin `/rest/v1` |
   | `SUPABASE_SERVICE_ROLE_KEY` | la service_role key |
   | `CORS_ORIGINS` | `http://localhost:5173` *(lo corriges en el paso 5)* |

5. **Create Web Service** y espera. La primera construcción tarda unos minutos.
6. Cuando termine, arriba verás la dirección, algo como
   `https://proctoring-api.onrender.com`. **Apúntala**: es tu **URL de la API**.
7. Comprueba que vive: abre esa dirección **añadiendo `/health` al final**.
   Tiene que responder algo como
   `{"status":"ok","env":"production","auth":"enabled"}`.

   > Si abres la dirección a secas verás `{"detail":"Not Found"}`. **Eso es
   > correcto**: la API no tiene ninguna página en la raíz, solo endpoints. El
   > único sitio que confirma que está viva es `/health`.

> **El plan gratuito se duerme** tras 15 minutos sin uso, y despertar tarda
> unos 50 segundos. Antes de una demo, abre esa dirección un minuto antes.

---

## 3. El worker de IA, también en Render

> **Hugging Face ya no sirve.** Los Spaces de Docker pasaron a ser de pago; solo
> los estáticos siguen siendo gratis, y el worker necesita ejecutar código. Da
> igual: va en Render con los mismos pasos que acabas de hacer.

1. En Render: **New +** → **Web Service** → el mismo repositorio.
2. Rellena:
   - **Name:** `proctoring-ai`
   - **Language / Runtime:** `Docker`
   - **Branch:** `develop`
   - **Root Directory:** `services/ai` ← distinto del de la API
   - **Instance Type:** `Free`
3. En **Advanced → Add Environment Variable**:

   | Clave | Valor |
   |---|---|
   | `REDIS_URL` | la misma del paso 1, **idéntica a la de la API** |
   | `PROCTORING_API_URL` | la URL de la API del paso 2 |
   | `INTERNAL_API_TOKEN` | el mismo secreto del paso 0 |
   | `DEEPGRAM_API_KEY` | la clave de Deepgram de Pierreluiggi |

4. **Create Web Service**. Cuando termine, te da una dirección como
   `https://proctoring-ai-xxxx.onrender.com`. **Apúntala.**
5. Comprueba que está conectado a la cola: abre esa dirección y añade `/health`.
   Tiene que responder `{"queue": true, "queues": ["high", "audio"]}`.

   Si pone `"queue": false`, la `REDIS_URL` está mal.

6. **Vuelve al servicio de la API** (`proctoring-api`) → **Environment** → añade
   una variable más:

   | Clave | Valor |
   |---|---|
   | `AI_SERVICE_URL` | la dirección del worker que acabas de apuntar |

   **Este paso no es opcional.** El plan gratuito apaga un servicio tras un rato
   sin peticiones, y un worker que solo consume de una cola no recibe ninguna:
   se dormiría para siempre y los análisis de audio se acumularían sin que nadie
   los mire. Con esta variable, la API lo despierta cada vez que encola algo.

> **Lo que esto significa para la demo.** Si el worker llevaba rato dormido, el
> primer análisis tarda lo que tarde en arrancar (unos 50 s), por encima del
> presupuesto de 10 s del objetivo. Mientras se usa, se mantiene despierto. Si
> vas a medir la latencia de verdad, levanta el worker en tu máquina apuntando
> a la misma Redis y a la API desplegada: ahí no hay arranque en frío.

## 4. La web en Vercel

1. Entra en vercel.com → **Sign Up** con GitHub.
2. **Add New → Project** → importa `proctoring`.
3. Rellena:
   - **Framework Preset:** `Vite`
   - **Root Directory:** pulsa **Edit** y elige **`apps/web`** ← **importante**
4. Abre **Environment Variables** y añade:

   | Clave | Valor |
   |---|---|
   | `VITE_API_URL` | la URL de la API del paso 2, **sin barra al final** |
   | `VITE_SUPABASE_URL` | **solo el dominio**: `https://xxxx.supabase.co` |
   | `VITE_SUPABASE_PUBLISHABLE_KEY` | la clave **publicable** (la `anon`), nunca la de servicio |

   > **Cuidado con la de Supabase.** En su panel aparece también una dirección
   > terminada en `/rest/v1`, que es la de los ejemplos de la API. **Esa no.**
   > El cliente añade él mismo `/auth/v1` o `/rest/v1` según lo que vaya a
   > hacer, y con la ruta puesta el login falla con
   > `Invalid path specified in request URL`, que no dice nada de lo que pasa.
   > Si te equivocas, la web lo corrige sola y deja un aviso en la consola del
   > navegador, pero corrígelo también en el panel.

5. **Deploy**. Al terminar te da varias direcciones, y **elegir mal cuesta una
   tarde**. Ve a **Overview** y mira el apartado **Domains**: la que lleva el
   icono de mundo es la de produccion, con un nombre tipo
   `https://proctoring-brown.vercel.app`. **Esa es tu URL de la web.**

   Las otras no sirven para esto:

   - `...-git-develop-....vercel.app` es la de la rama.
   - `...-<hash>-....vercel.app` es la de ese despliegue concreto.

   Y lo importante: **las que no son la de produccion suelen estar protegidas**.
   A ti te funcionan porque tienes sesion en Vercel, pero a cualquier otra
   persona —un estudiante, el profesor— le sale la pantalla de Vercel en vez de
   tu web.

   > Para comprobar cual es publica de verdad, abrela en una **ventana de
   > incognito**. Si te pide iniciar sesion en Vercel, esa no es.

6. **Usa esa misma direccion en todas partes**: en `CORS_ORIGINS` de la API y en
   Supabase. Mezclar dominios da errores que parecen de codigo y no lo son.

> Estas tres se **hornean al construir**. Si las cambias después, hay que
> **volver a desplegar** (Deployments → ⋯ → Redeploy); reiniciar no basta.

---

## 5. Atar los cabos (si saltas esto, no funciona nada)

**a) Deja que la web hable con la API.** En Render → tu servicio →
**Environment** → edita `CORS_ORIGINS` y pon la URL de Vercel:

```
https://proctoring-xxx.vercel.app
```

Guarda. Render reinicia solo.

**b) Deja que el login vuelva a tu web.** En Supabase → **Authentication** →
**URL Configuration**:

- **Site URL:** `https://proctoring-xxx.vercel.app`
- **Redirect URLs:** añade `https://proctoring-xxx.vercel.app/**`

**c) Aplica la migración que falta.** En Supabase → **SQL Editor** →
**New query**, pega el contenido de
`supabase/migrations/20261016020000_multiple_select_questions.sql` y ejecútalo.

> Es la de las preguntas con varias respuestas correctas. **Añadir un valor a un
> enum no se puede deshacer**, por eso no se aplicó antes. Sin ella, ese tipo de
> pregunta falla al guardarse.

---

## 6. Comprobar que funciona

En este orden, y si algo falla, para aquí:

1. Abre la URL de Vercel. Tiene que verse la portada.
2. Pulsa **Iniciar sesión** y entra con tu cuenta de docente.
3. Si ves el panel, la web y la API se están hablando. **Si da error de red o de
   CORS, es el paso 5a.**
4. Crea un examen de prueba.
5. Abre `https://TU-API/health`: tiene que responder.

---

## 7. El instalador, al final

**Solo cuando los pasos 1 a 6 estén bien.** La dirección de la web se congela
dentro del instalador, y un `.exe` ya publicado no la puede cambiar.

En PowerShell, desde `apps/desktop`:

```bash
$env:PROCTORING_WEB_URL="https://proctoring-xxx.vercel.app"; npm run build:win
```

Si se te olvida la variable, el empaquetado se niega y te dice qué poner.

El instalador sale en `apps/desktop/dist/`. Súbelo a un **Release** de GitHub
(repositorio → **Releases** → **Draft a new release**, etiqueta `v1.0.0`,
arrastra el `.exe`, **Publish**).

A partir de ahí, quien tenga una versión anterior recibe el aviso al abrir la
aplicación.

---

## Mientras pruebas

**No hace falta publicar el instalador para probar.** Deja la aplicación de
escritorio en local y apúntala a donde quieras.

Dos detalles de Windows que cuestan un rato si no se saben:

- **Hay que estar en `apps/desktop`**, no en la raíz del repositorio. No hay
  `package.json` en la raíz, así que `npm run dev` ahí no encuentra nada.
- **Windows bloquea `npm` en PowerShell** con «la ejecución de scripts está
  deshabilitada en este sistema». Es la política por defecto y afecta al
  envoltorio `npm.ps1`. La salida limpia es llamar a `npm.cmd`, que no pasa
  por esa política y **no obliga a bajar ninguna protección del equipo**.

```bash
cd C:\Users\Usuario\Desktop\proctoring\apps\desktop
```

```bash
$env:PROCTORING_WEB_URL="https://proctoring-xxx.vercel.app"; & "C:\Program Files\nodejs\npm.cmd" run dev
```

> Si prefieres escribir `npm` a secas de aquí en adelante, se puede permitir
> con `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, que solo afecta
> a tu usuario. Pero no hace falta para esto.

Así pruebas la web desplegada con la app de escritorio de tu máquina, sin
comprometerte con ningún instalador.

---

## Qué se actualiza solo y qué no

| Cambias esto | Qué hay que hacer |
|---|---|
| Web o API | Nada: Vercel y Render redespliegan al hacer push a `develop` |
| Una variable `VITE_*` | Volver a desplegar en Vercel |
| Algo de `apps/desktop/src/main/` | Construir y publicar un instalador nuevo |
| El esquema de la base | Ejecutar la migración nueva en el SQL Editor |

## Si algo falla

| Lo que ves | Qué suele ser |
|---|---|
| La web carga pero nada responde | `CORS_ORIGINS` sin la URL de Vercel (paso 5a) |
| El login da vueltas y vuelve al inicio | Redirect URLs de Supabase (paso 5b) |
| «Invalid path specified in request URL» al entrar | `VITE_SUPABASE_URL` en Vercel lleva `/rest/v1`. Déjala en el dominio y **redespliega** |
| «No se pudo verificar el token en este momento» | Lo mismo pero en `SUPABASE_URL` de Render. Con ruta, el JWKS responde 401 |
| La API tarda 50 s la primera vez | Normal: el plan gratuito duerme |
| Render dice «no Dockerfile found» | El **Root Directory** no es `services/api` |
| Vercel compila pero sale en blanco | El **Root Directory** no es `apps/web` |
| El login falla con un error raro de Supabase | Estás en un dominio que no es el de producción. Compruébalo en incógnito |
| A tus compañeros les sale una pantalla de Vercel | Les pasaste un dominio protegido, no el de producción |
| Recargar una página da 404 | Falta el `vercel.json`; ya está en el repositorio, comprueba que desplegaste después de que entrara |
| El worker no coge trabajos | `REDIS_URL` distinta en la API y en el worker, o falta `AI_SERVICE_URL` en la API |
| `{"detail":"Not Found"}` al abrir la API | Normal: no hay nada en la raíz. Usa `/health` |
| El primer análisis de audio tarda un minuto | El worker estaba dormido. Normal en plan gratuito |
