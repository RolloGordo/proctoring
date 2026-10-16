/**
 * Avisar de que hay una versión nueva de la aplicación.
 *
 * **Avisa, no actualiza.** La diferencia es deliberada y conviene saber por qué:
 *
 * - Un instalador de Windows sin firmar no se puede reemplazar solo de forma
 *   fiable. `electron-updater` verifica la firma del publicador antes de
 *   instalar, y sin certificado —que cuesta dinero y hay que renovar— esa
 *   comprobación o falla o hay que desactivarla, que es peor.
 * - Y en una aplicación de supervisión, que un binario se sustituya solo en el
 *   equipo del estudiante es justo lo que no queremos tener que explicar. Que
 *   el estudiante descargue y vea lo que instala es más defendible.
 *
 * Así que esto consulta la última publicación en GitHub, compara versiones y,
 * si hay una más nueva, lo dice y ofrece abrir la página de descargas.
 *
 * **Nunca durante un examen.** Se comprueba al abrir la aplicación y nada más:
 * un diálogo encima de alguien que está rindiendo es exactamente la clase de
 * interrupción que el proyecto promete no causar.
 */

const REPO = 'RolloGordo/proctoring'
const API = `https://api.github.com/repos/${REPO}/releases/latest`
export const PAGINA_DESCARGAS = `https://github.com/${REPO}/releases/latest`

/** Lo que tarda como mucho en responder GitHub antes de darlo por perdido. */
const TIEMPO_LIMITE_MS = 5_000

/**
 * Compara dos versiones semánticas.
 *
 * Devuelve `true` si `candidata` es posterior a `actual`. Compara número a
 * número, no como texto: `"0.10.0" > "0.9.0"` es falso si se comparan cadenas,
 * y ese es justo el salto donde se rompería.
 *
 * Lo que no sepa leer lo trata como "no es más nueva": ante la duda, no molestar.
 */
export function esMasNueva(candidata: string, actual: string): boolean {
  const partes = (version: string): number[] | null => {
    const limpia = version.trim().replace(/^v/i, '').split('-')[0]
    const numeros = limpia.split('.').map((n) => Number(n))
    if (numeros.length === 0 || numeros.some((n) => !Number.isInteger(n) || n < 0)) return null
    return numeros
  }

  const a = partes(candidata)
  const b = partes(actual)
  if (!a || !b) return false

  for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
    const uno = a[i] ?? 0
    const otro = b[i] ?? 0
    if (uno !== otro) return uno > otro
  }
  return false
}

/** Lo poco que nos interesa de una publicación de GitHub. */
export interface VersionPublicada {
  version: string
  url: string
}

/**
 * Pregunta por la última versión publicada.
 *
 * Devuelve `null` si no hay ninguna, si GitHub no responde o si responde algo
 * que no entendemos. **Ningún fallo aquí puede impedir abrir la aplicación**:
 * quedarse sin examen porque GitHub está caído sería mucho peor que no enterarse
 * de una actualización.
 */
export async function ultimaVersion(
  fetchImpl: typeof fetch = fetch
): Promise<VersionPublicada | null> {
  try {
    const respuesta = await fetchImpl(API, {
      headers: { Accept: 'application/vnd.github+json' },
      signal: AbortSignal.timeout(TIEMPO_LIMITE_MS)
    })
    if (!respuesta.ok) return null
    const cuerpo: unknown = await respuesta.json()
    const etiqueta = (cuerpo as { tag_name?: unknown })?.tag_name
    if (typeof etiqueta !== 'string' || !etiqueta) return null
    const pagina = (cuerpo as { html_url?: unknown })?.html_url
    return {
      version: etiqueta.replace(/^v/i, ''),
      url: typeof pagina === 'string' && pagina ? pagina : PAGINA_DESCARGAS
    }
  } catch {
    return null
  }
}

/**
 * Comprueba si hay una versión nueva y devuelve cuál, o `null`.
 *
 * Separado de quien enseña el diálogo para poder probarlo sin Electron.
 */
export async function hayActualizacion(
  versionActual: string,
  fetchImpl: typeof fetch = fetch
): Promise<VersionPublicada | null> {
  const publicada = await ultimaVersion(fetchImpl)
  if (!publicada) return null
  return esMasNueva(publicada.version, versionActual) ? publicada : null
}
