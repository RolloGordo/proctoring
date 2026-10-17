import { useEffect, useRef, useState } from 'react'
import { supabase } from '../lib/supabase'
import { verFotogramas, type EstadoCamara, type EstadoVista, type EstadoVision, type Fotograma } from '../supervision/monitoreo'

/** Si no llega un fotograma en este tiempo, se dice «sin señal». */
const SIN_SENAL_MS = 5000

/**
 * La cámara de **un** estudiante, en vivo.
 *
 * Es la pieza que se repite en la cuadrícula del docente (HU-015): se monta una
 * por estudiante y cada una abre su propio canal. Montarla es lo que hace que
 * ese estudiante empiece a enviar, y desmontarla, lo que hace que deje de
 * enviar. De ahí que la cuadrícula no deba montar las que no se están viendo.
 *
 * No hay `<video>` ni grabación: llegan JPEG sueltos y se pintan en un `<img>`.
 * Nada se guarda, ni aquí ni en el servidor.
 */
export function CamaraEnVivo({
  sessionId,
  studentId,
  teacherId,
  nombre
}: {
  sessionId: string
  studentId: string
  /** Quién mira. Sin esto no se puede descontar su propia presencia. */
  teacherId: string
  /** Lo que se muestra debajo. Si no se pasa, el id abreviado. */
  nombre?: string
}) {
  const [ultimo, setUltimo] = useState<Fotograma>()
  const [conectado, setConectado] = useState(false)
  const [estado, setEstado] = useState<EstadoVista>('conectando')
  const [fresco, setFresco] = useState(false)
  const [camaraEstado, setCamaraEstado] = useState<EstadoCamara | null>(null)
  const [visionEstado, setVisionEstado] = useState<EstadoVision | null>(null)
  const [modulosFallidos, setModulosFallidos] = useState<string[]>([])
  const [receivedFps, setReceivedFps] = useState(0)
  const lastFrameAt = useRef<number | null>(null)

  useEffect(() => {
    if (!supabase || !sessionId || !studentId || !teacherId) return

    const vista = verFotogramas({
      cliente: supabase,
      sessionId,
      studentId,
      teacherId,
      // Que llegó algo lo decide este equipo, no el reloj del estudiante: su
      // `capturadoEn` viene en el mensaje y queda ahí para diagnóstico, pero
      // un reloj desfasado no puede hacer que una imagen de ahora mismo
      // aparezca como «sin señal».
      onFotograma: (fotograma) => {
        setUltimo(fotograma)
        setFresco(true)
        const now = performance.now()
        if (lastFrameAt.current !== null) {
          const delta = now - lastFrameAt.current
          if (delta > 0) setReceivedFps(Math.round((1000 / delta) * 10) / 10)
        }
        lastFrameAt.current = now
      },
      onConectado: (value) => {
        setConectado(value)
        if (!value) setCamaraEstado(null)
      },
      onCamaraEstado: setCamaraEstado,
      onVisionEstado: (status, modules) => { setVisionEstado(status); setModulosFallidos(modules) },
      onEstado: setEstado
    })

    return () => {
      void vista.detener()
      setConectado(false)
      lastFrameAt.current = null
    }
  }, [sessionId, studentId, teacherId])

  // «Hace rato que no llega nada» no se puede deducir en el repintado, porque
  // cuando dejan de llegar fotogramas no hay repintado. Cada fotograma arma de
  // nuevo este plazo, y si no llega el siguiente, el plazo vence.
  useEffect(() => {
    if (!ultimo) return
    const plazo = setTimeout(() => setFresco(false), SIN_SENAL_MS)
    return () => clearTimeout(plazo)
  }, [ultimo])

  const etiqueta = nombre ?? studentId.slice(0, 8)

  if (!supabase) {
    return (
      <figure className="camara-vivo">
        <div className="camara-vivo-marco camara-vivo-vacia">
          <p className="ayuda">Supabase no está configurado: no hay monitoreo en vivo.</p>
        </div>
      </figure>
    )
  }

  const estadoSenal = !conectado
    ? 'Desconectado'
    : camaraEstado === 'interrupted'
      ? 'Cámara desconectada'
      : camaraEstado === 'no_image'
        ? 'Imagen no disponible'
        : fresco
      ? 'En vivo'
      : ultimo
        ? 'Sin señal'
        : 'Sin cámara'

  return (
    <figure className="camara-vivo">
      <div className="camara-vivo-marco">
        {ultimo ? (
          <img
            src={`data:image/jpeg;base64,${ultimo.jpeg}`}
            alt={`Cámara de ${etiqueta}`}
            className={fresco && (camaraEstado === null || camaraEstado === 'active') ? undefined : 'camara-vivo-congelada'}
          />
        ) : (
          <div className="camara-vivo-vacia">
            <p className="ayuda">
              {estado === 'error'
                ? 'No se pudo abrir el canal.'
                : conectado
                  ? 'Conectado, esperando imagen…'
                  : 'El estudiante no está rindiendo.'}
            </p>
          </div>
        )}
      </div>

      <figcaption className="camara-vivo-pie">
        <span>{etiqueta}</span>
        <span className="en-vivo" role="status" aria-live="polite">
          <span className={estadoSenal === 'En vivo' ? 'punto punto-activo' : 'punto'} />
          {estadoSenal}{fresco && receivedFps > 0 ? ` · ${receivedFps} FPS recibidos` : ''}
        </span>
        {visionEstado && visionEstado !== 'active' && (
          <span role="alert" className="aviso">
            Visión {visionEstado === 'unavailable' ? 'no disponible' : 'parcial'}
            {modulosFallidos.length > 0 ? `: ${modulosFallidos.join(', ')}` : ''}
          </span>
        )}
      </figcaption>
    </figure>
  )
}
