import { describe, expect, it } from 'vitest'
import { aCsv, nombreSeguro, senalesACsv } from './exportar'
import type { ProctoringEvent } from './api'

describe('exportar a CSV', () => {
  it('usa ; y BOM para que Excel en español lo abra en columnas y con tildes', () => {
    const csv = aCsv(['Señal', 'Nivel'], [['Mirada fuera', 'Alta']])
    expect(csv.startsWith('﻿')).toBe(true)
    expect(csv).toContain('Señal;Nivel\r\nMirada fuera;Alta')
  })

  it('escapa comillas y separadores, y neutraliza fórmulas', () => {
    const csv = aCsv(['a'], [['dijo "hola"; adiós'], ['=HYPERLINK("x")'], ['-2+3']])
    expect(csv).toContain('"dijo ""hola""; adiós"')
    expect(csv).toContain(`"'=HYPERLINK(""x"")"`)
    expect(csv).toContain("'-2+3")
  })

  it('una fila por señal con el estudiante', () => {
    const evento = {
      id: 'e1',
      session_id: 's',
      student_id: 'u1',
      question_id: null,
      event_type: 'focus_lost',
      started_at: '2026-11-14T21:24:50Z',
      duration_ms: 12_500,
      metadata: {},
      evidence_path: null,
      severity: 'medium'
    } as ProctoringEvent
    const csv = senalesACsv([evento], () => ({ nombre: 'Ana', correo: 'ana@upao.edu.pe' }))
    const [, fila] = csv.split('\r\n')
    expect(fila).toContain(';Ana;ana@upao.edu.pe;')
    expect(fila).toContain(';12,5;')
    expect(fila.endsWith(';No')).toBe(true)
  })

  it('nombres de archivo sin tildes ni espacios', () => {
    expect(nombreSeguro('Señales', 'Examen Parcial Nº1')).toBe('senales-examen-parcial-n-1.csv')
  })
})
