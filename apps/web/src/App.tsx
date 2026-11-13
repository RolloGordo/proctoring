import { Suspense, lazy, useEffect, type ReactNode } from 'react'
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigationType,
  useParams
} from 'react-router-dom'
import { CapaExamen, CapaPanel, CapaPublica } from './components/Capas'
import { RequireDesktopExam } from './components/RequireDesktopExam'
import { ProveedorAuth } from './lib/auth'
import { useAuth } from './lib/auth-context'
import { inicioSegunRol, type Rol } from './lib/rutas'
import { authEnabled } from './lib/supabase'
import { AccesoExamen } from './pages/AccesoExamen'
import { Banco } from './pages/Banco'
import { Bancos } from './pages/Bancos'
import { Curso } from './pages/Curso'
import { EditorExamen } from './pages/EditorExamen'
import { Cursos } from './pages/Cursos'
import { Login } from './pages/Login'
import { NuevaSesion } from './pages/NuevaSesion'
import { PanelDocente } from './pages/PanelDocente'
import { PanelEstudiante } from './pages/PanelEstudiante'
import { DetalleExamenEstudiante } from './pages/DetalleExamenEstudiante'
import { CursoEstudiante } from './pages/CursoEstudiante'
import { Portada } from './pages/Portada'
import { Privacidad } from './pages/Privacidad'
import { RevisionCaso } from './pages/RevisionCaso'
import { SalaDeEspera } from './pages/SalaDeEspera'
import { Sesiones } from './pages/Sesiones'
import { pageTitle } from './lib/exam-progress'

/**
 * La pantalla del examen se carga solo al entrar en ella.
 *
 * Arrastra MediaPipe, que son unos 140 kB que el panel del docente no usa
 * para nada. Sin esto, abrir «Mis exámenes» descarga el modelo de visión.
 */
const RendirExamen = lazy(async () => {
  const modulo = await import('./pages/RendirExamen')
  return { default: modulo.RendirExamen }
})

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

function EstudianteEnExamen({
  children,
  rindiendo = false
}: {
  children: ReactNode
  rindiendo?: boolean
}) {
  const contenido = window.api ? (
    rindiendo ? (
      <CapaExamen>{children}</CapaExamen>
    ) : (
      <CapaPanel rol="student">{children}</CapaPanel>
    )
  ) : (
    <RequireDesktopExam>{children}</RequireDesktopExam>
  )
  return <Zona rol="student">{contenido}</Zona>
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

function TituloRuta() {
  const { pathname } = useLocation()

  useEffect(() => {
    document.title = pageTitle(pathname)
  }, [pathname])

  return null
}

/**
 * Cada página nueva empieza arriba.
 *
 * El navegador no lo hace solo en una SPA: al ir de la portada, ya
 * desplazada hasta el pie, a «Iniciar sesión», el acceso se abría desplazado
 * hasta abajo (visto el 13/11/2026). Con un ancla (`/#como-funciona`) se va a
 * ella, aunque la sección tarde en existir.
 */
function ScrollAlCambiarDePagina() {
  const { pathname, hash } = useLocation()
  const tipo = useNavigationType()

  useEffect(() => {
    // Atrás y adelante sin ancla: el navegador ya devuelve cada página a donde
    // estaba. Con ancla sí se busca, también al abrir la página desde fuera
    // (que React Router cuenta como `POP`): el salto nativo del navegador llega
    // antes de que exista la sección y no hace nada.
    if (tipo === 'POP' && !hash) return
    if (!hash) {
      window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
      return
    }
    // La página de destino puede cargarse aparte (la portada es un trozo
    // propio): el ancla todavía no existe cuando cambia la ruta. Se la busca en
    // cada fotograma hasta 3 s, y si nunca aparece se queda arriba.
    // Y una vez encontrada se la mantiene alineada 1,5 s, porque lo de arriba
    // (fotos, la burbuja) cambia de alto mientras carga y la dejaba corrida.
    // Si la persona hace scroll, se la suelta.
    const id = decodeURIComponent(hash.slice(1))
    const inicio = performance.now()
    let encontrada: number | null = null
    let cuadro = 0
    let soltar = false
    const alTocar = () => {
      soltar = true
    }
    window.addEventListener('wheel', alTocar, { passive: true, once: true })
    window.addEventListener('touchstart', alTocar, { passive: true, once: true })
    window.addEventListener('keydown', alTocar, { once: true })
    const buscar = () => {
      if (soltar) return
      const ahora = performance.now()
      const destino = document.getElementById(id)
      if (destino) {
        encontrada ??= ahora
        if (Math.abs(destino.getBoundingClientRect().top) > 4) destino.scrollIntoView()
        if (ahora - encontrada < 1500) cuadro = requestAnimationFrame(buscar)
      } else if (ahora - inicio < 3000) {
        cuadro = requestAnimationFrame(buscar)
      }
    }
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
    buscar()
    return () => {
      cancelAnimationFrame(cuadro)
      window.removeEventListener('wheel', alTocar)
      window.removeEventListener('touchstart', alTocar)
      window.removeEventListener('keydown', alTocar)
    }
  }, [pathname, hash, tipo])

  return null
}

function RedirigirSeccionExamen({ vista }: { vista: 'contenido' | 'participantes' | 'entregas' | 'actividad' | 'ajustes' }) {
  const { id = '' } = useParams()
  return <Navigate to={`/sesiones/${id}/editar?vista=${vista}`} replace />
}

function Aplicacion() {
  return (
    <BrowserRouter>
      <TituloRuta />
      <ScrollAlCambiarDePagina />
      <Routes>
        {/* Público */}
        <Route path="/" element={<Portada />} />
        <Route path="/login" element={<Login />} />
        <Route path="/privacidad" element={<Privacidad />} />

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
              <RedirigirSeccionExamen vista="actividad" />
            </Docente>
          }
        />
        <Route
          path="/sesiones/:id/editar"
          element={
            <Docente>
              <EditorExamen />
            </Docente>
          }
        />
        <Route
          path="/sesiones/:id/ajustes"
          element={
            <Docente>
              <RedirigirSeccionExamen vista="ajustes" />
            </Docente>
          }
        />
        <Route
          path="/sesiones/:id/preguntas"
          element={
            <Docente>
              <RedirigirSeccionExamen vista="contenido" />
            </Docente>
          }
        />
        <Route
          path="/sesiones/:id/participantes"
          element={
            <Docente>
              <RedirigirSeccionExamen vista="participantes" />
            </Docente>
          }
        />
        <Route
          path="/sesiones/:id/resultados"
          element={
            <Docente>
              <RedirigirSeccionExamen vista="entregas" />
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
          path="/estudiante/cursos/:id"
          element={
            <Estudiante>
              <CursoEstudiante />
            </Estudiante>
          }
        />
        <Route
          path="/estudiante/examenes/:id"
          element={
            <Estudiante>
              <DetalleExamenEstudiante />
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
            <EstudianteEnExamen>
              <SalaDeEspera />
            </EstudianteEnExamen>
          }
        />

        {/* Rindiendo: sin barra lateral ni un solo enlace de salida. */}
        <Route
          path="/examen/:id/rendir"
          element={
            <EstudianteEnExamen rindiendo>
              <Suspense fallback={<p className="tenue">Cargando examen…</p>}>
                <RendirExamen />
              </Suspense>
            </EstudianteEnExamen>
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
