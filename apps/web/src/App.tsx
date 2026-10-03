import { BrowserRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { ProveedorAuth } from './lib/auth'
import { useAuth } from './lib/auth-context'
import { authEnabled } from './lib/supabase'
import { Login } from './pages/Login'
import { Sesiones } from './pages/Sesiones'
import { NuevaSesion } from './pages/NuevaSesion'
import { SesionEnVivo } from './pages/SesionEnVivo'

function Cabecera() {
  const { email, salir } = useAuth()

  return (
    <header className="cabecera">
      <div className="contenedor">
        <NavLink to="/sesiones" className="marca">
          Proc<span>toring</span>
        </NavLink>

        <nav className="navegacion">
          <NavLink to="/sesiones" className={({ isActive }) => (isActive ? 'activo' : '')}>
            Exámenes
          </NavLink>
          <NavLink to="/sesiones/nueva" className={({ isActive }) => (isActive ? 'activo' : '')}>
            Crear
          </NavLink>
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

/** Deja pasar solo al docente autenticado; sin autenticación, deja pasar. */
function Privado({ children }: { children: React.ReactNode }) {
  const { cargando, token } = useAuth()

  if (!authEnabled) return <>{children}</>
  if (cargando) return <div className="vacio">Cargando…</div>
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

function Aplicacion() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="*"
          element={
            <Privado>
              <Cabecera />
              <main className="principal">
                <div className="contenedor">
                  <Routes>
                    <Route path="/" element={<Navigate to="/sesiones" replace />} />
                    <Route path="/sesiones" element={<Sesiones />} />
                    <Route path="/sesiones/nueva" element={<NuevaSesion />} />
                    <Route path="/sesiones/:id" element={<SesionEnVivo />} />
                    <Route path="*" element={<NoEncontrado />} />
                  </Routes>
                </div>
              </main>
            </Privado>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

function NoEncontrado() {
  return (
    <div className="vacio">
      <h3>Esa página no existe</h3>
      <p className="subtitulo">Revisa el enlace o vuelve a tus exámenes.</p>
    </div>
  )
}

export default function App() {
  return (
    <ProveedorAuth>
      <Aplicacion />
    </ProveedorAuth>
  )
}
