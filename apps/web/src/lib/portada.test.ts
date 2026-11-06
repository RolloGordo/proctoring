import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, type Course } from './api'
import { MAX_ORIGINAL_BYTES, subirPortada, validarArchivoPortada } from './portada'

function archivo(tipo: string, bytes = 10): File {
  return new File([new Uint8Array(bytes)], 'portada', { type: tipo })
}

const CURSO: Course = {
  id: 'curso-uno',
  name: 'Taller',
  section: null,
  created_at: '2026-11-06T00:00:00Z',
  student_count: 0,
  cover_url: 'https://storage.example.com/firmada'
}

afterEach(() => vi.restoreAllMocks())

describe('validarArchivoPortada', () => {
  it.each(['image/jpeg', 'image/png', 'image/webp'])('acepta %s', (tipo) => {
    expect(() => validarArchivoPortada(archivo(tipo))).not.toThrow()
  })

  it.each(['image/gif', 'image/svg+xml', 'application/pdf', ''])('rechaza %s', (tipo) => {
    expect(() => validarArchivoPortada(archivo(tipo))).toThrow('JPG, PNG o WebP')
  })

  it('rechaza un archivo de más de 15 MB', () => {
    expect(() => validarArchivoPortada(archivo('image/jpeg', MAX_ORIGINAL_BYTES + 1))).toThrow(
      '15 MB'
    )
  })
})

describe('subirPortada', () => {
  it('pide la firma, sube con PUT y fija la ruta', async () => {
    const firma = vi.spyOn(api, 'courseCoverUpload').mockResolvedValue({
      path: 'curso-uno/abc.webp',
      url: 'https://storage.example.com/upload',
      token: 'firmado',
      expires_in_seconds: 7200
    })
    const fijar = vi.spyOn(api, 'setCourseCover').mockResolvedValue(CURSO)
    const subida = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(null, { status: 200 }))

    const curso = await subirPortada('curso-uno', new Blob(['x'], { type: 'image/webp' }), 'jwt')

    expect(firma).toHaveBeenCalledWith('curso-uno', 'image/webp', 'jwt')
    const [url, opciones] = subida.mock.calls[0]
    expect(url).toBe('https://storage.example.com/upload?token=firmado')
    expect(opciones?.method).toBe('PUT')
    expect(fijar).toHaveBeenCalledWith('curso-uno', 'curso-uno/abc.webp', 'jwt')
    expect(curso).toBe(CURSO)
  })

  it('si Storage rechaza la imagen, el curso no apunta a ella', async () => {
    vi.spyOn(api, 'courseCoverUpload').mockResolvedValue({
      path: 'curso-uno/abc.webp',
      url: 'https://storage.example.com/upload',
      token: null,
      expires_in_seconds: 7200
    })
    const fijar = vi.spyOn(api, 'setCourseCover')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 413 }))

    await expect(
      subirPortada('curso-uno', new Blob(['x'], { type: 'image/webp' }))
    ).rejects.toThrow('HTTP 413')
    expect(fijar).not.toHaveBeenCalled()
  })

  it('no sube algo que no sea una imagen admitida', async () => {
    const firma = vi.spyOn(api, 'courseCoverUpload')

    await expect(
      subirPortada('curso-uno', new Blob(['x'], { type: 'image/gif' }))
    ).rejects.toThrow()
    expect(firma).not.toHaveBeenCalled()
  })
})
