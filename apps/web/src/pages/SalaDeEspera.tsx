import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api, type JoinedExam, type Participant } from '../lib/api'
import { supabase } from '../lib/supabase'
import { useAuth } from '../lib/auth-context'
import { recordarExamen, recuperarExamen } from '../lib/examen-guardado'
import { cuandoEmpieza, fechaLarga } from '../lib/formato'
import { VerificacionFacialEspera } from './VerificacionFacialEspera'
import { PruebaMicrofono } from '../supervision/PruebaMicrofono'
import { CalibracionMirada } from '../components/CalibracionMirada'
import { ComprobacionEncuadre } from '../components/ComprobacionEncuadre'
import { nivelDe } from '../supervision/detectores/encuadre-core'
import type { EstadoEncuadreSala } from '../supervision/encuadreSala'
import { agrupar, dispositivosQueUsa, modulosVigilados } from '../lib/modulos'
import { sondear } from '../lib/sondeo'

/** Cada cuánto se vuelve a preguntar si el docente ya admitió al estudiante.
 *  Diez segundos de media, con un margen al azar (`sondear`): suficiente para
 *  que no se sienta colgado, y sin que los que entraron juntos pregunten juntos
 *  cada diez segundos (ADR-0011). */
const ESPERA_MS = 10_000

/**
 * Sala de espera y **consentimiento**.
 *
 * Es la pantalla donde el estudiante ve qué se va a observar y lo acepta antes
 * de empezar. La API no entrega ni una pregunta sin esa aceptación: aquí se
 * explica y allí se exige.
 */
export function SalaDeEspera() {
  const { id = '' } = useParams()
  const { token, userId } = useAuth()
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
  const [acabanDeAdmitirme, setAcabanDeAdmitirme] = useState(false)
  const [error, setError] = useState<string>()
  const [encuadre, setEncuadre] = useState<EstadoEncuadreSala | null>(null)
  const [ahora, setAhora] = useState(() => Date.now())

  useEffect(() => {
    if (examen) recordarExamen(examen)
  }, [examen])

  // Si ya consintió antes, no se le vuelve a preguntar: se le deja pasar.
  //
  // Y mientras su identidad no esté resuelta, esta pantalla **espera sola**. El
  // estudiante no tiene que recargar ni volver a intentarlo para enterarse de
  // que su docente ya lo admitió: antes tenía que hacerlo, y era lo peor de
  // estar esperando.
  //
  // Dos caminos a la vez, a propósito: Realtime avisa en el instante en que el
  // docente pulsa «Admitir», y la consulta periódica cubre el caso de que la
  // conexión en vivo no esté disponible (sin Supabase configurado, o con la red
  // del estudiante bloqueando websockets). Perder el aviso es peor que pedirlo
  // dos veces.
  useEffect(() => {
    if (!id) return
    let cancelado = false

    const consultar = (): void => {
      api
        .myEnrollment(id, token)
        .then((mia) => {
          if (cancelado) return
          setMatricula((previa) => {
            if (!previa?.can_take_exam && mia.can_take_exam && !mia.submitted_at) {
              setAcabanDeAdmitirme(true)
            }
            return mia
          })
        })
        // Un 400 aquí significa "todavía no has consentido", que es el estado
        // normal de esta pantalla y no un error que mostrar.
        .catch(() => undefined)
    }

    const parar = sondear(consultar, ESPERA_MS)

    const cliente = supabase
    const canal = cliente
      ?.channel(`mi-matricula-${id}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'session_participants',
          // Solo mi fila. Filtrando por examen, cada cambio de cualquier
          // participante se evaluaba contra las políticas de los sesenta
          // suscritos de ese examen: trabajo cuadrático en la base para
          // entregarle a cada uno solo lo suyo (ADR-0011).
          filter: userId ? `student_id=eq.${userId}` : `session_id=eq.${id}`
        },
        // Llega la fila cambiada, pero se vuelve a preguntar a la API: el
        // aviso solo dice «algo cambió»; qué me toca lo decide el token, no un
        // mensaje que llega por el canal (y sin `userId` el filtro es del
        // examen entero).
        () => consultar()
      )
      .subscribe()

    return () => {
      cancelado = true
      parar()
      if (cliente && canal) void cliente.removeChannel(canal)
    }
  }, [id, token, userId])

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
  // Lo que se vigila de verdad, no solo lo que enciende la web: en los niveles
  // ya armados la app de escritorio vigila además la ventana, los monitores y
  // los programas. Decírselo no es un trámite: es la base del consentimiento.
  const vigilados = modulosVigilados(examen)
  const grupos = agrupar(vigilados)
  const usa = dispositivosQueUsa(vigilados)
  const noUsa = [!usa.camara && 'tu cámara', !usa.microfono && 'tu micrófono'].filter(Boolean)
  const yaConsintio = matricula?.consent_at != null
  const yaEntrego = matricula?.submitted_at != null
  // Antes de la hora no se ofrece aceptar: pulsarlo daba un error, y encima uno
  // que decía lo contrario de lo que pasaba («el plazo está cerrado»).
  const todaviaNoEmpieza = empiezaEn > 0 && !examen.can_enter_now
  const requiereVerificacionFacial = 'face_verification' in examen.modules
  const requiereMicrofono = 'ai_voice' in examen.modules || 'external_voices' in examen.modules
  // Encuadre de hombros y brazos (Jesús): con mirada u objetos activos, la
  // cámara tiene que ver más que la cara antes de entrar.
  const nivelEncuadre = nivelDe((examen.modules.objects ?? examen.modules.gaze)?.framing_required)
  const requiereEncuadre =
    ('gaze' in examen.modules || 'objects' in examen.modules) && nivelEncuadre !== 'off'
  const encuadreListo = !requiereEncuadre || encuadre !== null

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

      {grupos.length > 0 && (
        <div className="tarjeta">
          <div className="tarjeta-cuerpo">
            <h2>Qué se va a supervisar</h2>
            <p className="subtitulo">
              Durante el examen se registran estas señales y nada más. No se graba video continuo:
              solo se guardan los avisos puntuales y la evidencia asociada.
            </p>
            <div className="sala-modulos">
              {grupos.map(({ grupo, modulos }) => (
                <section key={grupo.id} aria-labelledby={`sala-grupo-${grupo.id}`}>
                  <h3 id={`sala-grupo-${grupo.id}`}>{grupo.estudiante}</h3>
                  <ul className="lista-modulos">
                    {modulos.map((m) => (
                      <li key={m.id}>{m.paraEstudiante}</li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
            {noUsa.length > 0 && (
              <p className="sala-no-usa">Este examen no usa {noUsa.join(' ni ')}.</p>
            )}
            <p className="ayuda">
              El sistema no decide nada por su cuenta. Si aparece un aviso, lo revisa tu docente y
              es él quien resuelve, con una justificación escrita.
            </p>
          </div>
        </div>
      )}

      {acabanDeAdmitirme && !yaEntrego && (
        <p className="aviso aviso-exito" role="status">
          <strong>Tu docente te admitió.</strong> Ya puedes entrar al examen.
        </p>
      )}

      {matricula && !matricula.can_take_exam && !yaEntrego && (
        <p className="aviso aviso-neutro" role="status">
          Tu identidad todavía no está verificada. Tu docente te admitirá desde su panel y esta
          pantalla te avisará sola: no hace falta que recargues ni que vuelvas a intentarlo.
        </p>
      )}

      {yaConsintio &&
        matricula &&
        !matricula.can_take_exam &&
        !yaEntrego &&
        requiereVerificacionFacial && (
          <VerificacionFacialEspera
            sessionId={id}
            studentId={matricula.student_id}
            token={token}
            verificationStatus={matricula.verification_status}
            onCheckRequested={setMatricula}
          />
        )}

      {error && <p className="aviso">{error}</p>}

      {/* Calibrar antes de entrar: sin esto el umbral de «mirada fuera de
          pantalla» es el mismo para un portátil de 13 pulgadas que para dos
          monitores, que es de donde salen los falsos positivos. */}
      {matricula?.can_take_exam && !yaEntrego && 'gaze' in examen.modules && (
        <CalibracionMirada
          sessionId={id}
          studentId={matricula.student_id}
          defaultDeg={Number(examen.modules.gaze?.yaw_degrees) || 25}
        />
      )}

      {yaConsintio && !yaEntrego && requiereMicrofono && <PruebaMicrofono />}

      {yaConsintio && matricula?.can_take_exam && !yaEntrego && requiereEncuadre && (
        <ComprobacionEncuadre
          sessionId={id}
          studentId={matricula.student_id}
          nivel={nivelEncuadre}
          onEstado={setEncuadre}
        />
      )}

      {!yaEntrego && (
        <div className="tarjeta">
          <div className="tarjeta-cuerpo">
            {todaviaNoEmpieza ? (
              <>
                <h2>Todavía no es la hora</h2>
                <p className="subtitulo">
                  Este examen empieza {cuandoEmpieza(empiezaEn)}. Puedes dejar esta pantalla
                  abierta: se actualizará sola cuando puedas entrar.
                </p>
              </>
            ) : yaConsintio ? (
              matricula?.can_take_exam ? (
                <>
                  {requiereMicrofono && (
                    <p className="ayuda">
                      La comprobación del micrófono no bloquea el ingreso al examen.
                    </p>
                  )}
                  {encuadreListo ? (
                    <Link to={`/examen/${id}/rendir`} className="boton">
                      Entrar al examen
                    </Link>
                  ) : (
                    <button type="button" className="boton" disabled>
                      Comprueba el encuadre de la cámara para entrar
                    </button>
                  )}
                </>
              ) : (
                <button type="button" className="boton" disabled>
                  Esperando verificación o admisión del docente
                </button>
              )
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
                  {entrando ? 'Guardando consentimiento…' : 'Aceptar y continuar'}
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
