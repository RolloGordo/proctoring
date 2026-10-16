import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  avisoCamara,
  avisoParaEvento,
  DURACION_AVISO_MS,
  GestorDeAvisos,
  SILENCIO_MISMA_SENAL_MS,
  VENTANA_SIMULTANEIDAD_MS,
  type AvisoVisible
} from './avisos'

describe('qué se le dice al estudiante', () => {
  it('hablar en voz alta no se presenta como una infracción', () => {
    // Es la promesa del proyecto: leer la pregunta para concentrarse es
    // legítimo, y el texto que el estudiante lee tiene que decirlo.
    const aviso = avisoParaEvento('speech_detected')

    expect(aviso?.detalle).toContain('no significa una infracción')
  })

  it.each(['gaze_away', 'face_absent', 'extra_person', 'speech_detected'] as const)(
    '%s se explica sin acusar',
    (evento) => {
      const aviso = avisoParaEvento(evento)

      expect(aviso).not.toBeNull()
      expect(aviso!.detalle.toLowerCase()).not.toMatch(/copiando|trampa|infracción detectada/)
    }
  )

  it('un evento que no se le muestra al estudiante no inventa texto', () => {
    expect(avisoParaEvento('focus_lost')).toBeNull()
  })
})

describe('cuándo se le dice', () => {
  let visto: AvisoVisible | null
  let gestor: GestorDeAvisos

  beforeEach(() => {
    vi.useFakeTimers()
    visto = null
    gestor = new GestorDeAvisos()
    gestor.suscribir((a) => (visto = a))
  })

  it('la primera señal se ve', () => {
    gestor.registrar('gaze_away', 0)

    expect(visto?.titulo).toBe('Orientación de cabeza fuera de pantalla')
  })

  it('la misma señal repetida no vuelve a avisar en seguida', () => {
    // Mirar a un lado medio minuto cierra varios episodios seguidos. Sin esto,
    // el estudiante recibe un aviso detrás de otro y deja de leerlos.
    gestor.registrar('gaze_away', 0)
    const segunda = gestor.registrar('gaze_away', SILENCIO_MISMA_SENAL_MS - 1)

    expect(segunda).toBe(false)
  })

  it('pasado el silencio, vuelve a avisar', () => {
    gestor.registrar('gaze_away', 0)

    expect(gestor.registrar('gaze_away', SILENCIO_MISMA_SENAL_MS + 1)).toBe(true)
  })

  it('dos señales a la vez son un aviso, no dos', () => {
    // Si la cámara y el micrófono saltan juntos es un suceso. Dos cajas
    // encima del enunciado es exactamente lo que no se quiere.
    gestor.registrar('gaze_away', 0)
    gestor.registrar('speech_detected', VENTANA_SIMULTANEIDAD_MS - 1)

    expect(visto?.eventos).toEqual(['gaze_away', 'speech_detected'])
    expect(visto?.titulo).toBe('Se detectaron varias señales')
  })

  it('señales separadas no se juntan', () => {
    gestor.registrar('gaze_away', 0)
    gestor.registrar('speech_detected', VENTANA_SIMULTANEIDAD_MS + 1000)

    expect(visto?.eventos).toEqual(['speech_detected'])
  })

  it('el aviso se retira solo', () => {
    // Nadie tiene que cerrar una caja para poder seguir respondiendo.
    gestor.registrar('extra_person', 0)
    expect(visto).not.toBeNull()

    vi.advanceTimersByTime(DURACION_AVISO_MS + 10)

    expect(visto).toBeNull()
  })

  it('se puede descartar antes de tiempo', () => {
    gestor.registrar('extra_person', 0)

    gestor.descartar()

    expect(visto).toBeNull()
  })

  it('un problema de cámara también llega al estudiante', () => {
    // No es un `EventType`, asi que pasarlo por su tipo lo dejaba caer en
    // `avisoParaEvento` y el estudiante no veia nada: compilaba y no hacia
    // nada. El gestor acepta el aviso ya construido.
    gestor.registrar(avisoCamara('interrupted'), 0)

    expect(visto?.titulo).toBe('Se perdió la conexión con la cámara')
  })

  it('el aviso de cámara no acusa de nada', () => {
    // Quedarse sin camara por un cable suelto no es una infraccion, y el texto
    // que lee el estudiante tiene que decirlo.
    expect(avisoCamara('no_image').detalle).toContain('No implica una infracción')
    expect(avisoCamara('interrupted').detalle).toContain('El examen continúa')
  })

  it('un problema de cámara se combina con una señal sin perder su título', () => {
    // La combinación resolvía los títulos otra vez a partir del tipo, y los de
    // cámara no tienen `EventType`: al juntarse con otra señal desaparecían.
    gestor.registrar('gaze_away', 0)
    gestor.registrar(avisoCamara('interrupted'), 1_000)

    expect(visto?.titulo).toBe('Se detectaron varias señales')
    expect(visto?.detalle).toContain('Orientación de cabeza fuera de pantalla')
    expect(visto?.detalle).toContain('Se perdió la conexión con la cámara')
  })

  it('el mismo problema de cámara no repite el aviso en seguida', () => {
    gestor.registrar(avisoCamara('interrupted'), 0)

    expect(gestor.registrar(avisoCamara('interrupted'), 1_000)).toBe(false)
  })

  it('al destruirlo no quedan temporizadores sueltos', () => {
    gestor.registrar('face_absent', 0)

    gestor.destruir()
    vi.advanceTimersByTime(DURACION_AVISO_MS * 3)

    expect(vi.getTimerCount()).toBe(0)
  })
})
