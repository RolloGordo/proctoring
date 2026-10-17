/**
 * Enciende la supervisión mientras el estudiante rinde.
 *
 * Junta las cuatro piezas: abre la cámara, corre los detectores sobre cada
 * fotograma, agrupa con histéresis y manda las señales con reintento.
 *
 * **Si la cámara falla, el examen sigue.** Un modelo que no carga o un permiso
 * denegado no pueden dejar a alguien sin rendir: se avisa al estudiante y queda
 * registrado, y el docente decide después. Es la misma idea que con la
 * verificación facial.
 */

import { useEffect, useRef, useState } from 'react'
import { supabase } from '../lib/supabase'
import { abrirCamara, CamaraNoDisponibleError, capturarFotograma } from './camara'
import { CapturasPorCondicion } from './capturasVision'
import { CameraHealthMonitor, meanVideoBrightness, type CameraHealth } from './cameraHealth'
import {
  avisoCamara,
  avisoDetectoresNoDisponibles,
  avisoParaEvento,
  type AvisoSupervision
} from './avisos'
import { recordDiagnostic, type DiagnosticCode } from './diagnostics'
import type { SenalDetectada } from './tipos'
import { EmisorDeSenales } from './emisor'
import { publicarFotogramas, type AjustesMonitoreo, type Publicacion } from './monitoreo'
import { SeguimientoCondicion } from './seguimiento'
import type { Detector } from './tipos'

/**
 * Cada cuánto se mira un fotograma.
 *
 * Ocho por segundo. Eran quince, y con la cámara subida a 960x540 para que el
 * docente vea algo útil (punto 12) quince inferencias por segundo calientan el
 * equipo sin aportar nada: ninguna de las condiciones que se vigilan dura menos
 * de tres segundos.
 */
const INTERVALO_MS = 125

export interface OpcionesSupervision {
  sessionId: string
  studentId?: string
  questionId: string | null
  token?: string
  /** Los detectores a correr. Vacío = no se enciende la cámara. */
  detectores: Detector[]
  /** Si hace falta el micrófono (detección de habla). */
  conAudio?: boolean
  /**
   * Ajustes del módulo `live_monitoring`, o `null` si el docente no lo activó.
   *
   * Activarlo enciende la cámara aunque no haya ningún detector: un examen con
   * supervisión mínima pero monitoreo en vivo es una combinación válida.
   */
  monitoreo?: AjustesMonitoreo | null
  /**
   * Avisa cuando el docente empieza o deja de mirar la cámara.
   *
   * Lo pide la pantalla para decírselo al estudiante. Va por callback y no en
   * el valor devuelto para que un cambio de estado de la pantalla no reinicie
   * la cámara.
   */
  onObservado?: (observado: boolean) => void
  /** Un aviso por episodio, compartido con el módulo de audio. */
  onAviso?: (aviso: AvisoSupervision) => void
  /** Muestra una previsualización sin abrir otra cámara. */
  onCamara?: (stream: MediaStream | null) => void
  /** Botón de reintento si el navegador pierde la cámara. */
  reintento?: number
  /** Permite apagarlo todo (por ejemplo, si el examen ya se entregó). */
  activa?: boolean
}

export type EstadoSupervision =
  | { tipo: 'apagada' }
  | { tipo: 'iniciando' }
  | { tipo: 'activa' }
  /**
   * La camara va, pero algun detector no.
   *
   * Es un estado propio y no un 'fallo' porque el examen sigue y el estudiante
   * no ha hecho nada: lo que hay que decirle es que esa parte no se esta
   * supervisando, no que algo va mal por su culpa.
   */
  | { tipo: 'degradada'; mensaje: string; fallidos: string[] }
  | { tipo: 'fallo'; mensaje: string }

export function useSupervision({
  sessionId,
  studentId,
  questionId,
  token,
  detectores,
  conAudio = false,
  monitoreo = null,
  onObservado,
  onAviso,
  onCamara,
  reintento = 0,
  activa = true
}: OpcionesSupervision): EstadoSupervision {
  const [estado, setEstado] = useState<EstadoSupervision>({ tipo: 'apagada' })
  const emisorRef = useRef<EmisorDeSenales | null>(null)

  // Por referencia: si entrara en las dependencias del efecto, cada renderizado
  // de la pantalla apagaría y encendería la cámara.
  const observadoRef = useRef(onObservado)
  useEffect(() => {
    observadoRef.current = onObservado
  }, [onObservado])

  const callbacksRef = useRef({ onAviso, onCamara })
  useEffect(() => {
    callbacksRef.current = { onAviso, onCamara }
  }, [onAviso, onCamara])

  // Sin estudiante no se puede reportar nada: la API exige que el `student_id`
  // coincida con el del token. Se calcula aqui, no dentro del efecto: poner el
  // estado en 'apagada' desde dentro provocaria un renderizado de mas.
  const habilitada =
    activa && (detectores.length > 0 || monitoreo !== null) && studentId !== undefined

  // La pregunta cambia mientras el estudiante responde; el emisor se entera sin
  // reiniciar la cámara.
  useEffect(() => {
    emisorRef.current?.actualizarContexto({ questionId })
  }, [questionId])

  useEffect(() => {
    if (!habilitada || studentId === undefined) return

    // En una constante: el estrechamiento de `studentId` no sobrevive dentro de
    // `encender`, porque es un parámetro desestructurado y no una constante.
    const alumnoId = studentId

    let cancelado = false
    let cerrarCamara: (() => void) | null = null
    let temporizador: ReturnType<typeof setInterval> | undefined
    let chequeoCamara: ReturnType<typeof setInterval> | undefined
    let envioEnVivo: Publicacion | null = null
    let quitarEscuchaCamara: (() => void) | null = null
    let ultimoFallo: CameraHealth | null = null
    const saludCamara = new CameraHealthMonitor()

    /** Los módulos que ahora mismo no están supervisando. */
    const fallidos = new Set<string>()
    /** Fallos seguidos al observar, por detector. Uno aislado no tumba nada. */
    const erroresSeguidos = new Map<string, number>()

    /**
     * Cuánto trabajó de verdad cada detector.
     *
     * Está aquí por una razón concreta: tras varios exámenes reales sin una sola
     * señal de cámara ni de voz, no se podía distinguir «el detector no arrancó»
     * de «arrancó, miró miles de fotogramas y nunca le pareció que pasara algo».
     * Son dos fallos distintos y se arreglan en sitios distintos. Sin este
     * recuento hay que adivinar, y adivinar ya costó bastante.
     */
    const trabajo = new Map<string, { fotogramas: number; veredictos: number; episodios: number }>(
      detectores.map((d) => [d.nombre, { fotogramas: 0, veredictos: 0, episodios: 0 }])
    )

    const informar = (
      code: DiagnosticCode,
      module?: string,
      details?: Record<string, string | number | boolean>
    ) => {
      void recordDiagnostic(supabase, {
        session_id: sessionId,
        student_id: alumnoId,
        code,
        ...(module ? { module } : {}),
        ...(details ? { details } : {})
      })
    }

    /** Pone al día el estado, el canal del docente y el aviso en pantalla. */
    const reportarFallidos = () => {
      const nombres = [...fallidos].sort()
      envioEnVivo?.reportarVision?.(
        nombres.length === 0
          ? 'active'
          : nombres.length >= detectores.length
            ? 'unavailable'
            : 'degraded',
        nombres
      )
      if (nombres.length > 0) {
        const aviso = avisoDetectoresNoDisponibles(nombres)
        setEstado({
          tipo: 'degradada',
          mensaje: aviso?.detalle ?? `No están activos: ${nombres.join(', ')}.`,
          fallidos: nombres
        })
        if (aviso) callbacksRef.current.onAviso?.(aviso)
      } else if (ultimoFallo === null) {
        setEstado({ tipo: 'activa' })
      }
    }

    const emisor = new EmisorDeSenales({ sessionId, studentId, questionId, token })
    emisorRef.current = emisor
    const seguimientos = new Map(
      detectores.map((d) => [d.nombre, new SeguimientoCondicion({ minimoMs: d.minimoMs })])
    )
    const ultimaMetadata = new Map<string, Record<string, unknown>>()
    const capturas = new Map(
      detectores.filter((d) => d.evento !== 'speech_detected')
        .map((d) => [d.nombre, new CapturasPorCondicion(d.minimoMs)])
    )
    const notificar = (evento: SenalDetectada['evento']) => {
      const aviso = avisoParaEvento(evento)
      if (aviso) callbacksRef.current.onAviso?.(aviso)
    }

    async function encender(): Promise<void> {
      setEstado({ tipo: 'iniciando' })
      try {
        const camara = await abrirCamara({ audio: conAudio })
        if (cancelado) {
          camara.cerrar()
          return
        }
        cerrarCamara = camara.cerrar
        const stream = camara.video.srcObject as MediaStream
        callbacksRef.current.onCamara?.(stream)
        const pista = stream.getVideoTracks()[0]
        const falloCamara = (tipo: Exclude<CameraHealth, 'active'>) => {
          if (cancelado || ultimoFallo === tipo) return
          ultimoFallo = tipo
          const mensaje = tipo === 'interrupted'
            ? 'La cámara se desconectó. Reconéctala y selecciona Reintentar cámara.'
            : 'La cámara no está entregando imagen útil. Comprueba la luz o si otra aplicación está usando la cámara y pulsa Reintentar.'
          setEstado({ tipo: 'fallo', mensaje })
          callbacksRef.current.onAviso?.(avisoCamara(tipo))
          envioEnVivo?.reportarCamara?.(tipo)
          informar(tipo === 'interrupted' ? 'camera_interrupted' : 'camera_no_image')
        }
        const perdidaCamara = () => falloCamara('interrupted')
        pista?.addEventListener('ended', perdidaCamara)
        quitarEscuchaCamara = () => pista?.removeEventListener('ended', perdidaCamara)

        // El monitoreo en vivo usa el mismo `<video>` que los detectores: una
        // sola cámara abierta. Y no empieza a enviar por abrirse: espera a que
        // el docente entre al canal.
        if (monitoreo !== null && supabase) {
          envioEnVivo = publicarFotogramas({
            cliente: supabase,
            sessionId,
            studentId: alumnoId,
            video: camara.video,
            ajustes: monitoreo,
            onObservado: (observado) => observadoRef.current?.(observado)
          })
        }

        // Lightweight diagnostic once per second; never stores the sampled image.
        chequeoCamara = setInterval(() => {
          const status = saludCamara.check(
            Date.now(), camara.video.currentTime, pista?.readyState ?? 'ended',
            meanVideoBrightness(camara.video)
          )
          if (status !== 'active') falloCamara(status)
          else if (ultimoFallo !== null) {
            ultimoFallo = null
            envioEnVivo?.reportarCamara?.('active')
            informar('camera_recovered')
            reportarFallidos()
          }
        }, 1000)

        // Un detector que no carga se descarta y los demás siguen, pero **se
        // dice**: queda en `fallidos`, se lo ve el estudiante, se lo ve el
        // docente en vivo y queda registrado en `supervision_diagnostics`.
        const listos: Detector[] = []
        for (const detector of detectores) {
          try {
            await detector.preparar?.({
              stream: camara.video.srcObject as MediaStream,
              captureSender: () => {
                const enviar = emisor.captureSender()
                return (senal) => {
                  enviar(senal)
                  notificar(senal.evento)
                }
              }
            })
            if (cancelado) {
              detector.detener?.()
              return
            }
            listos.push(detector)
          } catch (fallo) {
            detector.detener?.()
            fallidos.add(detector.nombre)
            console.error(`[supervisión] no se pudo preparar ${detector.nombre}`, fallo)
            informar('vision_module_failed', detector.nombre, {
              reason: fallo instanceof Error ? fallo.message.slice(0, 200) : 'desconocido'
            })
          }
        }
        if (cancelado) return
        reportarFallidos()

        temporizador = setInterval(() => {
          // Never run vision inference on a known stopped or unusable stream.
          if (ultimoFallo !== null) return
          const ahoraMs = Date.now()
          for (const detector of listos) {
            if (detector.ownsSegments || fallidos.has(detector.nombre)) continue
            const seguimiento = seguimientos.get(detector.nombre)
            if (!seguimiento) continue
            let veredicto
            try {
              veredicto = detector.observar({ video: camara.video, ahoraMs })
              erroresSeguidos.delete(detector.nombre)
            } catch (fallo) {
              // Un fallo aislado no lo tumba: un fotograma a medio decodificar
              // lanza y al siguiente ya va. Tres seguidos sí son un detector
              // roto, y entonces se deja de fingir que supervisa.
              const seguidos = (erroresSeguidos.get(detector.nombre) ?? 0) + 1
              erroresSeguidos.set(detector.nombre, seguidos)
              if (seguidos >= 3 && !fallidos.has(detector.nombre)) {
                console.error(`[supervisión] ${detector.nombre} falla al observar`, fallo)
                fallidos.add(detector.nombre)
                informar('vision_module_failed', detector.nombre, {
                  reason: fallo instanceof Error ? fallo.message.slice(0, 200) : 'desconocido',
                  consecutive: seguidos
                })
                reportarFallidos()
              }
              continue
            }
            const cuenta = trabajo.get(detector.nombre)
            if (cuenta) {
              cuenta.fotogramas += 1
              if (veredicto.activa) cuenta.veredictos += 1
            }
            if (veredicto.metadata) ultimaMetadata.set(detector.nombre, veredicto.metadata)

            const capturador = capturas.get(detector.nombre)
            if (capturador?.actualizar(
              veredicto,
              ahoraMs,
              () => capturarFotograma(camara.video, 0.75)
            )) notificar(detector.evento)
            const episodio = seguimiento.actualizar(veredicto.activa, ahoraMs)
            if (episodio) {
              if (cuenta) cuenta.episodios += 1
              emisor.emitir({
                evento: detector.evento,
                inicioMs: episodio.inicioMs,
                duracionMs: episodio.duracionMs,
                metadata: ultimaMetadata.get(detector.nombre) ?? {},
                image: capturador?.consumir()
              })
            } else if (!seguimiento.activa && capturador) {
              // El episodio era demasiado corto: no se guarda ninguna captura.
              capturador.reiniciar()
            }
          }
        }, INTERVALO_MS)

        if (ultimoFallo === null) reportarFallidos()
      } catch (fallo) {
        if (cancelado) return
        const mensaje =
          fallo instanceof CamaraNoDisponibleError
            ? fallo.message
            : 'No se pudo encender la supervisión.'
        // El examen sigue: se avisa y queda constancia, pero no se bloquea.
        console.error('[supervisión]', fallo)
        setEstado({ tipo: 'fallo', mensaje })
        callbacksRef.current.onAviso?.(avisoCamara('interrupted'))
        informar('camera_interrupted', undefined, {
          reason: fallo instanceof Error ? fallo.message.slice(0, 200) : 'desconocido'
        })
      }
    }

    void encender()

    return () => {
      cancelado = true
      clearInterval(temporizador)
      clearInterval(chequeoCamara)
      // Las condiciones abiertas se cierran antes de salir: si no, la última
      // señal de cada detector se perdería.
      for (const [nombre, seguimiento] of seguimientos) {
        const episodio = seguimiento.cerrar()
        const detector = detectores.find((d) => d.nombre === nombre)
        if (episodio && detector && !detector.ownsSegments) {
          emisor.emitir({
            evento: detector.evento,
            inicioMs: episodio.inicioMs,
            duracionMs: episodio.duracionMs,
            metadata: ultimaMetadata.get(nombre) ?? {},
            image: capturas.get(nombre)?.consumir()
          })
        }
        detector?.detener?.()
      }
      // Cuánto trabajó cada detector durante el examen. Una fila por módulo,
      // sin imágenes: es lo que permite leer después «miró 4 800 fotogramas y
      // no le pareció que pasara nada» en vez de suponerlo.
      for (const [nombre, cuenta] of trabajo) {
        if (cuenta.fotogramas === 0 && !fallidos.has(nombre)) continue
        informar('vision_module_summary', nombre, {
          frames: cuenta.fotogramas,
          verdicts: cuenta.veredictos,
          episodes: cuenta.episodios,
          failed: fallidos.has(nombre)
        })
      }
      void emisor.cerrar()
      emisorRef.current = null
      // Antes de apagar la cámara: salir del canal deja de anunciar presencia,
      // y el docente ve «desconectado» en lugar de una imagen congelada.
      void envioEnVivo?.detener()
      observadoRef.current?.(false)
      quitarEscuchaCamara?.()
      callbacksRef.current.onCamara?.(null)
      cerrarCamara?.()
    }
    // `questionId` se actualiza por su propio efecto: incluirlo aquí reiniciaría
    // la cámara en cada pregunta.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [habilitada, sessionId, studentId, token, detectores, conAudio, monitoreo, reintento])

  return habilitada ? estado : { tipo: 'apagada' }
}
