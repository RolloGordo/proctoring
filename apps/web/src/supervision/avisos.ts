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
  /** Los problemas de cámara no son un `EventType`: no se registran como
   *  señal del estudiante, solo se le avisan a él. */
  tipo: EventType | ProblemaCamara
  titulo: string
  detalle: string
}

/** Un fallo técnico de la cámara, que no es una señal de supervisión. */
export type ProblemaCamara = 'camera_interrupted' | 'camera_no_image'

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
  eventos: Array<EventType | ProblemaCamara>
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
  private ultimaVezPorTipo = new Map<EventType | ProblemaCamara, number>()
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
