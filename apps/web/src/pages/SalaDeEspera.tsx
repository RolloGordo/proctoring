import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { fechaLarga } from '../lib/formato'
import type { JoinedExam } from '../lib/api'

/** Nombre legible de cada módulo de supervisión, para que el estudiante sepa
 *  qué se va a observar. Decírselo no es un trámite: es la base del
 *  consentimiento, y el sistema vigila, no espía. */
const MODULOS: Record<string, string> = {
  face_verification: 'Verificación de identidad por rostro',
  face_reverification: 'Reverificación de identidad durante el examen',
  focus_loss: 'Salidas de la ventana del examen',
  copy_paste_block: 'Bloqueo de copiar y pegar',
  multi_monitor: 'Monitores adicionales conectados',
  gaze: 'Mirada fuera de la pantalla',
  extra_person: 'Presencia de otra persona en cámara',
  objects: 'Objetos no permitidos',
  external_voices: 'Voces externas',
  ai_voice: 'Consulta a un asistente de IA por voz',
  live_monitoring: 'Supervisión en vivo por el docente',
  screen_capture: 'Aplicaciones de captura o control remoto'
}

export function SalaDeEspera() {
  const { state } = useLocation()
  const examen = state as JoinedExam | null
  const [ahora, setAhora] = useState(() => Date.now())

  // Un reloj por minuto basta: la cuenta atrás se mide en minutos, no en
  // segundos, y refrescar cada segundo solo gasta batería.
  useEffect(() => {
    const temporizador = setInterval(() => setAhora(Date.now()), 60_000)
    return () => clearInterval(temporizador)
  }, [])

  if (!examen) {
    return (
      <div className="centrado-estrecho">
        <div className="tarjeta">
          <div className="vacio">
            <h3>No encontramos ese examen</h3>
            <p className="subtitulo">Vuelve a escribir tu código de acceso.</p>
            <p style={{ marginTop: 'var(--e5)' }}>
              <Link to="/examen" className="boton">
                Escribir el código
              </Link>
            </p>
          </div>
        </div>
      </div>
    )
  }

  const empiezaEn = new Date(examen.starts_at).getTime() - ahora
  const modulos = Object.keys(examen.modules).filter((m) => MODULOS[m])

  return (
    <div className="centrado-estrecho">
      <h1>{examen.title}</h1>
      <p className="subtitulo">
        {fechaLarga(examen.starts_at)} · {examen.duration_minutes} minutos
      </p>

      <div className="tarjeta" style={{ marginTop: 'var(--e6)' }}>
        <div className="tarjeta-cuerpo">
          {examen.can_enter_now ? (
            <>
              <h2>Tu examen está abierto</h2>
              <p className="subtitulo">
                Ábrelo desde la aplicación de escritorio para empezar.
              </p>
            </>
          ) : empiezaEn > 0 ? (
            <>
              <h2>Todavía no empieza</h2>
              <p className="subtitulo">
                Empieza {cuandoEmpieza(empiezaEn)}. Puedes entrar hasta{' '}
                {examen.entry_tolerance_minutes} minutos después del inicio.
              </p>
            </>
          ) : (
            <>
              <h2>El plazo de ingreso terminó</h2>
              <p className="subtitulo">
                Habla con tu docente si crees que es un error. Él puede admitirte a mano.
              </p>
            </>
          )}

          {examen.description && (
            <>
              <h4 style={{ marginTop: 'var(--e6)' }}>Indicaciones del docente</h4>
              <p>{examen.description}</p>
            </>
          )}
        </div>
      </div>

      {modulos.length > 0 && (
        <div className="tarjeta">
          <div className="tarjeta-cuerpo">
            <h2>Qué se va a supervisar</h2>
            <p className="subtitulo">
              Durante el examen se registran estas señales. No se graba video continuo: solo se
              guardan los avisos puntuales y la evidencia asociada.
            </p>
            <ul className="lista-modulos">
              {modulos.map((modulo) => (
                <li key={modulo}>{MODULOS[modulo]}</li>
              ))}
            </ul>
            <p className="ayuda">
              El sistema no decide nada por su cuenta. Si aparece un aviso, lo revisa tu docente y
              es él quien resuelve, con una justificación escrita.
            </p>
          </div>
        </div>
      )}

      <p style={{ marginTop: 'var(--e5)' }}>
        <Link to="/examen" className="boton boton-secundario">
          Usar otro código
        </Link>
      </p>
    </div>
  )
}

function cuandoEmpieza(ms: number): string {
  const minutos = Math.ceil(ms / 60_000)
  if (minutos < 60) return `en ${minutos} minuto${minutos === 1 ? '' : 's'}`
  const horas = Math.floor(minutos / 60)
  if (horas < 24) return `en ${horas} hora${horas === 1 ? '' : 's'}`
  const dias = Math.floor(horas / 24)
  return `en ${dias} día${dias === 1 ? '' : 's'}`
}
