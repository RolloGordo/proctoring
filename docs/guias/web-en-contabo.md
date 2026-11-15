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

## El dominio del GitHub Student Developer Pack

Con el correo de la UPAO y el pack aprobado (1 a 7 días), se puede pedir gratis:

- **Namecheap:** un `.me` gratis por un año, con SSL incluido (no hace falta: Traefik ya lo da).
- **.TECH (get.tech):** un `.tech` gratis por un año.
- **Name.com:** un dominio de los que ofrezca el pack en ese momento.

Cualquiera sirve. En el panel del registrador basta con dos registros DNS:

| Tipo | Nombre | Valor |
|---|---|---|
| A | `@` | `86.48.18.81` |
| A | `api` | `86.48.18.81` |

Y el IPv6 si se quiere (`AAAA` a `2605:a144:2374:4408::1`). Traefik pide el certificado solo la
primera vez que alguien entra.

**Ojo con la renovación:** el dominio es gratis el primer año. Antes de que venza hay que renovarlo
(de pago) o volver al subdominio de `sslip.io`, que sigue funcionando sin hacer nada.
