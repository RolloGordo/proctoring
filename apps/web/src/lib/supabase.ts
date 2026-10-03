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

const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

export const supabase: SupabaseClient | null =
  url && key ? createClient(url, key, { auth: { persistSession: true } }) : null

/** Si la web tiene que pedir credenciales. */
export const authEnabled = supabase !== null
