import { describe, expect, it } from 'vitest'
import type { SupervisionModule } from './api'
import {
  MODULOS,
  MODULOS_DE_PRESET,
  agrupar,
  alternarModulo,
  comoModulosElegidos,
  dispositivosQueUsa,
  modulosVigilados
} from './modulos'

describe('catálogo de módulos', () => {
  it('nombra los doce módulos del contrato, una vez cada uno', () => {
    const ids = MODULOS.map((m) => m.id)
    expect(new Set(ids).size).toBe(12)
    expect(ids).toHaveLength(12)
  })

  it('la estricta los activa todos', () => {
    expect(new Set(MODULOS_DE_PRESET.strict)).toEqual(new Set(MODULOS.map((m) => m.id)))
  })
})

describe('alternarModulo', () => {
  it('marcar la reverificación marca la verificación', () => {
    const elegidos = alternarModulo(new Set(), 'face_reverification', true)
    expect(elegidos).toEqual(new Set(['face_reverification', 'face_verification']))
  })

  it('quitar la verificación quita la reverificación', () => {
    const elegidos = alternarModulo(
      new Set<SupervisionModule>(['face_verification', 'face_reverification', 'gaze']),
      'face_verification',
      false
    )
    expect(elegidos).toEqual(new Set(['gaze']))
  })

  it('no toca el conjunto que recibe', () => {
    const antes = new Set<SupervisionModule>(['gaze'])
    alternarModulo(antes, 'objects', true)
    expect(antes).toEqual(new Set(['gaze']))
  })
})

describe('dispositivosQueUsa', () => {
  it('solo el equipo: ni cámara ni micrófono', () => {
    expect(dispositivosQueUsa(['focus_loss', 'multi_monitor'])).toEqual({
      camara: false,
      microfono: false
    })
  })

  it('la verificación de identidad también pide la cámara', () => {
    expect(dispositivosQueUsa(['face_verification']).camara).toBe(true)
  })

  it('las voces piden el micrófono', () => {
    expect(dispositivosQueUsa(['ai_voice'])).toEqual({ camara: false, microfono: true })
  })
})

describe('modulosVigilados', () => {
  it('usa watched_modules cuando la API lo manda', () => {
    expect(
      modulosVigilados({
        modules: { face_verification: {} },
        watched_modules: ['screen_capture', 'face_verification', 'focus_loss']
      })
    ).toEqual(['face_verification', 'focus_loss', 'screen_capture'])
  })

  it('con una API anterior, cae en las claves de modules', () => {
    expect(modulosVigilados({ modules: { gaze: {}, focus_loss: {} } })).toEqual([
      'gaze',
      'focus_loss'
    ])
  })

  it('ignora lo que no conoce', () => {
    expect(modulosVigilados({ modules: { algo_nuevo: {} } })).toEqual([])
  })
})

describe('agrupar', () => {
  it('agrupa por dispositivo y omite los grupos vacíos', () => {
    const grupos = agrupar(['ai_voice', 'focus_loss', 'gaze'])
    expect(grupos.map((g) => g.grupo.id)).toEqual(['camara', 'microfono', 'equipo'])
    expect(grupos[0].modulos.map((m) => m.id)).toEqual(['gaze'])
  })
})

it('comoModulosElegidos manda cada módulo vacío', () => {
  expect(comoModulosElegidos(['gaze', 'objects'])).toEqual({ gaze: {}, objects: {} })
})
