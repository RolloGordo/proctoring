import { describe, expect, it } from 'vitest'
import { esMasNueva, hayActualizacion, ultimaVersion } from './actualizaciones'

/** Una respuesta de GitHub simulada; ninguna prueba sale a la red. */
function responde(cuerpo: unknown, ok = true): typeof fetch {
  return (async () =>
    ({ ok, json: async () => cuerpo }) as unknown as Response) as unknown as typeof fetch
}

describe('comparar versiones', () => {
  it('reconoce una posterior', () => {
    expect(esMasNueva('1.1.0', '1.0.0')).toBe(true)
    expect(esMasNueva('1.0.1', '1.0.0')).toBe(true)
    expect(esMasNueva('2.0.0', '1.9.9')).toBe(true)
  })

  it('la misma versión no es más nueva', () => {
    expect(esMasNueva('1.0.0', '1.0.0')).toBe(false)
  })

  it('una anterior no es más nueva', () => {
    expect(esMasNueva('1.0.0', '1.0.1')).toBe(false)
  })

  it('compara números, no texto', () => {
    // Comparando cadenas, "0.10.0" < "0.9.0". Es justo el salto donde se rompe.
    expect(esMasNueva('0.10.0', '0.9.0')).toBe(true)
    expect(esMasNueva('0.9.0', '0.10.0')).toBe(false)
  })

  it('acepta la v de la etiqueta y las versiones cortas', () => {
    expect(esMasNueva('v1.2.0', '1.1.0')).toBe(true)
    expect(esMasNueva('1.1', '1.0.9')).toBe(true)
  })

  it('una versión que no se entiende no avisa', () => {
    // Ante la duda, no molestar: un aviso falso en mitad de un examen es peor
    // que no enterarse de una actualización.
    expect(esMasNueva('no-es-una-version', '1.0.0')).toBe(false)
    expect(esMasNueva('1.0.0', 'tampoco')).toBe(false)
    expect(esMasNueva('', '1.0.0')).toBe(false)
  })
})

describe('consultar la última publicación', () => {
  it('lee la etiqueta y la página', async () => {
    const publicada = await ultimaVersion(
      responde({ tag_name: 'v1.4.0', html_url: 'https://ejemplo/releases/v1.4.0' })
    )

    expect(publicada).toEqual({ version: '1.4.0', url: 'https://ejemplo/releases/v1.4.0' })
  })

  it('sin publicaciones devuelve null en vez de fallar', async () => {
    expect(await ultimaVersion(responde({}, false))).toBeNull()
    expect(await ultimaVersion(responde({ mensaje: 'Not Found' }))).toBeNull()
  })

  it('si GitHub no responde, tampoco falla', async () => {
    // Lo importante: quedarse sin poder abrir la aplicación porque GitHub está
    // caído sería mucho peor que no enterarse de una actualización.
    const rompe = (async () => {
      throw new Error('sin red')
    }) as unknown as typeof fetch

    expect(await ultimaVersion(rompe)).toBeNull()
  })
})

describe('decidir si avisar', () => {
  it('avisa cuando la publicada es posterior', async () => {
    const aviso = await hayActualizacion('1.0.0', responde({ tag_name: 'v1.1.0' }))

    expect(aviso?.version).toBe('1.1.0')
  })

  it('no avisa con la misma versión instalada', async () => {
    expect(await hayActualizacion('1.1.0', responde({ tag_name: 'v1.1.0' }))).toBeNull()
  })

  it('no avisa si la instalada es más nueva que la publicada', async () => {
    // Pasa al probar una compilación local antes de publicarla.
    expect(await hayActualizacion('1.2.0', responde({ tag_name: 'v1.1.0' }))).toBeNull()
  })
})
