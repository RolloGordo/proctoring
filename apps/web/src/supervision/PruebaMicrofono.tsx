import { useEffect, useRef, useState } from 'react'
import { abrirCamara, CamaraNoDisponibleError } from './camara'
import { DetectorHabla } from './detectores/voz'

type Estado = 'pendiente' | 'preparando' | 'escuchando' | 'detectado' | 'fallo'

interface Recursos {
  cerrarCamara: () => void
  detector: DetectorHabla
  contexto: AudioContext
  animacion: number
}

/**
 * Comprueba el micrófono después del consentimiento, antes de abrir el examen.
 *
 * Comparte la misma apertura de dispositivos y el mismo Silero VAD que se usa
 * al rendir. El fragmento de prueba nunca se sube: el callback del detector solo
 * confirma que el VAD oyó la frase solicitada.
 */
export function PruebaMicrofono() {
  const [estado, setEstado] = useState<Estado>('pendiente')
  const [nivel, setNivel] = useState(0)
  const [mensaje, setMensaje] = useState<string>()
  const recursos = useRef<Recursos | undefined>(undefined)

  function detener(): void {
    const actual = recursos.current
    if (!actual) return
    cancelAnimationFrame(actual.animacion)
    actual.detector.detener()
    void actual.contexto.close()
    actual.cerrarCamara()
    recursos.current = undefined
  }

  useEffect(() => detener, [])

  async function comprobar(): Promise<void> {
    detener()
    setNivel(0)
    setMensaje(undefined)
    setEstado('preparando')
    try {
      // Reutiliza la apertura común: mantiene permisos y errores coherentes con
      // la supervisión que se ejecutará durante el examen.
      const camara = await abrirCamara({ audio: true })
      const stream = camara.video.srcObject as MediaStream
      const contexto = new AudioContext()
      const analizador = contexto.createAnalyser()
      analizador.fftSize = 512
      const fuente = contexto.createMediaStreamSource(new MediaStream(stream.getAudioTracks()))
      fuente.connect(analizador)
      const muestras = new Uint8Array(analizador.fftSize)

      const detector = new DetectorHabla()
      await detector.preparar({
        stream,
        captureSender: () => (senal) => {
          if (senal.evento === 'speech_detected') {
            setEstado('detectado')
            setMensaje('Voz detectada. El micrófono está listo para el examen.')
          }
        }
      })

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
        // Una barra legible, no una medición científica: muestra que llega voz.
        setNivel(Math.min(100, Math.round(Math.sqrt(energia / muestras.length) * 420)))
        recursos.current.animacion = requestAnimationFrame(actualizarNivel)
      }
      recursos.current = {
        cerrarCamara: camara.cerrar,
        detector,
        contexto,
        animacion: requestAnimationFrame(actualizarNivel)
      }
      setEstado('escuchando')
      setMensaje('Di: “Estoy listo para rendir el examen”.')
    } catch (fallo) {
      detener()
      setEstado('fallo')
      setMensaje(
        fallo instanceof CamaraNoDisponibleError
          ? fallo.message
          : 'No se pudo comprobar el micrófono. Comprueba tu dispositivo y vuelve a intentarlo.'
      )
    }
  }

  const listo = estado === 'detectado'

  return (
    <section className="tarjeta" aria-labelledby="titulo-prueba-microfono">
      <div className="tarjeta-cuerpo">
        <h2 id="titulo-prueba-microfono">Comprueba tu micrófono</h2>
        <p className="subtitulo">
          Antes de rendir, confirma que tu voz llega al sistema. Esta prueba no guarda ni envía
          el audio.
        </p>

        {(estado === 'escuchando' || listo) && (
          <>
            <label htmlFor="nivel-microfono">Nivel de entrada</label>
            <progress id="nivel-microfono" value={nivel} max="100" style={{ width: '100%' }}>
              {nivel}%
            </progress>
          </>
        )}

        {mensaje && (
          <p className={listo ? 'aviso aviso-exito' : estado === 'fallo' ? 'aviso' : 'aviso aviso-neutro'}>
            {mensaje}
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
