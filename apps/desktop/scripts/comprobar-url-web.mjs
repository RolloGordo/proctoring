import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * Se niega a empaquetar un instalador sin saber a dónde apunta.
 *
 * `apps/desktop/src/main/web.ts` cae a `http://localhost:5173` cuando no hay
 * nada configurado, que en desarrollo es lo correcto y en un `.exe` instalado
 * es una ventana en blanco reintentando contra una máquina donde no hay nada.
 * Ese fue el error que apareció al probar la aplicación en otra computadora.
 *
 * Documentarlo no basta: alguien lo olvidará justo el día de la entrega. Esto
 * lo hace imposible — el empaquetado falla y dice qué poner.
 */

/**
 * Lee `PROCTORING_WEB_URL` del `.env`, si existe.
 *
 * Mismo sitio del que la lee `electron.vite.config.ts`. Si este guardián solo
 * mirara el entorno, rechazaría un `.env` perfectamente válido y mandaría a
 * quien empaqueta a pelearse con la sintaxis de su consola para nada.
 */
function delArchivoEnv() {
  const archivo = resolve(import.meta.dirname, '..', '.env')
  if (!existsSync(archivo)) return undefined

  for (const linea of readFileSync(archivo, 'utf8').split(/\r?\n/u)) {
    const limpia = linea.trim()
    if (!limpia || limpia.startsWith('#')) continue
    const corte = limpia.indexOf('=')
    if (corte === -1) continue
    if (limpia.slice(0, corte).trim() !== 'PROCTORING_WEB_URL') continue
    return limpia
      .slice(corte + 1)
      .trim()
      .replace(/^["']|["']$/gu, '')
  }
  return undefined
}

function rechazar(motivo) {
  console.error(`\n  No se puede empaquetar: ${motivo}\n`)
  console.error('  El instalador lleva dentro la dirección de la web del examen, y se')
  console.error('  congela al construirlo: un .exe ya publicado no la puede cambiar.\n')
  console.error('  Ponla en apps/desktop/.env:\n')
  console.error('    PROCTORING_WEB_URL=https://tu-web.vercel.app\n')
  console.error('  O en la consola, antes de construir. En PowerShell:\n')
  console.error('    $env:PROCTORING_WEB_URL="https://tu-web.vercel.app"\n')
  console.error('  En cmd:\n')
  console.error('    set PROCTORING_WEB_URL=https://tu-web.vercel.app\n')
  process.exit(1)
}

const url = process.env.PROCTORING_WEB_URL || delArchivoEnv()

if (!url || !url.trim()) rechazar('falta PROCTORING_WEB_URL (ni en el entorno ni en .env)')

let destino
try {
  destino = new URL(url)
} catch {
  rechazar(`PROCTORING_WEB_URL no es una dirección válida: ${url}`)
}

if (destino.protocol !== 'https:' && destino.protocol !== 'http:') {
  rechazar(`PROCTORING_WEB_URL tiene que ser http o https, no ${destino.protocol}`)
}

// Un instalador apuntando a localhost es el fallo que esto existe para evitar,
// así que se avisa fuerte pero no se bloquea: construir uno así a propósito,
// para probar en la misma máquina, es legítimo.
if (['localhost', '127.0.0.1', '[::1]'].includes(destino.hostname)) {
  console.warn(`\n  AVISO: se está empaquetando apuntando a ${url}`)
  console.warn('  Ese instalador solo funciona en una máquina que tenga la web local')
  console.warn('  levantada. No lo publiques en el Release.\n')
}

console.log(`  La aplicación se construirá apuntando a ${url}`)
