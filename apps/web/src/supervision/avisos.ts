/**
 * HU-025: lo que el estudiante ve cuando se detecta algo, mientras rinde.
 *
 * Dos partes:
 *
 * - **Qué se le dice** (`avisoParaEvento`). El tono documenta, no acusa. Lo de
 *   hablar en voz alta lo dice con todas las letras, porque es la promesa del
 *   proyecto: leer la pregunta no es una infracción.
 * - **Cuándo se le dice** (`GestorDeAvisos`). Un aviso cada tres segundos es
 *   ruido, y a quien no está haciendo nada malo lo pone nervioso. El gestor
 *   silencia la repetición, junta lo que ocurre a la vez y lo retira solo.
 *
 * El gestor no sabe nada de React a propósito: así su comportamiento en el
 * tiempo se prueba con un reloj falso, sin montar una pantalla.
 */

import type { EventType } from '../lib/api'

/** Cuánto se calla la misma señal antes de volver a avisar de ella. */
export const SILENCIO_MISMA_SENAL_MS = 8_000
/** Cuánto se queda el aviso antes de retirarse solo. */
export const DURACION_AVISO_MS = 6_000
/** Dos señales dentro de esta ventana se cuentan como una sola cosa. */
export const VENTANA_SIMULTANEIDAD_MS = 2_500

export interface AvisoSupervision {
  /** Los problemas técnicos no son un `EventType`: no se registran como
   *  señal del estudiante, solo se le avisan a él. */
  tipo: TipoDeAviso
  titulo: string
  detalle: string
}

/** Un fallo técnico de la cámara, que no es una señal de supervisión. */
export type ProblemaCamara = 'camera_interrupted' | 'camera_no_image'

/** Un fallo técnico del micrófono o del VAD, que no es una señal de supervisión. */
export type ProblemaAudio = 'audio_vad_failed' | 'audio_interrupted'

/** Varios modulos de supervision caidos a la vez. Tampoco es una senal. */
export type ProblemaSupervision = 'vision_unavailable'

/**
 * Todo lo de lo que se puede avisar: senales de supervision y fallos tecnicos.
 *
 * En un alias porque el gestor silencia y agrupa por este tipo, y tenerlo
 * escrito a mano en tres sitios ya hizo que anadir los fallos de audio
 * compilara en uno y no en los otros dos.
 */
export type TipoDeAviso = EventType | ProblemaCamara | ProblemaAudio | ProblemaSupervision

/** Cómo lo nombra el monitor de cámara y el canal en vivo, sin el prefijo. */
export type EstadoCamaraFallida = 'interrupted' | 'no_image'

/**
 * Qué se le dice al estudiante cuando su cámara falla.
 *
 * Un problema técnico **no es una acusación y no termina el examen**. El texto
 * lo dice con todas las letras, igual que el de hablar en voz alta: quien se
 * queda sin cámara por un cable suelto no debe leer que ha infringido nada.
 */
export function avisoCamara(estado: EstadoCamaraFallida): AvisoSupervision {
  return estado === 'interrupted'
    ? {
        tipo: 'camera_interrupted',
        titulo: 'Se perdió la conexión con la cámara',
        detalle:
          'Comprueba el permiso o la conexión de tu cámara y vuelve a intentarlo. El examen continúa; el docente podrá revisar esta interrupción.'
      }
    : {
        tipo: 'camera_no_image',
        titulo: 'No llega una imagen útil de la cámara',
        detalle:
          'Puede haber poca luz, una lente tapada o una imagen congelada. Ajusta la cámara y vuelve a intentarlo. No implica una infracción.'
      }
}

/**
 * Qué se le dice al estudiante cuando la detección de audio/VAD falla técnicamente.
 */
export function avisoAudio(problema: ProblemaAudio): AvisoSupervision {
  return problema === 'audio_vad_failed'
    ? {
        tipo: 'audio_vad_failed',
        titulo: 'Detección de voz no disponible',
        detalle:
          'El reconocimiento de voz no pudo iniciarse en este equipo. El examen continúa; el docente podrá ver que el módulo no estuvo activo.'
      }
    : {
        tipo: 'audio_interrupted',
        titulo: 'Se perdió la conexión con el micrófono',
        detalle:
          'Comprueba la conexión de tu micrófono. El examen continúa; el docente podrá revisar esta interrupción.'
      }
}

/**
 * Resuelve el aviso adecuado cuando un detector no consigue prepararse al iniciar la supervisión.
 */
export function avisoDetectorFallido(nombre: string): AvisoSupervision {
  if (nombre === 'habla') return avisoAudio('audio_vad_failed')
  return {
    tipo: 'camera_interrupted',
    titulo: `Módulo no disponible: ${nombre}`,
    detalle:
      `El detector (${nombre}) no pudo iniciarse en este equipo. El examen continúa; el docente podrá ver que el módulo no estuvo activo.`
  }
}

/**
 * Lo mismo, pero cuando caen varios módulos a la vez.
 *
 * Un aviso por detector sería una pila de cuatro cuadros encima de alguien que
 * está rindiendo, y la causa de que cuatro fallen juntos casi siempre es una
 * sola. Con uno, el estudiante se entera igual y el docente ve la lista.
 *
 * Con un solo módulo caído delega en `avisoDetectorFallido`, que sabe
 * distinguir el micrófono de la cámara.
 */
export function avisoDetectoresNoDisponibles(nombres: readonly string[]): AvisoSupervision | null {
  if (nombres.length === 0) return null
  if (nombres.length === 1) return avisoDetectorFallido(nombres[0])
  return {
    tipo: 'vision_unavailable',
    titulo: 'Parte de la supervisión no está activa',
    detalle: `No se pudieron iniciar estos módulos en tu equipo: ${nombres.join(', ')}. El examen continúa y no implica ninguna infracción; el docente verá que no estuvieron activos.`
  }
}

export function avisoParaEvento(evento: EventType): AvisoSupervision | null {
  switch (evento) {
    case 'gaze_away':
      return {
        tipo: evento,
        titulo: 'Orientación de cabeza fuera de pantalla',
        detalle:
          'Se detectó que giraste la cabeza durante varios segundos. Mira hacia el examen y mantén la cámara estable. El docente podrá revisar el evento.'
      }
    case 'face_absent':
      return {
        tipo: evento,
        titulo: 'No se detecta tu rostro',
        detalle:
          'Vuelve al encuadre y comprueba que tu cámara esté estable e iluminada. El examen continúa.'
      }
    case 'extra_person':
      return {
        tipo: evento,
        titulo: 'Se detectó otra persona',
        detalle:
          'La cámara detectó más de un rostro durante varios segundos. Se ha registrado para revisión del docente.'
      }
    case 'speech_detected':
      return {
        tipo: evento,
        titulo: 'Se detectó voz',
        detalle:
          'Se registró un fragmento de voz durante el examen. Hablar no significa una infracción: el docente revisará el contexto.'
      }
    case 'prohibited_object':
      return {
        tipo: evento,
        titulo: 'Se detectó un celular u objeto no permitido',
        detalle: 'La cámara detectó un objeto que debe permanecer fuera del área del examen. El docente podrá revisar la señal.'
      }
    default:
      return null
  }
}

/** El aviso que se muestra: uno solo, aunque lo compongan varias señales. */
export interface AvisoVisible {
  id: string
  titulo: string
  detalle: string
  /** Las señales que lo componen. La primera es la que lo abrió. */
  eventos: TipoDeAviso[]
}

type Oyente = (aviso: AvisoVisible | null) => void

/**
 * Decide **cuándo** se ve un aviso y cuándo no.
 *
 * Tres reglas, y cada una resuelve una forma distinta de molestar:
 *
 * 1. La misma señal no vuelve a avisar hasta pasado `SILENCIO_MISMA_SENAL_MS`.
 *    Sin esto, mirar a un lado diez segundos lanza un aviso por episodio.
 * 2. Lo que cae dentro de `VENTANA_SIMULTANEIDAD_MS` se junta en un aviso.
 *    Si la cámara y el micrófono saltan a la vez, es un suceso, no dos.
 * 3. El aviso se retira solo. No hay que obligar a nadie a cerrar una caja
 *    para seguir respondiendo.
 */
export class GestorDeAvisos {
  private ultimaVezPorTipo = new Map<TipoDeAviso, number>()
  private visible: AvisoVisible | null = null
  private oyentes = new Set<Oyente>()
  private temporizador?: ReturnType<typeof setTimeout>

  constructor(
    private readonly silencioMs = SILENCIO_MISMA_SENAL_MS,
    private readonly duracionMs = DURACION_AVISO_MS,
    private readonly ventanaMs = VENTANA_SIMULTANEIDAD_MS
  ) {}

  suscribir(oyente: Oyente): () => void {
    this.oyentes.add(oyente)
    oyente(this.visible)
    return () => {
      this.oyentes.delete(oyente)
    }
  }

  /** Devuelve `true` si la señal llegó a mostrarse.
   *
   *  Admite un `EventType` —y resuelve su texto— o un aviso ya construido.
   *  Lo segundo hace falta para los problemas de cámara: no son señales de
   *  supervisión, no tienen `EventType`, y pasarlos como tal los dejaba caer
   *  en silencio aquí mismo, sin que nada fallara. */
  registrar(entrada: EventType | AvisoSupervision, ahoraMs: number = Date.now()): boolean {
    const aviso = typeof entrada === 'string' ? avisoParaEvento(entrada) : entrada
    if (!aviso) return false
    const evento = aviso.tipo

    const ultima = this.ultimaVezPorTipo.get(evento)
    if (ultima !== undefined && ahoraMs - ultima < this.silencioMs) return false
    this.ultimaVezPorTipo.set(evento, ahoraMs)

    const junto =
      this.visible !== null &&
      this.abiertoEn !== undefined &&
      ahoraMs - this.abiertoEn <= this.ventanaMs

    if (junto && this.visible) {
      // Se encadenan los títulos ya resueltos en vez de volver a buscarlos por
      // su tipo: los problemas de cámara no tienen `EventType`, así que
      // re-resolverlos los perdía justo al combinarse con otra señal.
      const anteriores =
        this.visible.eventos.length > 1 ? this.visible.detalle : this.visible.titulo
      this.mostrar(
        {
          id: `${this.visible.id}+${evento}`,
          titulo: 'Se detectaron varias señales',
          detalle: `${anteriores} · ${aviso.titulo}`,
          eventos: [...this.visible.eventos, evento]
        },
        this.abiertoEn ?? ahoraMs
      )
    } else {
      this.mostrar(
        { id: `${evento}-${ahoraMs}`, titulo: aviso.titulo, detalle: aviso.detalle, eventos: [evento] },
        ahoraMs
      )
    }
    return true
  }

  descartar(): void {
    this.mostrar(null)
  }

  destruir(): void {
    if (this.temporizador) clearTimeout(this.temporizador)
    this.oyentes.clear()
    this.visible = null
  }

  private abiertoEn?: number

  private mostrar(aviso: AvisoVisible | null, abiertoEn?: number): void {
    if (this.temporizador) {
      clearTimeout(this.temporizador)
      this.temporizador = undefined
    }
    this.visible = aviso
    this.abiertoEn = aviso ? abiertoEn : undefined
    for (const oyente of this.oyentes) oyente(aviso)
    if (aviso) {
      this.temporizador = setTimeout(() => this.mostrar(null), this.duracionMs)
    }
  }
}
