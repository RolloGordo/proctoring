# Desplegar, paso a paso

Para alguien que no ha desplegado nunca. **Sigue el orden**: cada paso necesita
una dirección que te da el anterior.

Vas a abrir cuatro webs y crear cuatro cosas. Todo en plan gratuito.

| | Qué es | Dónde |
|---|---|---|
| 1 | Redis (la cola) | upstash.com |
| 2 | La API | render.com |
| 3 | El worker de IA | huggingface.co |
| 4 | La web | vercel.com |

Antes de empezar, ten a mano dos cosas del panel de Supabase
(**Settings → API**): la **Project URL** y la **service_role key**. Esa clave
abre toda la base: no la pegues en ningún chat ni en ningún archivo del repo.

---

## 0. Un secreto que vas a necesitar

La API y el worker se hablan con un secreto compartido. Invéntalo ahora, una
sola vez, y úsalo igual en los dos sitios:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Guárdalo. Lo llamaremos **INTERNAL_API_TOKEN**.

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
   | `SUPABASE_URL` | la Project URL de Supabase |
   | `SUPABASE_SERVICE_ROLE_KEY` | la service_role key |
   | `CORS_ORIGINS` | `http://localhost:5173` *(lo corriges en el paso 5)* |

5. **Create Web Service** y espera. La primera construcción tarda unos minutos.
6. Cuando termine, arriba verás la dirección, algo como
   `https://proctoring-api.onrender.com`. **Apúntala**: es tu **URL de la API**.
7. Comprueba que vive: abre `https://proctoring-api.onrender.com/health` en el
   navegador. Tiene que responder algo, no un error.

> **El plan gratuito se duerme** tras 15 minutos sin uso, y despertar tarda
> unos 50 segundos. Antes de una demo, abre esa dirección un minuto antes.

---

## 3. El worker de IA en Hugging Face

1. Entra en huggingface.co → **Sign Up**.
2. Arriba a la derecha, tu foto → **New Space**.
3. Rellena:
   - **Space name:** `proctoring-ai`
   - **Space SDK:** **Docker** → **Blank**
   - **Visibility:** `Private`
4. Créalo. Te deja en un repositorio vacío.
5. Ese Space es un repositorio de git aparte. Desde tu máquina:

```bash
git clone https://huggingface.co/spaces/TU_USUARIO/proctoring-ai espacio-ai
```

```bash
cp -r services/ai/* espacio-ai/ && cd espacio-ai && git add -A && git commit -m "worker" && git push
```

6. En el Space, **Settings → Variables and secrets**, añade como **Secrets**:

   | Clave | Valor |
   |---|---|
   | `REDIS_URL` | la misma del paso 1 |
   | `PROCTORING_API_URL` | la URL de la API del paso 2 |
   | `INTERNAL_API_TOKEN` | el mismo secreto del paso 0 |
   | `DEEPGRAM_API_KEY` | la clave de Deepgram de Pierreluiggi |

7. El Space se reconstruye solo. Cuando ponga **Running**, está escuchando la cola.

> El worker no tiene pantalla: lo que abre es un endpoint de salud que responde
> `{"queue": true}`. Si responde eso, está conectado a la cola.

---

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
   | `VITE_SUPABASE_URL` | la Project URL de Supabase |
   | `VITE_SUPABASE_PUBLISHABLE_KEY` | la clave **publicable** (la `anon`), nunca la de servicio |

5. **Deploy**. Al terminar te da la dirección: `https://proctoring-xxx.vercel.app`.
   **Apúntala**: es tu **URL de la web**.

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
escritorio en local y apúntala a donde quieras. En PowerShell, desde
`apps/desktop`:

```bash
$env:PROCTORING_WEB_URL="https://proctoring-xxx.vercel.app"; npm run dev
```

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
| La API tarda 50 s la primera vez | Normal: el plan gratuito duerme |
| Render dice «no Dockerfile found» | El **Root Directory** no es `services/api` |
| Vercel compila pero sale en blanco | El **Root Directory** no es `apps/web` |
| Recargar una página da 404 | Falta el `vercel.json`; ya está en el repositorio, comprueba que desplegaste después de que entrara |
| El worker no coge trabajos | `REDIS_URL` distinta en la API y en el Space |
| El Space se reinicia en bucle | No encuentra el puerto. Comprueba que `salud.py` está en el Space |
