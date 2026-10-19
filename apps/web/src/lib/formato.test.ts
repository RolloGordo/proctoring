import { describe, expect, it } from 'vitest'
import { cuandoEmpieza, detalleEvento, estadoExamen } from './formato'
import { inicioSegunRol } from './rutas'

const INICIO = '2026-10-05T15:00:00.000Z'
const T = new Date(INICIO).getTime()
const MIN = 60_000

describe('estadoExamen', () => {
  it('antes de la hora de inicio está programado', () => {
    expect(estadoExamen(INICIO, 60, T - MIN)).toBe('programado')
  })

  it('justo al empezar ya está en curso', () => {
    expect(estadoExamen(INICIO, 60, T)).toBe('en_curso')
  })

  it('durante la ventana está en curso, y el último minuto todavía cuenta', () => {
    expect(estadoExamen(INICIO, 60, T + 30 * MIN)).toBe('en_curso')
    expect(estadoExamen(INICIO, 60, T + 60 * MIN)).toBe('en_curso')
  })

  it('pasada la duración está terminado', () => {
    // Era el bug: un examen de ayer seguia diciendo "Programado".
    expect(estadoExamen(INICIO, 60, T + 61 * MIN)).toBe('terminado')
    expect(estadoExamen(INICIO, 60, T + 24 * 60 * MIN)).toBe('terminado')
  })
})

describe('cuandoEmpieza', () => {
  it('habla en minutos, horas y días con su plural', () => {
    expect(cuandoEmpieza(1 * MIN)).toBe('en 1 minuto')
    expect(cuandoEmpieza(5 * MIN)).toBe('en 5 minutos')
    expect(cuandoEmpieza(60 * MIN)).toBe('en 1 hora')
    expect(cuandoEmpieza(3 * 60 * MIN)).toBe('en 3 horas')
    expect(cuandoEmpieza(24 * 60 * MIN)).toBe('en 1 día')
    expect(cuandoEmpieza(48 * 60 * MIN)).toBe('en 2 días')
  })

  it('redondea hacia arriba y nunca dice cero minutos', () => {
    expect(cuandoEmpieza(10_000)).toBe('en 1 minuto')
    expect(cuandoEmpieza(0)).toBe('en 1 minuto')
  })
})

describe('detalleEvento', () => {
  it('explica cuando una señal se guardo sin su captura', () => {
    expect(detalleEvento({ capture_error: 'capture_timeout' })).toBe('La captura tardó demasiado.')
    expect(detalleEvento({ capture_error: 'upload_failed' })).toBe('No se pudo subir la captura.')
    expect(detalleEvento({ capture_error: 'no_jpeg' })).toBe('La cámara no produjo una imagen.')
  })

  it('no revela valores tecnicos desconocidos', () => {
    expect(detalleEvento({ capture_error: 'unexpected' })).toBe('La captura no está disponible.')
  })
})

describe('inicioSegunRol', () => {
  it('lleva a cada rol a su panel', () => {
    expect(inicioSegunRol('teacher')).toBe('/docente')
    expect(inicioSegunRol('student')).toBe('/estudiante')
  })

  it('sin rol vuelve a la portada y no adivina un panel', () => {
    expect(inicioSegunRol(undefined)).toBe('/')
  })
})
