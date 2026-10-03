import { BrowserRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { ProveedorAuth } from './lib/auth'
import { useAuth } from './lib/auth-context'
import { authEnabled } from './lib/supabase'
import { Login } from './pages/Login'
import { Sesiones } from './pages/Sesiones'
import { NuevaSesion } from './pages/NuevaSesion'
import { SesionEnVivo } from './pages/SesionEnVivo'
import { AccesoExamen } from './pages/AccesoExamen'
import { SalaDeEspera } from './pages/SalaDeEspera'

/** A dónde va cada quien al entrar. Sin autenticación, al panel del docente,
 *  que es la pantalla desde la que se crea todo lo demás. */
function inicioSegunRol(rol?: 'teacher' | 'student'): string {
  return rol === 'student' ? '/examen' : '/sesiones'
}

function Cabecera() {
  const { rol, email, salir } = useAuth()
  const esEstudiante = rol === 'student'
  // Sin autenticación se muestran las dos zonas: es el modo de desarrollo y
  // conviene poder recorrer todo el flujo sin crear usuarios.
  const verDocente = !authEnabled || !esEstudiante
  const verEstudiante = !authEnabled || esEstudiante

  return (
    <header className="cabecera">
      <div className="contenedor">
        <NavLink to={inicioSegunRol(rol)} className="marca">
          Proc<span>toring</span>
        </NavLink>

        <nav className="navegacion">
          {verDocente && (
            <>
              <NavLink to="/sesiones" className={({ isActive }) => (isActive ? 'activo' : '')}>
                Exámenes
              </NavLink>
              <NavLink to="/sesiones/nueva" className={({ isActive }) => (isActive ? 'activo' : '')}>
                Crear
              </NavLink>
            </>
          )}
          {verEstudiante && (
            <NavLink to="/examen" className={({ isActive }) => (isActive ? 'activo' : '')}>
              Entrar a un examen
            </NavLink>
          )}
          {authEnabled && (
            <button type="button" className="boton boton-texto" onClick={() => void salir()}>
              Salir
            </button>
          )}
        </nav>
      </div>
      {email && (
        <span className="sr-only" aria-live="polite">
          Sesión de {email}
        </span>
      )}
    </header>
  )
}

/**
 * Deja pasar solo a quien corresponde.
 *
 * Esta comprobación es de **navegación**, no de seguridad: evita que alguien
 * aterrice en una pantalla que no le sirve. Quien protege los datos de verdad
 * es la API, que valida el token y el rol en cada petición.
 */
function Zona({ rol: rolRequerido, children }: { rol?: 'teacher' | 'student'; children: React.ReactNode }) {
  const { cargando, token, rol } = useAuth()

  if (!authEnabled) return <>{children}</>
  if (cargando) return <div className="vacio">Cargando…</div>
  if (!token) return <Navigate to="/login" replace />
  // El rol llega un instante después del token: no se expulsa a nadie mientras
  // tanto, o el docente vería parpadear la pantalla del estudiante.
  if (rolRequerido && rol && rol !== rolRequerido) {
    return <Navigate to={inicioSegunRol(rol)} replace />
  }
  return <>{children}</>
}

function Marco({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Cabecera />
      <main className="principal">
        <div className="contenedor">{children}</div>
      </main>
    </>
  )
}

function Inicio() {
  const { rol } = useAuth()
  return <Navigate to={inicioSegunRol(rol)} replace />
}

function NoEncontrado() {
  return (
    <div className="vacio">
      <h3>Esa página no existe</h3>
      <p className="subtitulo">Revisa el enlace o vuelve al inicio.</p>
    </div>
  )
}

function Aplicacion() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />

        {/* Docente */}
        <Route
          path="/sesiones/*"
          element={
            <Zona rol="teacher">
              <Marco>
                <Routes>
                  <Route path="/" element={<Sesiones />} />
                  <Route path="/nueva" element={<NuevaSesion />} />
                  <Route path="/:id" element={<SesionEnVivo />} />
                  <Route path="*" element={<NoEncontrado />} />
                </Routes>
              </Marco>
            </Zona>
          }
        />

        {/* Estudiante */}
        <Route
          path="/examen/*"
          element={
            <Zona rol="student">
              <Marco>
                <Routes>
                  <Route path="/" element={<AccesoExamen />} />
                  <Route path="/:id/sala" element={<SalaDeEspera />} />
                  <Route path="*" element={<NoEncontrado />} />
                </Routes>
              </Marco>
            </Zona>
          }
        />

        <Route
          path="*"
          element={
            <Zona>
              <Inicio />
            </Zona>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

export default function App() {
  return (
    <ProveedorAuth>
      <Aplicacion />
    </ProveedorAuth>
  )
}
