# La web en el VPS de Contabo (salida de Vercel)

Pedido de la reunión del 14/11/2026: dejar Vercel y servir todo desde el VPS que ya pagamos, con un
dominio propio gratuito del GitHub Student Developer Pack.

## Cómo queda

```
navegador ──► Traefik (HTTPS, Let's Encrypt, HSTS) ──► web × 2 (nginx, archivos estáticos)
                                                  └──► api × 3 (FastAPI)
```

- **Imagen:** `apps/web/Dockerfile`. Construye con Node 22 y sirve `dist/` con nginx.
- **Cabeceras:** `apps/web/deploy/cabeceras.conf`, las mismas que tenía `vercel.json`: COOP y COEP (el
  detector de voz necesita `SharedArrayBuffer`, ver `apps/web/VERCEL.md`), CSP, `nosniff`,
  `X-Frame-Options`, `Referrer-Policy` y `Permissions-Policy`. HSTS lo pone Traefik.
- **SPA:** toda ruta que no es archivo devuelve `index.html`, como la reescritura de Vercel.
- **Caché:** `/assets/` (con hash en el nombre) un año; modelos y fuentes un día; `index.html` nunca,
  para que un despliegue nuevo llegue en la siguiente recarga.
- **Variables:** las `VITE_*` se hornean al construir y son públicas (la clave de Supabase es la
  publicable, con RLS detrás). En Dokploy van como argumentos de construcción, no como secretos.

## Pasos

1. Servicio `web` en Dokploy (lo crea `~/provisionar.py`), dominio de prueba
   `web.86-48-18-81.sslip.io` (puerto 80, HTTPS con Let's Encrypt).
2. Añadir ese origen a `CORS_ORIGINS` de la API.
3. Probar el flujo entero en el dominio nuevo: inicio de sesión, crear examen, rendir desde la app
   de escritorio y ver la actividad. Comprobar en la consola `crossOriginIsolated === true`.
4. Cuando llegue el dominio del Student Pack (ver abajo), apuntarlo al VPS y cambiar el dominio en
   Dokploy y en `CORS_ORIGINS`.
5. Compilar la app de escritorio con la URL nueva (`PROCTORING_WEB_URL` horneada) y publicar el
   instalador.
6. Actualizar las URL de redirección de Supabase Auth (Authentication → URL Configuration) con el
   dominio nuevo.
7. Recién entonces apagar el proyecto de Vercel.

## El dominio: `proctoring-upao.app` (desde el 18/11/2026)

Registrado en **Name.com** con la oferta del GitHub Student Developer Pack: gratis hasta el
**18/11/2027** (la renovación cuesta 26,99 USD; la renovación automática se deja apagada).

| Servicio | URL |
|---|---|
| Web (docente y examen) | `https://proctoring-upao.app` |
| API | `https://api.proctoring-upao.app` |

Los dominios `web.86-48-18-81.sslip.io` y `api.86-48-18-81.sslip.io` siguen respondiendo como
alias para los instaladores ya repartidos; se retiran cuando todos tengan el instalador nuevo.

**Por qué `.app`:** está en la lista de precarga HSTS de los navegadores, así que ninguno lo abre por
HTTP, ni siquiera la primera vez (sin ventana para un ataque de rebaja a HTTP). `.dev` y `.page`
también lo están; `.me`, `.tech` y el resto no.

**Seguridad de la cuenta del registrador:** 2FA, bloqueo de transferencia y privacidad WHOIS
activados. Si se pierde el control del DNS, se pierde el sitio: la cuenta es solo del PM.

**DNS** (solo estos registros, sin comodín `*`):

| Tipo | Nombre | Valor |
|---|---|---|
| A | `@` | `86.48.18.81` |
| A | `api` | `86.48.18.81` |

El panel de Name.com no ofrece registros CAA; no son imprescindibles. Traefik pide el certificado de
Let's Encrypt la primera vez que alguien entra.

**Ojo con la renovación:** antes del 18/11/2027 hay que renovarlo (de pago) o volver a los alias de
`sslip.io`, que siguen funcionando sin hacer nada.

## Segundo dominio: `proctoring-upao.me` (desde el 26/11/2026)

La red de la universidad bloquea `.app` y `.dev`: desde el campus la web no abría. Se añadió
`proctoring-upao.me` (**Namecheap**, oferta del Student Pack, gratis hasta el **26/11/2027**,
renovación automática apagada, privacidad WHOIS, bloqueo y 2FA). **Los dos dominios responden a la
vez**, con la misma web y la misma API:

| Servicio | `.app` | `.me` |
|---|---|---|
| Web | `https://proctoring-upao.app` | `https://proctoring-upao.me` |
| API | `https://api.proctoring-upao.app` | `https://api.proctoring-upao.me` |

- **Cada web llama a la API de su propio dominio** (`apps/web/src/lib/baseApi.ts`, con
  `VITE_API_POR_DOMINIO`). Si la `.me` llamara a la API `.app`, en el campus cargaría la página y
  fallarían todas sus llamadas.
- **La app de escritorio desde la 1.1.4** abre `proctoring-upao.me`.
- **`.me` no está en la precarga HSTS**: la primera visita por HTTP la redirige Traefik a HTTPS, y
  desde ahí la cabecera HSTS (un año) obliga al navegador a no volver a HTTP.
- DNS: los mismos dos registros A (`@` y `api` → `86.48.18.81`). No pulsar «Setup GitHub Pages» en
  Namecheap: apunta el dominio a GitHub.

## Endurecimiento tras la migración (18/11/2026)

Revisión de seguridad con ataques simulados contra `proctoring-upao.app` y `api.proctoring-upao.app`:

| Qué | Cómo queda |
|---|---|
| TLS | Solo 1.2 y 1.3, cifrados AEAD con ECDHE (`/etc/dokploy/traefik/dynamic/proctoring-tls.yml`). Sin SNI válido no hay certificado (`sniStrict`). Se apagaron los CBC-SHA1 que aceptaba por defecto. |
| Cabeceras | HSTS y sin `Server` en **todo** HTTPS: el middleware `proctoring-seguridad@file` va en el entrypoint `websecure` de `traefik.yml`, no en cada router (Dokploy reescribe los routers al cambiar dominios y lo perdía). |
| Tamaño de petición | 4 MB como máximo antes de llegar a la API (`proctoring-limite-cuerpo@file`); lo más grande legítimo es un QTI de 1 MB. Antes un cuerpo de 12 MB llegaba entero a uvicorn. |
| Archivos ocultos | `/.env`, `/.git/…` responden 404 (`deploy/nginx.conf`); antes 200 con `index.html`. No filtraban nada, pero confundían a los escáneres. |
| Tokens | `alg: none`, firma HS256 falsa, basura y sin token: 401 en todas las rutas. |
| CORS | Solo `proctoring-upao.app` y el alias de sslip.io; Vercel se quitó. |
| Frecuencia | `POST /sessions/join`: 429 a partir del décimo intento seguido. |
| Puertos | Desde fuera, solo 22, 80 y 443. |
| Supabase | RLS en todas las tablas, sin buckets públicos, todo registro nuevo es `student`. |
| Dependencias | `npm audit` y `pip-audit` sin hallazgos tras subir `filelock` y `setuptools` en `services/ai`. |
| SSH | Solo llave, `admin` con la contraseña bloqueada, fail2ban (5 fallos en 10 min → 1 h). |
