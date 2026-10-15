/** HU-025: vocabulario común entre alertas de cámara y audio. No acusa. */
import type { EventType } from '../lib/api'

export interface AvisoSupervision {
  tipo: EventType
  titulo: string
  detalle: string
}

export function avisoParaEvento(evento: EventType): AvisoSupervision | null {
  switch (evento) {
    case 'gaze_away':
      return {
        tipo: evento,
        titulo: 'Orientación de cabeza fuera de pantalla',
        detalle: 'Se detectó que giraste la cabeza durante varios segundos. Mira hacia el examen y mantén la cámara estable. El docente podrá revisar el evento.'
      }
    case 'face_absent':
      return {
        tipo: evento,
        titulo: 'No se detecta tu rostro',
        detalle: 'Vuelve al encuadre y comprueba que tu cámara esté estable e iluminada. El examen continúa.'
      }
    case 'extra_person':
      return {
        tipo: evento,
        titulo: 'Se detectó otra persona',
        detalle: 'La cámara detectó más de un rostro durante varios segundos. Se ha registrado para revisión del docente.'
      }
    case 'speech_detected':
      return {
        tipo: evento,
        titulo: 'Se detectó voz',
        detalle: 'Se registró un fragmento de voz durante el examen. Hablar no significa una infracción: el docente revisará el contexto.'
      }
    default:
      return null
  }
}
