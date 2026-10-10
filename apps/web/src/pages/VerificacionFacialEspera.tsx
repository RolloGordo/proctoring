import { useEffect, useRef, useState } from 'react'
import type { Participant, VerificationStatus } from '../lib/api'
import { api } from '../lib/api'
import { subirFotoDeIdentidad } from '../lib/identidad'
import { abrirCamara, capturarFotograma } from '../supervision/camara'

interface Props {
  sessionId: string
  studentId: string
  token?: string
  verificationStatus: VerificationStatus
  onCheckRequested: (participant: Participant) => void
}

type CamaraActiva = Awaited<ReturnType<typeof abrirCamara>>

/**
 * HU-006. Capturas PUNTUALES de identidad, nunca grabación de vídeo.
 * El estudiante controla cuándo registra su referencia y cuándo verifica.
 * El docente conserva en todos los casos la opción de admisión manual.
 */
export function VerificacionFacialEspera({
  sessionId,
  studentId,
  token,
  verificationStatus,
  onCheckRequested
}: Props) {
  const contenedor = useRef<HTMLDivElement>(null)
  const camara = useRef<CamaraActiva | null>(null)
  const montado = useRef(false)
  const [camaraAbierta, setCamaraAbierta] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [referenciaRegistrada, setReferenciaRegistrada] = useState(false)
  const [solicitudEnviada, setSolicitudEnviada] = useState(false)
  const [mensaje, setMensaje] = useState<string>()
  const [error, setError] = useState<string>()

  function cerrar(): void {
    camara.current?.cerrar()
    camara.current = null
    contenedor.current?.replaceChildren()
    setCamaraAbierta(false)
  }

  // También cierra las pistas cuando se cambia de pantalla o de sesión.
  useEffect(() => {
    montado.current = true
    return () => {
      montado.current = false
      camara.current?.cerrar()
      camara.current = null
    }
  }, [])

  // Después de un resultado fallido se permite reintentar, sin borrar el
  // estado con un efecto ni confundir un trabajo 202 con una coincidencia.
  const permitirNuevaSolicitud = !solicitudEnviada || verificationStatus === 'failed'

  async function iniciarCamara(): Promise<void> {
    if (ocupado || camara.current) return
    setError(undefined)
    setMensaje(undefined)
    setOcupado(true)
    try {
      // Se reutiliza el tratamiento de permisos y errores ya implementado.
      const nueva = await abrirCamara({ ancho: 1280, alto: 720 })
      if (!montado.current) {
        nueva.cerrar()
        return
      }
      camara.current = nueva
      nueva.video.style.width = '100%'
      nueva.video.style.maxWidth = '560px'
      nueva.video.style.borderRadius = 'var(--r, 12px)'
      nueva.video.setAttribute('aria-label', 'Vista previa de cámara para verificar identidad')
      contenedor.current?.replaceChildren(nueva.video)
      setCamaraAbierta(true)
    } catch (fallo) {
      if (montado.current) {
        setError(fallo instanceof Error ? fallo.message : 'No se pudo abrir la cámara.')
      }
    } finally {
      if (montado.current) setOcupado(false)
    }
  }

  async function fotografiar(): Promise<Blob> {
    if (!camara.current) throw new Error('Primero debes abrir la cámara.')
    const foto = await capturarFotograma(camara.current.video, 0.9)
    if (!foto || foto.size === 0) {
      throw new Error('La cámara no devolvió una fotografía válida. Revisa la iluminación.')
    }
    return foto
  }

  async function registrarReferencia(): Promise<void> {
    if (ocupado) return
    setError(undefined)
    setMensaje(undefined)
    setOcupado(true)
    try {
      const foto = await fotografiar()
      const ruta = await subirFotoDeIdentidad({
        sessionId, studentId, kind: 'reference_face', foto, token
      })
      await api.registerReferenceFace(ruta, token)
      if (!montado.current) return
      setReferenciaRegistrada(true)
      cerrar()
      setMensaje('Foto de referencia registrada. Abre otra vez la cámara para tomar una foto actual y solicitar la comparación.')
    } catch (fallo) {
      if (montado.current) setError(fallo instanceof Error ? fallo.message : 'No se pudo registrar la referencia.')
    } finally {
      if (montado.current) setOcupado(false)
    }
  }

  async function comprobarIdentidad(): Promise<void> {
    if (ocupado || !permitirNuevaSolicitud) return
    setError(undefined)
    setMensaje(undefined)
    setOcupado(true)
    try {
      const foto = await fotografiar()
      const ruta = await subirFotoDeIdentidad({ sessionId, studentId, kind: 'image', foto, token })
      // 202 = trabajo encolado, NO coincidencia confirmada.
      const participante = await api.requestIdentityCheck(sessionId, ruta, token)
      if (!montado.current) return
      onCheckRequested(participante)
      setSolicitudEnviada(true)
      cerrar()
      setMensaje('Solicitud enviada. Espera la comprobación automática. Si no coincide o no se puede evaluar, el docente podrá admitirte manualmente.')
    } catch (fallo) {
      if (montado.current) {
        const descripcion = fallo instanceof Error ? fallo.message : 'No se pudo solicitar la verificación.'
        setError(
          descripcion.toLowerCase().includes('referencia')
            ? 'Aún no tienes una foto de referencia registrada. Captúrala primero y vuelve a intentarlo.'
            : descripcion
        )
      }
    } finally {
      if (montado.current) setOcupado(false)
    }
  }

  return (
    <section className="tarjeta" aria-labelledby="titulo-identidad-facial">
      <div className="tarjeta-cuerpo">
        <h2 id="titulo-identidad-facial">Verificación de identidad facial</h2>
        <p className="subtitulo">
          Necesitamos una fotografía de referencia (una sola vez) y otra actual para
          comprobar que eres la misma persona. No se graba vídeo continuo.
        </p>
        <p className="ayuda">
          Si ya registraste tu foto en un examen anterior, puedes verificarte
          directamente. Si nunca la registraste, hazlo primero.
        </p>
        <div ref={contenedor} style={{ marginTop: 'var(--e4)' }} />
        {camaraAbierta ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--e3)', marginTop: 'var(--e4)' }}>
            <button type="button" className="boton" onClick={() => void registrarReferencia()} disabled={ocupado || !permitirNuevaSolicitud}>
              {referenciaRegistrada ? 'Reemplazar foto de referencia' : 'Registrar foto de referencia'}
            </button>
            <button type="button" className="boton boton-secundario" onClick={() => void comprobarIdentidad()} disabled={ocupado || !permitirNuevaSolicitud}>
              Comprobar mi identidad
            </button>
            <button type="button" className="boton boton-secundario" onClick={cerrar} disabled={ocupado}>
              Cerrar cámara
            </button>
          </div>
        ) : permitirNuevaSolicitud ? (
          <button type="button" className="boton" onClick={() => void iniciarCamara()} disabled={ocupado} style={{ marginTop: 'var(--e4)' }}>
            {ocupado ? 'Preparando cámara…' : 'Abrir cámara para mi identidad'}
          </button>
        ) : null}
        {mensaje && <p className="aviso aviso-neutro" role="status" style={{ marginTop: 'var(--e4)' }}>{mensaje}</p>}
        {error && <p className="aviso" role="alert" style={{ marginTop: 'var(--e4)' }}>{error}</p>}
        {verificationStatus === 'failed' && (
          <p className="aviso aviso-neutro" role="status">
            La verificación no se pudo confirmar. Puedes intentarlo nuevamente o
            esperar a que tu docente revise y autorice el ingreso.
          </p>
        )}
      </div>
    </section>
  )
}
