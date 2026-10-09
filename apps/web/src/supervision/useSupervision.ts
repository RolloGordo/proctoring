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
import { abrirCamara, CamaraNoDisponibleError } from './camara'
import { EmisorDeSenales } from './emisor'
import { publicarFotogramas, type AjustesMonitoreo, type Publicacion } from './monitoreo'
import { SeguimientoCondicion } from './seguimiento'
import type { Detector } from './tipos'

/** Cada cuánto se mira un fotograma. 15 por segundo basta y no calienta el equipo. */
const INTERVALO_MS = 66

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
  /** Permite apagarlo todo (por ejemplo, si el examen ya se entregó). */
  activa?: boolean
}

export type EstadoSupervision =
  | { tipo: 'apagada' }
  | { tipo: 'iniciando' }
  | { tipo: 'activa' }
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
    let envioEnVivo: Publicacion | null = null

    const emisor = new EmisorDeSenales({ sessionId, studentId, questionId, token })
    emisorRef.current = emisor
    const seguimientos = new Map(
      detectores.map((d) => [d.nombre, new SeguimientoCondicion({ minimoMs: d.minimoMs })])
    )
    const ultimaMetadata = new Map<string, Record<string, unknown>>()

    async function encender(): Promise<void> {
      setEstado({ tipo: 'iniciando' })
      try {
        const camara = await abrirCamara({ audio: conAudio })
        if (cancelado) {
          camara.cerrar()
          return
        }
        cerrarCamara = camara.cerrar

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

        // Un detector que no carga se descarta y los demás siguen.
        const listos: Detector[] = []
        for (const detector of detectores) {
          try {
            await detector.preparar?.({
              stream: camara.video.srcObject as MediaStream,
              captureSender: () => emisor.captureSender()
            })
            if (cancelado) {
              detector.detener?.()
              return
            }
            listos.push(detector)
          } catch (fallo) {
            detector.detener?.()
            console.error(`[supervisión] no se pudo preparar ${detector.nombre}`, fallo)
          }
        }
        if (cancelado) return

        temporizador = setInterval(() => {
          const ahoraMs = Date.now()
          for (const detector of listos) {
            if (detector.ownsSegments) continue
            const seguimiento = seguimientos.get(detector.nombre)
            if (!seguimiento) continue
            let veredicto
            try {
              veredicto = detector.observar({ video: camara.video, ahoraMs })
            } catch (fallo) {
              console.error(`[supervisión] ${detector.nombre} falló al observar`, fallo)
              continue
            }
            if (veredicto.metadata) ultimaMetadata.set(detector.nombre, veredicto.metadata)

            const episodio = seguimiento.actualizar(veredicto.activa, ahoraMs)
            if (episodio) {
              emisor.emitir({
                evento: detector.evento,
                inicioMs: episodio.inicioMs,
                duracionMs: episodio.duracionMs,
                metadata: ultimaMetadata.get(detector.nombre) ?? {}
              })
            }
          }
        }, INTERVALO_MS)

        setEstado({ tipo: 'activa' })
      } catch (fallo) {
        if (cancelado) return
        const mensaje =
          fallo instanceof CamaraNoDisponibleError
            ? fallo.message
            : 'No se pudo encender la supervisión.'
        // El examen sigue: se avisa y queda constancia, pero no se bloquea.
        console.error('[supervisión]', fallo)
        setEstado({ tipo: 'fallo', mensaje })
      }
    }

    void encender()

    return () => {
      cancelado = true
      clearInterval(temporizador)
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
            metadata: ultimaMetadata.get(nombre) ?? {}
          })
        }
        detector?.detener?.()
      }
      void emisor.cerrar()
      emisorRef.current = null
      // Antes de apagar la cámara: salir del canal deja de anunciar presencia,
      // y el docente ve «desconectado» en lugar de una imagen congelada.
      void envioEnVivo?.detener()
      observadoRef.current?.(false)
      cerrarCamara?.()
    }
    // `questionId` se actualiza por su propio efecto: incluirlo aquí reiniciaría
    // la cámara en cada pregunta.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [habilitada, sessionId, studentId, token, detectores, conAudio, monitoreo])

  return habilitada ? estado : { tipo: 'apagada' }
}
