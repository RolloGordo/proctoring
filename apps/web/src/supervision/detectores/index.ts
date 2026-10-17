/**
 * Arma la lista de detectores según lo que el docente activó en la sesión.
 *
 * Cada módulo de `session_modules` se traduce a un detector con **sus** ajustes.
 * Un módulo que no está activo no corre: un examen con supervisión básica no
 * tiene por qué encender la cámara.
 */

import type { Detector } from '../tipos'
import {
  DetectorMirada,
  DetectorPersonaExtra,
  DetectorRostroAusente,
  type AjustesMirada,
  type AjustesPersonaExtra,
  type AjustesRostro
} from './vision'
import { DetectorHabla, type AjustesVoz } from './voz'

/** Módulos de `SupervisionModule` que corren en el navegador. */
const CONSTRUCTORES: Record<string, (ajustes: Record<string, unknown>) => Detector> = {
  gaze: (a) => new DetectorMirada(a as AjustesMirada),
  // El contrato no tiene un módulo propio para el rostro ausente: va con la
  // mirada, porque lo detecta el mismo modelo sobre el mismo fotograma.
  face_absent: (a) => new DetectorRostroAusente(a as AjustesRostro),
  extra_person: (a) => new DetectorPersonaExtra(a as AjustesPersonaExtra),
  ai_voice: (a) => new DetectorHabla(a as AjustesVoz),
  external_voices: (a) => new DetectorHabla(a as AjustesVoz)
}

export function detectoresDe(modulos: Record<string, Record<string, unknown>>): Detector[] {
  const detectores: Detector[] = []
  const yaPuestos = new Set<string>()
  for (const [modulo, ajustes] of Object.entries(modulos)) {
    // `face_absent` no es un módulo elegible en el contrato, sino parte de gaze.
    if (modulo === 'gaze' && !yaPuestos.has('rostro-ausente')) {
      const ausente = new DetectorRostroAusente(ajustes as AjustesRostro)
      yaPuestos.add(ausente.nombre)
      detectores.push(ausente)
    }
    const construir = CONSTRUCTORES[modulo]
    if (!construir) continue
    const detector = construir(ajustes ?? {})
    // `ai_voice` y `external_voices` comparten detector: no se enciende dos veces.
    if (yaPuestos.has(detector.nombre)) continue
    yaPuestos.add(detector.nombre)
    detectores.push(detector)
  }
  return detectores
}

/** Si alguno de los detectores necesita el micrófono. */
export function necesitaAudio(detectores: Detector[]): boolean {
  return detectores.some((d) => d.evento === 'speech_detected')
}

export * from './vision'
export * from './voz'
