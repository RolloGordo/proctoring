import { useState, type ReactNode } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth-context'
import { inicioSegunRol, type Rol } from '../lib/rutas'
import { authEnabled } from '../lib/supabase'

/**
 * Las tres "capas" que envuelven a las pantallas.
 *
 * - **Pública:** la portada y el acceso. Cabecera con la marca y el botón de
 *   entrar.
 * - **Panel:** lo que ve alguien con sesión. Barra lateral con lo que su rol
 *   puede hacer, que es lo que pidió el equipo: el docente y el estudiante ven
 *   herramientas distintas y no tienen por qué ver las del otro.
 * - **Examen:** quien está rindiendo. **Sin navegación**, a propósito: durante
 *   un examen supervisado no hay a dónde ir, y ofrecer enlaces sería ofrecer
 *   formas de abandonarlo por accidente. Respondus y Moodle hacen lo mismo.
 */

interface Enlace {
  a: string
  texto: string
  /** Si el enlace cuenta como activo en esta ruta. Más fino que `NavLink`. */
  activo: (ruta: string) => boolean
}

const ENLACES: Record<Rol, Enlace[]> = {
  teacher: [
    { a: '/docente', texto: 'Panel', activo: (r) => r === '/docente' },
    {
      a: '/sesiones',
      texto: 'Mis exámenes',
      // "Crear" tiene su propio enlace: sin esta excepción se encenderían los dos.
      activo: (r) => r.startsWith('/sesiones') && r !== '/sesiones/nueva'
    },
    { a: '/sesiones/nueva', texto: 'Crear examen', activo: (r) => r === '/sesiones/nueva' },
    { a: '/bancos', texto: 'Bancos de preguntas', activo: (r) => r.startsWith('/bancos') },
    { a: '/cursos', texto: 'Mis cursos', activo: (r) => r.startsWith('/cursos') }
  ],
  student: [
    { a: '/estudiante', texto: 'Panel', activo: (r) => r === '/estudiante' },
    { a: '/examen', texto: 'Entrar a un examen', activo: (r) => r.startsWith('/examen') }
  ]
}

const NOMBRE_ROL: Record<Rol, string> = { teacher: 'Docente', student: 'Estudiante' }

function Marca({ a }: { a: string }) {
  return (
    <Link to={a} className="marca">
      Proc<span>toring</span>
    </Link>
  )
}

/** La portada, el acceso y las páginas que no existen. */
export function CapaPublica({ children }: { children: ReactNode }) {
  const { token, rol } = useAuth()
  const conSesion = authEnabled && token !== undefined

  // Sin autenticacion no hay login al que llevar: el boton entra directo al
  // panel, igual que el de la portada.
  const destino = conSesion ? inicioSegunRol(rol) : authEnabled ? '/login' : '/docente'
  const texto = conSesion ? 'Ir a mi panel' : authEnabled ? 'Iniciar sesión' : 'Entrar'

  return (
    <div className="publica">
      <header className="cabecera">
        <div className="contenedor">
          <Marca a="/" />
          <nav className="navegacion" aria-label="Principal">
            <a href="/#como-funciona" className="oculta-movil">
              Cómo funciona
            </a>
            <a href="/#principios" className="oculta-movil">
              Principios
            </a>
            <Link to={destino} className="boton boton-compacto">
              {texto}
            </Link>
          </nav>
        </div>
      </header>

      <main>{children}</main>

      <footer className="pie-publico">
        <div className="contenedor">
          <p>
            <strong>Proctoring</strong> · Proyecto de Taller Integrador 1, UPAO
          </p>
          <p className="tenue">El sistema es un auditor, no un juez: decide siempre el docente.</p>
        </div>
      </footer>
    </div>
  )
}

/** Barra lateral + contenido. `rol` decide qué herramientas se ofrecen. */
export function CapaPanel({ rol, children }: { rol: Rol; children: ReactNode }) {
  const { email, salir } = useAuth()
  const { pathname } = useLocation()
  const [abierto, setAbierto] = useState(false)
  const inicio = inicioSegunRol(rol)
  const otro: Rol = rol === 'teacher' ? 'student' : 'teacher'

  return (
    <div className="app">
      <header className="app-movil">
        <Marca a={inicio} />
        <button
          type="button"
          className="boton boton-texto"
          aria-expanded={abierto}
          aria-controls="barra-lateral"
          onClick={() => setAbierto((v) => !v)}
        >
          {abierto ? 'Cerrar' : 'Menú'}
        </button>
      </header>

      <aside id="barra-lateral" className={abierto ? 'lateral abierto' : 'lateral'}>
        <Marca a={inicio} />
        <p className="lateral-rol">{NOMBRE_ROL[rol]}</p>

        <nav className="lateral-nav" aria-label={`Menú del ${NOMBRE_ROL[rol].toLowerCase()}`}>
          {ENLACES[rol].map((enlace) => (
            <NavLink
              key={enlace.a}
              to={enlace.a}
              className={enlace.activo(pathname) ? 'activo' : ''}
              onClick={() => setAbierto(false)}
            >
              {enlace.texto}
            </NavLink>
          ))}
        </nav>

        <div className="lateral-pie">
          {authEnabled ? (
            <>
              {email && <p className="lateral-correo">{email}</p>}
              <button type="button" className="boton boton-texto" onClick={() => void salir()}>
                Cerrar sesión
              </button>
            </>
          ) : (
            <>
              <p className="lateral-correo">Modo desarrollo, sin cuentas</p>
              {/* Sin login no hay rol que decida: este enlace deja recorrer las dos mitades. */}
              <Link to={inicioSegunRol(otro)} className="lateral-cambio">
                Ver como {NOMBRE_ROL[otro].toLowerCase()}
              </Link>
            </>
          )}
        </div>
      </aside>

      {abierto && <div className="lateral-velo" onClick={() => setAbierto(false)} aria-hidden />}

      <main className="app-contenido">
        <div className="app-pagina">{children}</div>
      </main>
    </div>
  )
}

/** Quien está rindiendo: solo la marca y un recordatorio. Ni un enlace. */
export function CapaExamen({ children }: { children: ReactNode }) {
  return (
    <div className="examen-marco">
      <header className="examen-cabecera">
        <span className="marca">
          Proc<span>toring</span>
        </span>
        <span className="examen-aviso">
          <span className="punto punto-activo" aria-hidden />
          Supervisión activa
        </span>
      </header>
      <main className="examen-cuerpo">{children}</main>
    </div>
  )
}
