import { useEffect, useRef, useState } from 'react'
import {
  abrirMicrofono,
  CamaraNoDisponibleError,
  microfonosDisponibles,
  type Microfono
} from './camara'
import { DetectorHabla } from './detectores/voz'
import { conLimite, LIMITE_ARRANQUE_MS } from './arranque'

type Estado = 'pendiente' | 'preparando' | 'escuchando' | 'detectado' | 'fallo'

interface Recursos {
  cerrarMicro: () => void
  detector?: DetectorHabla
  contexto: AudioContext
  animacion: number
}

/** Fotogramas seguidos por encima del umbral antes de dar por buena la señal. */
const FOTOGRAMAS_CON_SONIDO = 12
/** Por debajo de esto es ruido de fondo, no alguien hablando al micrófono. */
const UMBRAL_NIVEL = 18

/**
 * Comprueba el micrófono después del consentimiento, antes de abrir el examen.
 *
 * Pide **solo** el micrófono: encender la cámara para una prueba de audio haría
 * que se prendiera su luz sin motivo, y convertiría una cámara ocupada por otra
 * aplicación en un falso fallo de micrófono.
 *
 * Hay dos comprobaciones y **no dicen lo mismo**, así que la pantalla tampoco:
 *
 * - El **medidor de nivel** demuestra que llega sonido. Nada más. Un ventilador
 *   o un golpe en la mesa lo mueven, así que no se anuncia como «voz detectada».
 * - El **VAD (Silero)** es el que distingue voz, y es el que correrá durante el
 *   examen. Si no arranca aquí, tampoco va a arrancar allí, así que su fallo se
 *   le dice al estudiante en vez de quedarse en la consola: avisar ahora es
 *   justo para lo que existe esta pantalla.
 *
 * El fragmento de prueba nunca se sube.
 */
export function PruebaMicrofono() {
  const [estado, setEstado] = useState<Estado>('pendiente')
  const [nivel, setNivel] = useState(0)
  const [mensaje, setMensaje] = useState<string>()
  const [vadCaido, setVadCaido] = useState(false)
  const [microfonos, setMicrofonos] = useState<Microfono[]>([])
  const [elegido, setElegido] = useState('')
  const recursos = useRef<Recursos | undefined>(undefined)

  function detener(): void {
    const actual = recursos.current
    if (!actual) return
    cancelAnimationFrame(actual.animacion)
    actual.detector?.detener()
    void actual.contexto.close()
    actual.cerrarMicro()
    recursos.current = undefined
  }

  useEffect(() => detener, [])

  async function comprobar(): Promise<void> {
    detener()
    setNivel(0)
    setMensaje(undefined)
    setVadCaido(false)
    setEstado('preparando')

    try {
      const micro = await abrirMicrofono(elegido || undefined)
      // Despues de abrirlo, no antes: hasta que se concede el permiso los
      // nombres llegan vacios y la lista no sirve para elegir nada.
      void microfonosDisponibles().then(setMicrofonos)
      const contexto = new AudioContext()
      // Sin un gesto previo el contexto nace suspendido y el medidor se queda
      // plano, que parece un micrófono roto cuando no lo esta.
      if (contexto.state === 'suspended') await contexto.resume()

      const analizador = contexto.createAnalyser()
      analizador.fftSize = 512
      contexto.createMediaStreamSource(micro.stream).connect(analizador)
      const muestras = new Uint8Array(analizador.fftSize)
      let fotogramasConSonido = 0

      const actualizarNivel = (): void => {
        // Corre en el siguiente fotograma: si entre medias se desmonto la
        // pantalla o se reinicio la prueba, ya no hay nada que actualizar.
        if (!recursos.current) return
        analizador.getByteTimeDomainData(muestras)
        let energia = 0
        for (const muestra of muestras) {
          const amplitud = (muestra - 128) / 128
          energia += amplitud * amplitud
        }
        // Una barra legible, no una medicion cientifica.
        const calculado = Math.min(100, Math.round(Math.sqrt(energia / muestras.length) * 420))
        setNivel(calculado)

        if (calculado > UMBRAL_NIVEL) {
          fotogramasConSonido += 1
          if (fotogramasConSonido > FOTOGRAMAS_CON_SONIDO) {
            setEstado((previo) => (previo === 'detectado' ? previo : 'escuchando'))
            setMensaje((previo) =>
              previo?.startsWith('Voz')
                ? previo
                : 'Se está captando sonido. Di la frase para confirmar que se reconoce tu voz.'
            )
          }
        } else {
          fotogramasConSonido = Math.max(0, fotogramasConSonido - 1)
        }

        recursos.current.animacion = requestAnimationFrame(actualizarNivel)
      }

      recursos.current = {
        cerrarMicro: micro.cerrar,
        contexto,
        animacion: requestAnimationFrame(actualizarNivel)
      }
      setEstado('escuchando')
      setMensaje('Di: «Estoy listo para rendir el examen».')

      // El VAD se prepara aparte para que la barra de nivel no se congele
      // mientras carga el modelo.
      try {
        const detector = new DetectorHabla()
        // **Con límite de tiempo.** `MicVAD.new()` no resuelve ni rechaza si la
        // carga del worker de ONNX se atasca, y entonces esto no marcaba el
        // detector como listo *ni* entraba en el `catch`: la pantalla se
        // quedaba en «escuchando» para siempre, sin confirmar y sin avisar de
        // que había fallado. Quien lo probaba veía que se capta sonido y que
        // nunca se confirma, sin ninguna explicación.
        await conLimite(
          detector.preparar({
            stream: micro.stream,
            captureSender: () => (senal) => {
              if (senal.evento === 'speech_detected') {
                setEstado('detectado')
                setMensaje('Voz reconocida. El micrófono está listo para el examen.')
              }
            }
          }),
          LIMITE_ARRANQUE_MS
        )
        if (recursos.current) recursos.current.detector = detector
        else detector.detener()
      } catch (fallo) {
        // No se traga en silencio: este es el mismo detector que corre durante
        // el examen, asi que un fallo aqui significa que la deteccion de habla
        // no va a funcionar mientras se rinde.
        console.warn('[prueba-microfono] el VAD no arranco:', fallo)
        setVadCaido(true)
      }
    } catch (fallo) {
      detener()
      setEstado('fallo')
      setMensaje(
        fallo instanceof CamaraNoDisponibleError
          ? fallo.message
          : 'No se pudo activar el micrófono. Revisa los permisos en la barra de direcciones y vuelve a intentarlo.'
      )
    }
  }

  const listo = estado === 'detectado'

  return (
    <section className="tarjeta" aria-labelledby="titulo-prueba-microfono">
      <div className="tarjeta-cuerpo">
        <h2 id="titulo-prueba-microfono">Comprueba tu micrófono</h2>
        <p className="subtitulo">
          Antes de rendir, confirma que tu voz llega al sistema. Esta prueba no guarda ni envía el
          audio.
        </p>

        {/*
          Se ensena en cuanto hay un microfono, no solo si hay varios. Con el
          umbral en «mas de uno» no aparecia en el equipo donde hacia falta:
          quien tiene una camara virtual no siempre acaba con dos entradas
          enumeradas, y sin la lista no hay forma de saber cual se esta usando
          ni de probar con otra.
        */}
        {/*
          Se ensena en cuanto la prueba ha arrancado, aunque la lista venga
          vacia. **Un control que desaparece cuando no hay nada que elegir es
          indistinguible de uno que no se desplego**: se pidio este selector dos
          veces y las dos parecia que no estaba hecho, cuando lo que pasaba era
          que el equipo no enumeraba ninguna entrada.
        */}
        {estado !== 'pendiente' && estado !== 'preparando' && (
          <p>
            <label htmlFor="elegir-microfono">Micrófono</label>
            <select
              id="elegir-microfono"
              value={elegido}
              onChange={(evento) => {
                setElegido(evento.target.value)
                void comprobar()
              }}
              style={{ width: '100%' }}
            >
              <option value="">El que elija el sistema</option>
              {microfonos.map((micro, posicion) => (
                <option key={micro.deviceId} value={micro.deviceId}>
                  {micro.etiqueta || `Micrófono ${posicion + 1}`}
                </option>
              ))}
            </select>
            <span className="ayuda">
              {microfonos.length === 0
                ? 'Tu equipo no dio la lista de micrófonos, así que se usa el que elija el sistema. No impide rendir.'
                : `${microfonos.length} ${microfonos.length === 1 ? 'entrada detectada' : 'entradas detectadas'}. Si tienes una cámara virtual instalada (ManyCam, OBS), suele añadir su propio micrófono: elige el real si la prueba no confirma.`}
            </span>
          </p>
        )}

        {(estado === 'escuchando' || listo) && (
          <>
            <label htmlFor="nivel-microfono">Nivel de entrada</label>
            <progress id="nivel-microfono" value={nivel} max="100" style={{ width: '100%' }}>
              {nivel}%
            </progress>
          </>
        )}

        {mensaje && (
          <p
            className={
              listo ? 'aviso aviso-exito' : estado === 'fallo' ? 'aviso' : 'aviso aviso-neutro'
            }
          >
            {mensaje}
          </p>
        )}

        {vadCaido && (
          <p className="aviso aviso-neutro">
            Se capta sonido, pero el reconocimiento de voz no pudo cargarse en este equipo. Puedes
            rendir igual: quedará registrado que esta comprobación no se completó, y el docente lo
            verá.
          </p>
        )}

        <button
          type="button"
          className="boton boton-secundario"
          onClick={() => void comprobar()}
          disabled={estado === 'preparando'}
          style={{ marginTop: 'var(--e3)' }}
        >
          {estado === 'preparando'
            ? 'Solicitando permiso…'
            : estado === 'escuchando'
              ? 'Reiniciar prueba'
              : listo
                ? 'Probar otra vez'
                : 'Activar y probar micrófono'}
        </button>
        <p className="ayuda" style={{ marginTop: 'var(--e3)' }}>
          Si no puedes activarlo, puedes continuar. El docente verá que la comprobación no se pudo
          realizar y decidirá cómo proceder.
        </p>
      </div>
    </section>
  )
}
