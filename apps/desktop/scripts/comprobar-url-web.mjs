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

const url = process.env.PROCTORING_WEB_URL

function rechazar(motivo) {
  console.error(`\n  No se puede empaquetar: ${motivo}\n`)
  console.error('  El instalador lleva dentro la dirección de la web del examen, y se')
  console.error('  congela al construirlo: un .exe ya publicado no la puede cambiar.\n')
  console.error('  Construye así, con la web ya desplegada:\n')
  console.error('    PROCTORING_WEB_URL=https://tu-web.vercel.app npm run build:win\n')
  console.error('  En PowerShell:\n')
  console.error('    $env:PROCTORING_WEB_URL="https://tu-web.vercel.app"; npm run build:win\n')
  process.exit(1)
}

if (!url || !url.trim()) rechazar('falta PROCTORING_WEB_URL')

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
