import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api, type JoinedExam, type Participant } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { recordarExamen, recuperarExamen } from '../lib/examen-guardado'
import { fechaLarga } from '../lib/formato'

/** Nombre legible de cada módulo de supervisión, para que el estudiante sepa
 *  qué se va a observar. Decírselo no es un trámite: es la base del
 *  consentimiento, y el sistema vigila, no espía. */
/** Cada cuánto se vuelve a preguntar si el docente ya admitió al estudiante.
 *  Diez segundos: suficiente para que no se sienta colgado, y poco tráfico
 *  aunque haya treinta personas esperando a la vez. */
const ESPERA_MS = 10_000

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

/**
 * Sala de espera y **consentimiento**.
 *
 * Es la pantalla donde el estudiante ve qué se va a observar y lo acepta antes
 * de empezar. La API no entrega ni una pregunta sin esa aceptación: aquí se
 * explica y allí se exige.
 */
export function SalaDeEspera() {
  const { id = '' } = useParams()
  const { token } = useAuth()
  const navegar = useNavigate()

  // Viene de la pantalla del código. Si el estudiante recarga, el estado de
  // navegación se pierde, así que también se guarda por sesión del navegador.
  const { state } = useLocation()
  const [examen] = useState<JoinedExam | null>(
    () => (state as JoinedExam | null) ?? recuperarExamen(id)
  )
  const [matricula, setMatricula] = useState<Participant>()
  const [acepta, setAcepta] = useState(false)
  const [entrando, setEntrando] = useState(false)
  const [error, setError] = useState<string>()
  const [ahora, setAhora] = useState(() => Date.now())

  useEffect(() => {
    if (examen) recordarExamen(examen)
  }, [examen])

  // Si ya consintió antes, no se le vuelve a preguntar: se le deja pasar.
  //
  // Y mientras su identidad no esté resuelta, se vuelve a preguntar cada pocos
  // segundos: el estudiante está esperando a que su docente lo admita y no
  // tiene por qué recargar la página para enterarse.
  useEffect(() => {
    if (!id) return
    let cancelado = false

    const consultar = (): void => {
      api
        .myEnrollment(id, token)
        .then((mia) => {
          if (cancelado) return
          setMatricula(mia)
          if (mia.can_take_exam && !mia.submitted_at) clearInterval(temporizador)
        })
        // Un 400 aquí significa "todavía no has consentido", que es el estado
        // normal de esta pantalla y no un error que mostrar.
        .catch(() => undefined)
    }

    consultar()
    const temporizador = setInterval(consultar, ESPERA_MS)

    return () => {
      cancelado = true
      clearInterval(temporizador)
    }
  }, [id, token])

  // Un reloj por minuto basta: la cuenta atrás se mide en minutos, no en
  // segundos, y refrescar cada segundo solo gasta batería.
  useEffect(() => {
    const temporizador = setInterval(() => setAhora(Date.now()), 60_000)
    return () => clearInterval(temporizador)
  }, [])

  async function entrar(): Promise<void> {
    setError(undefined)
    setEntrando(true)
    try {
      const mia = await api.enroll(id, true, token)
      setMatricula(mia)
      if (mia.can_take_exam) navegar(`/examen/${id}/rendir`)
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo entrar al examen')
    } finally {
      setEntrando(false)
    }
  }

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
  const yaConsintio = matricula?.consent_at != null
  const yaEntrego = matricula?.submitted_at != null

  return (
    <div className="centrado-estrecho">
      <h1>{examen.title}</h1>
      <p className="subtitulo">
        {fechaLarga(examen.starts_at)} · {examen.duration_minutes} minutos
      </p>

      <div className="tarjeta" style={{ marginTop: 'var(--e6)' }}>
        <div className="tarjeta-cuerpo">
          {yaEntrego ? (
            <>
              <h2>Ya entregaste este examen</h2>
              <p className="subtitulo">No se puede volver a entrar.</p>
            </>
          ) : examen.can_enter_now ? (
            <>
              <h2>Tu examen está abierto</h2>
              <p className="subtitulo">
                {yaConsintio
                  ? 'Ya aceptaste la supervisión. Puedes continuar.'
                  : 'Revisa qué se va a supervisar y acepta para empezar.'}
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

      {matricula && !matricula.can_take_exam && !yaEntrego && (
        <p className="aviso aviso-neutro">
          Tu identidad todavía no está verificada. Tu docente te admitirá desde su panel y esta
          pantalla se actualizará sola: no hace falta que recargues.
        </p>
      )}

      {error && <p className="aviso">{error}</p>}

      {!yaEntrego && (
        <div className="tarjeta">
          <div className="tarjeta-cuerpo">
            {yaConsintio ? (
              <Link
                to={`/examen/${id}/rendir`}
                className="boton"
                aria-disabled={!matricula?.can_take_exam}
              >
                Entrar al examen
              </Link>
            ) : (
              <>
                <label className="casilla">
                  <input
                    type="checkbox"
                    checked={acepta}
                    onChange={(e) => setAcepta(e.target.checked)}
                  />
                  <span>
                    Acepto ser supervisado durante este examen con las señales de arriba, y que la
                    evidencia quede registrada para que mi docente la revise.
                  </span>
                </label>
                <button
                  type="button"
                  className="boton"
                  onClick={() => void entrar()}
                  disabled={!acepta || entrando}
                  style={{ marginTop: 'var(--e4)' }}
                >
                  {entrando ? 'Entrando…' : 'Aceptar y entrar al examen'}
                </button>
              </>
            )}
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
