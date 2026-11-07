import { useCallback, useEffect, useRef, useState } from 'react'
import { abrirCamara } from '../supervision/camara'
import {
  EstabilidadEncuadre,
  MENSAJES,
  type NivelEncuadre,
  type ResultadoEncuadre
} from '../supervision/detectores/encuadre-core'
import { guardarEncuadre, leerEncuadre, type EstadoEncuadreSala } from '../supervision/encuadreSala'

/** Cada cuánto se mide mientras el estudiante acomoda la cámara. */
const INTERVALO_MS = 400

const QUE_SE_VE: Record<Exclude<NivelEncuadre, 'off'>, string> = {
  shoulders: 'tu cara y tus dos hombros',
  elbows: 'tu cara, tus hombros y tus brazos hasta los codos',
  hands: 'tu cara, tus hombros, tus brazos y tus manos'
}

/**
 * Comprobación obligatoria del encuadre antes de entrar (Jesús Limay).
 *
 * Con la cámara enfocando solo la cara, un celular sostenido más abajo no
 * entra nunca en la imagen y ningún detector puede verlo. Aquí no se deja
 * entrar hasta que se vean hombros y brazos durante 2 s seguidos. No se graba
 * ni se envía ninguna imagen: todo corre en este equipo.
 *
 * Si el modelo no carga, NO bloquea: un modelo que falla no puede dejar a un
 * estudiante sin rendir (mismo criterio que `useSupervision`). Se avisa y el
 * detector del examen sigue intentándolo.
 */
export function ComprobacionEncuadre({
  sessionId,
  studentId,
  nivel,
  onEstado
}: {
  sessionId: string
  studentId: string
  nivel: Exclude<NivelEncuadre, 'off'>
  onEstado: (estado: EstadoEncuadreSala | null) => void
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const camaraRef = useRef<Awaited<ReturnType<typeof abrirCamara>> | null>(null)
  const [estado, setEstado] = useState<EstadoEncuadreSala | null>(() =>
    leerEncuadre(sessionId, studentId)
  )
  const [midiendo, setMidiendo] = useState(false)
  const [abriendo, setAbriendo] = useState(false)
  const [ultimo, setUltimo] = useState<ResultadoEncuadre | null>(null)
  const [progreso, setProgreso] = useState(0)
  const [error, setError] = useState<string>()

  useEffect(() => {
    onEstado(estado)
  }, [estado, onEstado])

  useEffect(() => () => camaraRef.current?.cerrar(), [])

  const terminar = useCallback(
    (resultado: EstadoEncuadreSala) => {
      guardarEncuadre(sessionId, studentId, resultado)
      camaraRef.current?.cerrar()
      camaraRef.current = null
      setMidiendo(false)
      setEstado(resultado)
    },
    [sessionId, studentId]
  )

  useEffect(() => {
    if (!midiendo) return
    let cancelado = false
    // La primera medición carga el modelo y tarda; sin esto se apilan.
    let ocupado = false
    const estable = new EstabilidadEncuadre()
    const reloj = setInterval(() => {
      const video = videoRef.current
      if (!video || ocupado) return
      ocupado = true
      void (async () => {
        try {
          const { medirEncuadre } = await import('../supervision/detectores/encuadre')
          const r = await medirEncuadre(video, nivel)
          if (cancelado || !r) return
          const ahora = Date.now()
          setUltimo(r)
          const listo = estable.registrar(r.ok, ahora)
          setProgreso(estable.progreso(ahora))
          if (listo) {
            cancelado = true
            terminar('passed')
          }
        } catch (fallo) {
          if (cancelado) return
          cancelado = true
          console.error('[encuadre]', fallo)
          setError(
            'No se pudo comprobar el encuadre en este equipo. Puedes entrar igual: durante el examen se seguirá intentando, y tu docente lo verá.'
          )
          terminar('unavailable')
        } finally {
          ocupado = false
        }
      })()
    }, INTERVALO_MS)
    return () => {
      cancelado = true
      clearInterval(reloj)
    }
  }, [midiendo, nivel, terminar])

  async function empezar() {
    setError(undefined)
    setAbriendo(true)
    try {
      camaraRef.current?.cerrar()
      const camara = await abrirCamara()
      camaraRef.current = camara
      if (videoRef.current) {
        videoRef.current.srcObject = camara.video.srcObject
        await videoRef.current.play()
      }
      setUltimo(null)
      setProgreso(0)
      setMidiendo(true)
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo abrir la cámara.')
    } finally {
      setAbriendo(false)
    }
  }

  const mensaje = ultimo?.mensaje ?? 'Acomódate frente a la cámara…'

  return (
    <section
      className="tarjeta"
      style={{ marginTop: 'var(--e4)' }}
      aria-label="Comprobación del encuadre de la cámara"
    >
      <div className="tarjeta-cuerpo">
        <h3>Encuadre de la cámara</h3>
        <p className="ayuda">
          Para entrar, la cámara tiene que mostrar {QUE_SE_VE[nivel]}, no solo tu rostro. Así la
          supervisión ve lo que tienes en las manos. Nada se graba ni se envía: se mide en tu
          equipo.
        </p>

        {estado === 'passed' ? (
          <p role="status" className="aviso aviso-exito">
            {MENSAJES.ok} Mantén la cámara así durante todo el examen.
          </p>
        ) : estado === 'unavailable' ? (
          <p role="status" className="aviso">
            No se pudo comprobar el encuadre en este equipo. Puedes entrar; mantén visibles tus
            hombros y brazos.
          </p>
        ) : (
          <>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              style={{
                display: midiendo ? 'block' : 'none',
                width: 320,
                maxWidth: '100%',
                borderRadius: 8,
                transform: 'scaleX(-1)'
              }}
              aria-label="Vista previa de la cámara"
            />
            {midiendo ? (
              <>
                <p role="status" aria-live="polite" style={{ marginTop: 'var(--e3)' }}>
                  <strong>{ultimo?.ok ? 'Bien, no te muevas…' : mensaje}</strong>
                </p>
                <progress
                  max={1}
                  value={progreso}
                  aria-label="Encuadre sostenido"
                  style={{ width: 320, maxWidth: '100%' }}
                />
              </>
            ) : (
              <button
                type="button"
                className="boton boton-secundario"
                disabled={abriendo}
                onClick={() => void empezar()}
              >
                {abriendo ? 'Abriendo cámara…' : 'Comprobar encuadre'}
              </button>
            )}
          </>
        )}
        {error && (
          <p className="aviso" role="alert">
            {error}
          </p>
        )}
      </div>
    </section>
  )
}
