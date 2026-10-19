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
import {
  CameraHealthMonitor,
  debeSeguirObservando,
  meanVideoBrightness,
  type CameraHealth
} from './cameraHealth'
import {
  avisoCamara,
  avisoDetectoresNoDisponibles,
  avisoParaEvento,
  type AvisoSupervision
} from './avisos'
import { recordDiagnostic, type DiagnosticCode } from './diagnostics'
import { prepararDetectores, type Arranque } from './arranque'
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

    const emisor = new EmisorDeSenales(
      { sessionId, studentId, questionId, token },
      (motivo) => informar('audio_segment_lost', 'habla', { reason: motivo }),
      (motivo) => informar('image_evidence_lost', 'captura', { reason: motivo }),
      (evento, motivo) => informar('signal_rejected', evento, { reason: motivo }),
      (intentos, pendientes) =>
        informar('signal_queue_stuck', 'cola', { attempts: intentos, pending: pendientes }),
      (motivo) => informar('audio_segment_lost', 'habla', { reason: `descartado: ${motivo}` })
    )
    emisorRef.current = emisor
    const seguimientos = new Map(
      detectores.map((d) => [d.nombre, new SeguimientoCondicion({ minimoMs: d.minimoMs })])
    )
    const ultimaMetadata = new Map<string, Record<string, unknown>>()
    const capturas = new Map(
      detectores
        .filter((d) => d.evento !== 'speech_detected')
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
          // **Solo 'interrupted' es un fallo.** Con 'no_image' la cámara sigue
          // abierta y los detectores siguen trabajando: decirle al estudiante
          // que la supervisión falló seria falso, y poner el estado en 'fallo'
          // le quitaba de la pantalla la vista de su propia camara, que es
          // justo lo que necesita para arreglar la luz o el encuadre.
          if (tipo === 'interrupted') {
            setEstado({
              tipo: 'fallo',
              mensaje: 'La cámara se desconectó. Reconéctala y selecciona Reintentar cámara.'
            })
          }
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
            Date.now(),
            camara.video.currentTime,
            pista?.readyState ?? 'ended',
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
        // A la vez y con límite de tiempo: ver `arranque.ts`. En serie, un
        // detector que no respondía nunca dejaba sin arrancar a los que vinieran
        // detrás **y** al bucle que mira fotogramas, que se crea más abajo.
        // `listos` crece segun van arrancando, y el bucle de abajo lo recorre
        // en cada vuelta: el que tarde no retrasa a los que ya estan.
        const listos: Detector[] = []
        const incorporar = ({ detector, listo, motivo }: Arranque): void => {
          if (cancelado) {
            detector.detener?.()
            return
          }
          if (listo) {
            listos.push(detector)
          } else {
            fallidos.add(detector.nombre)
            console.error(`[supervisión] no se pudo preparar ${detector.nombre}: ${motivo}`)
            informar('vision_module_failed', detector.nombre, { reason: motivo ?? 'desconocido' })
          }
          reportarFallidos()
        }

        const preparando = prepararDetectores(
          detectores,
          {
            stream: camara.video.srcObject as MediaStream,
            onSpeechStart: () => notificar('speech_detected'),
            captureSender: () => {
              const enviar = emisor.captureSender()
              return (senal) => {
                enviar(senal)
                notificar(senal.evento)
              }
            }
          },
          undefined,
          incorporar
        )
        // No se espera aqui a proposito; se recoge al salir para apagar lo que
        // hubiera quedado a medias.
        void preparando.then((arranques) => {
          if (cancelado) for (const { detector } of arranques) detector.detener?.()
        })

        temporizador = setInterval(() => {
          // **Solo se deja de observar si la pista se terminó de verdad.**
          //
          // Antes se paraba también con 'no_image', y eso era la causa de que un
          // examen entero no registrara nada: 'no_image' lo decide el monitor de
          // salud cuando la imagen sale muy oscura cuatro segundos seguidos, o
          // cuando `currentTime` no avanza. Rindiendo de noche, o cada vez que
          // el estudiante se va a otra ventana y el navegador deja de pintar un
          // <video> suelto, la supervisión se apagaba sola y en silencio.
          //
          // Una imagen mala no es ausencia de imagen: MediaPipe puede seguir
          // viendo una cara con poca luz, y «se fue del encuadre» importa más,
          // no menos, cuando la imagen es dudosa. Se sigue observando y se
          // apunta el estado de la cámara en la metadata, para que el docente
          // lea «esto se midió con imagen pobre» en lugar de no leer nada.
          if (!debeSeguirObservando(ultimoFallo)) return
          const saludActual = ultimoFallo
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
            if (veredicto.metadata) {
              ultimaMetadata.set(
                detector.nombre,
                saludActual === null
                  ? veredicto.metadata
                  : { ...veredicto.metadata, camera_health: saludActual }
              )
            }

            const capturador = capturas.get(detector.nombre)
            if (
              capturador?.actualizar(veredicto, ahoraMs, () =>
                capturarFotograma(camara.video, 0.75)
              )
            )
              notificar(detector.evento)
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
        const detector = detectores.find((d) => d.nombre === nombre)
        // El detector de habla no pasa por el bucle de observacion: se emite a
        // si mismo desde el VAD (`ownsSegments`), asi que no cuenta fotogramas.
        // Pero su fila es la que mas falta hacia, porque es la mitad del
        // problema: sin ella no se sabe si el microfono se abrio y no oyo nada
        // o si nunca llego a abrirse.
        const propio = detector?.ownsSegments === true
        // **Siempre una fila, también con cero fotogramas.** Saltarla escondía
        // justo el caso que hacía falta ver: un detector que arrancó bien y al
        // que nunca se le llegó a preguntar nada no dejaba rastro, y en el
        // expediente se lee igual que si no hubiera pasado nada.
        // El que se emite a si mismo lleva sus propios numeros: `episodes`
        // vive en el bucle de fotogramas, por el que no pasa, asi que para el
        // era siempre cero. Decia «0 episodios» tanto si el microfono no oyo
        // nada como si oyo y la senal se perdio, que no es lo mismo.
        let propio_detalle: string | undefined
        if (propio) {
          try {
            propio_detalle = detector?.diagnostico?.()
          } catch {
            // Un detector roto puede fallar tambien al describirse.
          }
        }
        informar('vision_module_summary', nombre, {
          frames: cuenta.fotogramas,
          verdicts: cuenta.veredictos,
          episodes: cuenta.episodios,
          failed: fallidos.has(nombre),
          self_emitting: propio,
          ...(propio_detalle ? { detail: propio_detalle.slice(0, 300) } : {})
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
