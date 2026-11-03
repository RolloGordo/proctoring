/**
 * Lo que se revisa del formulario de acceso antes de llamar a Supabase.
 *
 * Solo lo que se puede saber sin preguntarle a nadie: que haya correo, que
 * tenga forma de correo y que haya contraseña. Si eso falla, el mensaje va
 * junto al campo y dice qué arreglar; si pasa, la última palabra la tiene
 * Supabase. Así un campo vacío no gasta una petición ni vuelve en inglés.
 */

export type CampoAcceso = 'correo' | 'clave'

export type ErroresAcceso = Partial<Record<CampoAcceso, string>>

/** Algo@algo.algo, sin espacios: lo justo para pillar un correo mal tecleado. */
const FORMA_DE_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function revisarAcceso(correo: string, clave: string): ErroresAcceso {
  const errores: ErroresAcceso = {}
  const limpio = correo.trim()
  if (!limpio) errores.correo = 'Escribe tu correo institucional.'
  else if (!FORMA_DE_CORREO.test(limpio))
    errores.correo = 'Ese correo no está completo: revisa que tenga @ y el dominio.'
  // La contraseña no se recorta: un espacio puede ser parte de ella.
  if (!clave) errores.clave = 'Escribe tu contraseña.'
  return errores
}
