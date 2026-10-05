import { Link, Navigate } from 'react-router-dom'
import { CapaPublica } from '../components/Capas'
import { useAuth } from '../lib/auth-context'
import { inicioSegunRol } from '../lib/rutas'
import { authEnabled } from '../lib/supabase'

/**
 * La portada: lo primero que ve quien no ha iniciado sesión.
 *
 * Explica qué es el sistema antes de pedir credenciales. Quien ya tiene sesión
 * no pasa por aquí: va directo a su panel.
 *
 * **Dice solo lo que el sistema hace.** Las capacidades que todavía no existen
 * llevan la etiqueta "En desarrollo" en vez de venderse como hechas: una
 * portada que promete más de lo que hay es lo primero que un docente evaluador
 * detecta.
 */

type Estado = 'listo' | 'desarrollo'

interface Capacidad {
  titulo: string
  texto: string
  estado: Estado
  icono: 'pantalla' | 'rostro' | 'ojo' | 'voz'
}

const CAPACIDADES: Capacidad[] = [
  {
    titulo: 'Entorno del equipo',
    texto:
      'Salidas de la ventana del examen, monitores adicionales y aplicaciones de captura, control remoto o máquinas virtuales.',
    estado: 'listo',
    icono: 'pantalla'
  },
  {
    titulo: 'Identidad',
    texto:
      'Verificación por rostro al entrar. Si la cámara no reconoce a alguien por la luz, el docente lo admite a mano.',
    estado: 'desarrollo',
    icono: 'rostro'
  },
  {
    titulo: 'Mirada y presencia',
    texto: 'Mirada fuera de la pantalla, rostro ausente y una segunda persona en cámara.',
    estado: 'desarrollo',
    icono: 'ojo'
  },
  {
    titulo: 'Consulta a una IA por voz',
    texto:
      'Compara lo que el estudiante dice en voz alta con la pregunta en curso. Leerla para concentrarse no genera alerta.',
    estado: 'desarrollo',
    icono: 'voz'
  }
]

const PASOS = [
  {
    titulo: 'El docente crea el examen',
    texto: 'Elige el nivel de supervisión, escribe las preguntas y recibe un código de acceso.'
  },
  {
    titulo: 'El estudiante entra y acepta',
    texto:
      'Escribe el código, lee qué se va a observar y lo acepta. Sin esa aceptación no recibe ni una pregunta.'
  },
  {
    titulo: 'Se registran señales, no video',
    texto:
      'Durante el examen se guardan avisos puntuales y la evidencia asociada. No se graba ni se envía video continuo.'
  },
  {
    titulo: 'El docente revisa y decide',
    texto:
      'Ve las señales con su evidencia y resuelve. La decisión lleva una justificación escrita.'
  }
]

const PRINCIPIOS = [
  {
    titulo: 'Auditor, no juez',
    texto:
      'El sistema calcula un nivel de riesgo desglosado por señal y entrega evidencia. Nunca anula un examen por su cuenta.'
  },
  {
    titulo: 'Sin video continuo',
    texto:
      'La detección liviana corre en el equipo del estudiante. Solo salen eventos, capturas puntuales y fragmentos de audio con habla.'
  },
  {
    titulo: 'Consentimiento explícito',
    texto:
      'El estudiante ve, antes de empezar, cada cosa que se observa. La supervisión comienza después de que acepta, no antes.'
  }
]

function Icono({ tipo }: { tipo: Capacidad['icono'] }) {
  // Trazos simples a mano: nada de librerías de iconos para cuatro dibujos.
  const comun = {
    width: 28,
    height: 28,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true
  }
  switch (tipo) {
    case 'pantalla':
      return (
        <svg {...comun}>
          <rect x="3" y="4" width="18" height="12" rx="1.5" />
          <path d="M8 20h8M12 16v4" />
        </svg>
      )
    case 'rostro':
      return (
        <svg {...comun}>
          <circle cx="12" cy="9" r="3.5" />
          <path d="M5 20c.8-3.6 3.5-5.5 7-5.5s6.2 1.9 7 5.5" />
        </svg>
      )
    case 'ojo':
      return (
        <svg {...comun}>
          <path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12Z" />
          <circle cx="12" cy="12" r="2.8" />
        </svg>
      )
    case 'voz':
      return (
        <svg {...comun}>
          <rect x="9" y="3" width="6" height="11" rx="3" />
          <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3" />
        </svg>
      )
  }
}

export function Portada() {
  const { token, rol } = useAuth()

  // Quien ya tiene sesión no necesita la portada: va a lo suyo.
  if (authEnabled && token && rol) return <Navigate to={inicioSegunRol(rol)} replace />

  return (
    <CapaPublica>
      <section className="portada-inicio">
        <div className="contenedor">
          <p className="portada-lema">Exámenes remotos con supervisión transparente</p>
          <h1>
            Detecta. Documenta.
            <br />
            Decide el docente.
          </h1>
          <p className="portada-resumen">
            Una plataforma que aloja sus propios exámenes, supervisa al estudiante mientras los
            rinde y entrega al docente la evidencia, no un veredicto.
          </p>
          <div className="fila">
            <Link to={authEnabled ? '/login' : '/docente'} className="boton boton-grande">
              {authEnabled ? 'Iniciar sesión' : 'Entrar'}
            </Link>
            <a href="#como-funciona" className="boton boton-grande boton-claro">
              Cómo funciona
            </a>
          </div>
        </div>
      </section>

      <section className="portada-seccion" id="que-detecta">
        <div className="contenedor">
          <h2>Qué observa</h2>
          <p className="subtitulo portada-sub">
            Cuatro tipos de señal, cada una con su propio módulo
          </p>

          <div className="rejilla-capacidades">
            {CAPACIDADES.map((c) => (
              <article key={c.titulo} className="capacidad">
                <span className="capacidad-icono">
                  <Icono tipo={c.icono} />
                </span>
                <h3>{c.titulo}</h3>
                <p>{c.texto}</p>
                <span
                  className={c.estado === 'listo' ? 'etiqueta-estado listo' : 'etiqueta-estado'}
                >
                  {c.estado === 'listo' ? 'Disponible' : 'En desarrollo'}
                </span>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="portada-seccion portada-gris" id="como-funciona">
        <div className="contenedor">
          <h2>Cómo funciona</h2>
          <p className="subtitulo portada-sub">De la creación del examen a la decisión</p>

          <ol className="pasos">
            {PASOS.map((paso) => (
              <li key={paso.titulo}>
                <h3>{paso.titulo}</h3>
                <p>{paso.texto}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="portada-seccion" id="principios">
        <div className="contenedor">
          <h2>Principios</h2>
          <p className="subtitulo portada-sub">Lo que el sistema se compromete a no hacer</p>

          <div className="rejilla-principios">
            {PRINCIPIOS.map((p) => (
              <article key={p.titulo}>
                <h3>{p.titulo}</h3>
                <p>{p.texto}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="portada-seccion portada-oscura">
        <div className="contenedor">
          <div className="rejilla-roles">
            <div>
              <h2>Si eres docente</h2>
              <ul>
                <li>Crea exámenes con preguntas de cinco tipos.</li>
                <li>Elige el nivel de supervisión: básica, estándar o estricta.</li>
                <li>Admite a mano a quien la cámara no reconozca.</li>
                <li>Recibe las alertas mientras el examen ocurre.</li>
              </ul>
            </div>
            <div>
              <h2>Si eres estudiante</h2>
              <ul>
                <li>Entra con el código que te dio tu docente.</li>
                <li>Ve qué se observa antes de aceptar.</li>
                <li>Tus respuestas se guardan solas mientras escribes.</li>
                <li>Consulta tus exámenes entregados desde tu panel.</li>
              </ul>
            </div>
          </div>
          <p className="portada-cierre">
            <Link to={authEnabled ? '/login' : '/docente'} className="boton boton-grande">
              {authEnabled ? 'Iniciar sesión' : 'Entrar'}
            </Link>
          </p>
        </div>
      </section>
    </CapaPublica>
  )
}
