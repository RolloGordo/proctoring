import { mkdir, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { deflateSync } from 'node:zlib'
import { dirname, resolve } from 'node:path'

/**
 * Dibuja los iconos PNG a partir de la misma forma que `public/icono.svg`.
 *
 * Los navegadores modernos usan el SVG. El PNG hace falta para los que no lo
 * aceptan y para la pantalla de inicio de iOS, que ignora el SVG.
 *
 * Se dibujan aquí en vez de convertir el SVG con una herramienta externa para
 * no añadir una dependencia de compilación por dos imágenes de 32 KB. Si algún
 * día cambia el icono, se cambian los dos: la forma vive en `FORMA`.
 */

const TINTA = [0x21, 0x25, 0x29]
const AMBAR = [0xe8, 0xa7, 0x00]
const BLANCO = [0xff, 0xff, 0xff]

/** En la rejilla de 32x32 del SVG: [x, y, ancho, alto, color, opacidad]. */
const FORMA = [
  [7, 9, 4, 2.5, BLANCO, 0.45],
  [13, 9, 12, 2.5, BLANCO, 0.45],
  [7, 15, 4, 2.5, AMBAR, 1],
  [13, 15, 12, 2.5, AMBAR, 1],
  [7, 21, 4, 2.5, BLANCO, 0.45],
  [13, 21, 9, 2.5, BLANCO, 0.45]
]

const LADO_SVG = 32
const RADIO_SVG = 7

/** Cobertura de un píxel por un rectángulo, muestreando 4x4 dentro de él. */
function cobertura(px, py, escala, [x, y, ancho, alto], radio = 0) {
  const muestras = 4
  let dentro = 0
  for (let sy = 0; sy < muestras; sy += 1) {
    for (let sx = 0; sx < muestras; sx += 1) {
      const u = (px + (sx + 0.5) / muestras) / escala
      const v = (py + (sy + 0.5) / muestras) / escala
      if (u < x || u >= x + ancho || v < y || v >= y + alto) continue
      if (radio > 0 && !dentroDelRedondeo(u - x, v - y, ancho, alto, radio)) continue
      dentro += 1
    }
  }
  return dentro / (muestras * muestras)
}

function dentroDelRedondeo(u, v, ancho, alto, radio) {
  const cx = Math.min(Math.max(u, radio), ancho - radio)
  const cy = Math.min(Math.max(v, radio), alto - radio)
  return (u - cx) ** 2 + (v - cy) ** 2 <= radio ** 2
}

function mezclar(fondo, color, alfa) {
  return fondo.map((canal, i) => Math.round(canal * (1 - alfa) + color[i] * alfa))
}

function dibujar(lado) {
  const escala = lado / LADO_SVG
  const pixeles = Buffer.alloc(lado * lado * 4)
  for (let y = 0; y < lado; y += 1) {
    for (let x = 0; x < lado; x += 1) {
      const fondo = cobertura(x, y, escala, [0, 0, LADO_SVG, LADO_SVG], RADIO_SVG)
      let color = TINTA
      for (const [rx, ry, ancho, alto, tono, opacidad] of FORMA) {
        const c = cobertura(x, y, escala, [rx, ry, ancho, alto], alto / 2)
        if (c > 0) color = mezclar(color, tono, c * opacidad)
      }
      const i = (y * lado + x) * 4
      pixeles[i] = color[0]
      pixeles[i + 1] = color[1]
      pixeles[i + 2] = color[2]
      pixeles[i + 3] = Math.round(fondo * 255)
    }
  }
  return pixeles
}

// --- PNG a mano: cabecera, datos e IEND. Sin dependencias. -------------------

function trozo(tipo, datos) {
  const largo = Buffer.alloc(4)
  largo.writeUInt32BE(datos.length)
  const cuerpo = Buffer.concat([Buffer.from(tipo, 'ascii'), datos])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(cuerpo))
  return Buffer.concat([largo, cuerpo, crc])
}

const TABLA = (() => {
  const tabla = new Int32Array(256)
  for (let n = 0; n < 256; n += 1) {
    let c = n
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    tabla[n] = c
  }
  return tabla
})()

function crc32(buffer) {
  let c = 0xffffffff
  for (const byte of buffer) c = TABLA[(c ^ byte) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function png(lado, pixeles) {
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(lado, 0)
  ihdr.writeUInt32BE(lado, 4)
  ihdr[8] = 8 // bits por canal
  ihdr[9] = 6 // RGBA
  const filas = []
  for (let y = 0; y < lado; y += 1) {
    filas.push(Buffer.from([0])) // filtro "ninguno"
    filas.push(pixeles.subarray(y * lado * 4, (y + 1) * lado * 4))
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    trozo('IHDR', ihdr),
    trozo('IDAT', deflateSync(Buffer.concat(filas), { level: 9 })),
    trozo('IEND', Buffer.alloc(0))
  ])
}

const destino = resolve(import.meta.dirname, '..', 'public')
await mkdir(dirname(destino), { recursive: true })
for (const lado of [32, 180, 192, 512]) {
  const archivo = resolve(destino, `icono-${lado}.png`)
  const datos = png(lado, dibujar(lado))
  await writeFile(archivo, datos)
  const firma = createHash('sha256').update(datos).digest('hex').slice(0, 8)
  console.log(`  icono-${lado}.png  ${(datos.length / 1024).toFixed(1)} KB  ${firma}`)
}
