/**
 * La URL de la API que corresponde al dominio desde el que se abrió la web.
 *
 * La misma web se sirve en dos dominios (`proctoring-upao.app` y
 * `proctoring-upao.me`), con un solo build. Llamar siempre a la API del `.app`
 * no sirve: la red de la universidad bloquea `.app` y `.dev` (26/11/2026), así
 * que desde el campus la página `.me` cargaría y luego todas sus llamadas
 * fallarían. Cada dominio tiene su API al lado (`api.<dominio>`), y esto elige
 * la de quien la está mirando.
 *
 * `VITE_API_POR_DOMINIO` es una lista `dominio=url` separada por comas. Si el
 * dominio actual no está en ella, se usa `VITE_API_URL`, como antes.
 */
export function baseApi(
  porDefecto: string | undefined = import.meta.env.VITE_API_URL,
  mapa: string | undefined = import.meta.env.VITE_API_POR_DOMINIO,
  dominio: string | undefined = globalThis.location?.hostname
): string {
  const elegida = dominio ? apiDelDominio(mapa, dominio) : undefined
  return (elegida ?? porDefecto ?? 'http://localhost:8000').replace(/\/$/, '')
}

function apiDelDominio(mapa: string | undefined, dominio: string): string | undefined {
  for (const par of (mapa ?? '').split(',')) {
    const [clave, url] = par.split('=').map((x) => x.trim())
    // Solo HTTPS: una entrada mal escrita no puede mandar tokens en claro.
    if (clave && url && clave.toLowerCase() === dominio.toLowerCase() && url.startsWith('https://'))
      return url
  }
  return undefined
}
