import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { CapaExamen, CapaPanel, CapaPublica } from './components/Capas'
import { ProveedorAuth } from './lib/auth'
import { useAuth } from './lib/auth-context'
import { inicioSegunRol, type Rol } from './lib/rutas'
import { authEnabled } from './lib/supabase'
import { AccesoExamen } from './pages/AccesoExamen'
import { Banco } from './pages/Banco'
import { Bancos } from './pages/Bancos'
import { Curso } from './pages/Curso'
import { EditarSesion } from './pages/EditarSesion'
import { Cursos } from './pages/Cursos'
import { Login } from './pages/Login'
import { NuevaSesion } from './pages/NuevaSesion'
import { PanelDocente } from './pages/PanelDocente'
import { PanelEstudiante } from './pages/PanelEstudiante'
import { Participantes } from './pages/Participantes'
import { Portada } from './pages/Portada'
import { RevisionCaso } from './pages/RevisionCaso'
import { Preguntas } from './pages/Preguntas'
import { RendirExamen } from './pages/RendirExamen'
import { SalaDeEspera } from './pages/SalaDeEspera'
import { SesionEnVivo } from './pages/SesionEnVivo'
import { Sesiones } from './pages/Sesiones'

/**
 * Deja pasar solo a quien corresponde.
 *
 * Esta comprobación es de **navegación**, no de seguridad: evita que alguien
 * aterrice en una pantalla que no le sirve. Quien protege los datos de verdad
 * es la API, que valida el token y el rol en cada petición.
 */
function Zona({ rol: rolRequerido, children }: { rol: Rol; children: ReactNode }) {
  const { cargando, token, rol } = useAuth()

  if (!authEnabled) return <>{children}</>
  if (cargando) return <div className="vacio">Cargando…</div>
  if (!token) return <Navigate to="/login" replace />
  // El rol llega un instante después del token: no se expulsa a nadie mientras
  // tanto, o el docente vería parpadear la pantalla del estudiante.
  if (rol && rol !== rolRequerido) return <Navigate to={inicioSegunRol(rol)} replace />
  return <>{children}</>
}

/** Una pantalla del docente, con su barra lateral. */
function Docente({ children }: { children: ReactNode }) {
  return (
    <Zona rol="teacher">
      <CapaPanel rol="teacher">{children}</CapaPanel>
    </Zona>
  )
}

/** Una pantalla del estudiante, con su barra lateral. */
function Estudiante({ children }: { children: ReactNode }) {
  return (
    <Zona rol="student">
      <CapaPanel rol="student">{children}</CapaPanel>
    </Zona>
  )
}

function NoEncontrado() {
  return (
    <CapaPublica>
      <div className="contenedor principal">
        <div className="vacio">
          <h3>Esa página no existe</h3>
          <p className="subtitulo">Revisa el enlace o vuelve al inicio.</p>
        </div>
      </div>
    </CapaPublica>
  )
}

function Aplicacion() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Público */}
        <Route path="/" element={<Portada />} />
        <Route path="/login" element={<Login />} />

        {/* Docente */}
        <Route
          path="/docente"
          element={
            <Docente>
              <PanelDocente />
            </Docente>
          }
        />
        <Route
          path="/cursos"
          element={
            <Docente>
              <Cursos />
            </Docente>
          }
        />
        <Route
          path="/cursos/:id"
          element={
            <Docente>
              <Curso />
            </Docente>
          }
        />
        <Route
          path="/bancos"
          element={
            <Docente>
              <Bancos />
            </Docente>
          }
        />
        <Route
          path="/bancos/:id"
          element={
            <Docente>
              <Banco />
            </Docente>
          }
        />
        <Route
          path="/sesiones"
          element={
            <Docente>
              <Sesiones />
            </Docente>
          }
        />
        <Route
          path="/sesiones/nueva"
          element={
            <Docente>
              <NuevaSesion />
            </Docente>
          }
        />
        <Route
          path="/sesiones/:id"
          element={
            <Docente>
              <SesionEnVivo />
            </Docente>
          }
        />
        <Route
          path="/sesiones/:id/editar"
          element={
            <Docente>
              <EditarSesion />
            </Docente>
          }
        />
        <Route
          path="/sesiones/:id/preguntas"
          element={
            <Docente>
              <Preguntas />
            </Docente>
          }
        />
        <Route
          path="/sesiones/:id/participantes"
          element={
            <Docente>
              <Participantes />
            </Docente>
          }
        />

        <Route
          path="/sesiones/:id/estudiantes/:estudianteId"
          element={
            <Docente>
              <RevisionCaso />
            </Docente>
          }
        />

        {/* Estudiante */}
        <Route
          path="/estudiante"
          element={
            <Estudiante>
              <PanelEstudiante />
            </Estudiante>
          }
        />
        <Route
          path="/examen"
          element={
            <Estudiante>
              <AccesoExamen />
            </Estudiante>
          }
        />
        <Route
          path="/examen/:id/sala"
          element={
            <Estudiante>
              <SalaDeEspera />
            </Estudiante>
          }
        />

        {/* Rindiendo: sin barra lateral ni un solo enlace de salida. */}
        <Route
          path="/examen/:id/rendir"
          element={
            <Zona rol="student">
              <CapaExamen>
                <RendirExamen />
              </CapaExamen>
            </Zona>
          }
        />

        <Route path="*" element={<NoEncontrado />} />
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
