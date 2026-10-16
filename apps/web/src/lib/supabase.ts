/**
 * Cliente de Supabase para el navegador.
 *
 * Usa la **clave publicable**, que es segura aquí porque RLS protege los datos
 * en la base. La service role key nunca sale del servidor.
 *
 * Si las variables no están configuradas, el cliente es `null` y la web
 * funciona sin autenticación, igual que la API con `AUTH_ENABLED=false`. Es el
 * modo de desarrollo local mientras el equipo termina sus módulos.
 */

import { createClient, type SupabaseClient } from '@supabase/supabase-js'

/**
 * Deja la URL del proyecto en lo que el cliente espera: **solo el origen**.
 *
 * El panel de Supabase enseña la dirección con `/rest/v1` en los ejemplos de la
 * API, y es fácil copiar esa. Pero el cliente añade él mismo `/auth/v1` o
 * `/rest/v1` según lo que vaya a hacer, así que con la ruta puesta construye
 * `/rest/v1/auth/v1/token` y el login falla con `PGRST125: Invalid path
 * specified in request URL`, un mensaje que no dice nada a quien lo ve.
 *
 * Se corrige en vez de fallar, porque quien lo sufre es el estudiante en la
 * pantalla de login y el problema está en un panel al que no tiene acceso. Pero
 * se avisa por consola: una configuración silenciosamente arreglada vuelve a
 * aparecer en el siguiente despliegue.
 */
export function origenDeSupabase(valor: string | undefined): string | undefined {
  if (!valor?.trim()) return undefined
  try {
    const url = new URL(valor.trim())
    if (url.pathname !== '/' && url.pathname !== '') {
      console.warn(
        `[supabase] VITE_SUPABASE_URL lleva una ruta ("${url.pathname}") y no debería. ` +
          `Se usará solo ${url.origin}. Corrígela en el panel de despliegue.`
      )
    }
    return url.origin
  } catch {
    console.error(`[supabase] VITE_SUPABASE_URL no es una dirección válida: ${valor}`)
    return undefined
  }
}

const url = origenDeSupabase(import.meta.env.VITE_SUPABASE_URL)
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

export const supabase: SupabaseClient | null =
  url && key ? createClient(url, key, { auth: { persistSession: true } }) : null

/** Si la web tiene que pedir credenciales. */
export const authEnabled = supabase !== null
