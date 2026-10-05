/** A dónde lleva cada rol al entrar, en un solo sitio. */

export type Rol = 'teacher' | 'student'

/**
 * El panel de cada rol.
 *
 * Sin rol —la web sin autenticación, o el instante entre el token y el perfil—
 * se vuelve a la portada: no se adivina un panel.
 */
export function inicioSegunRol(rol?: Rol): string {
  if (rol === 'teacher') return '/docente'
  if (rol === 'student') return '/estudiante'
  return '/'
}
