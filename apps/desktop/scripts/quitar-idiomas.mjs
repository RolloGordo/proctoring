import { readdir, rm, stat } from 'node:fs/promises'
import { join } from 'node:path'

/**
 * Quita de la carpeta `locales` los idiomas que esta aplicación no habla.
 *
 * Electron empaqueta los 55 idiomas de Chromium: **50,6 MB en disco y 9 MB ya
 * comprimidos dentro del instalador**, medidos el 28/10 sobre la versión 1.1.0.
 * La interfaz de este proyecto está en español y no hay forma de cambiarla, así
 * que los otros 52 son peso que nadie va a usar nunca.
 *
 * Se hace aquí y no con `electronLanguages` porque esa opción de
 * electron-builder recorta los idiomas en macOS y Linux, pero no en Windows,
 * que es donde se instala esto.
 *
 * `en-US.pak` se queda aunque no se use: Chromium lo trata como el idioma de
 * respaldo y arrancar sin él no es algo que convenga descubrir en el equipo de
 * un estudiante a mitad de un examen.
 */
const QUE_SE_QUEDAN = new Set(['es.pak', 'es-419.pak', 'en-US.pak'])

export default async function quitarIdiomas(contexto) {
  const carpeta = join(contexto.appOutDir, 'locales')

  let archivos
  try {
    archivos = await readdir(carpeta)
  } catch {
    // En macOS los idiomas viven dentro del .app, no en `locales`. Que no
    // exista no es un fallo: es otra plataforma.
    return
  }

  let quitados = 0
  let bytes = 0
  for (const archivo of archivos) {
    if (!archivo.endsWith('.pak') || QUE_SE_QUEDAN.has(archivo)) continue
    const ruta = join(carpeta, archivo)
    bytes += (await stat(ruta)).size
    await rm(ruta)
    quitados += 1
  }

  console.log(
    `  idiomas: se quitaron ${quitados} (${(bytes / 1e6).toFixed(1)} MB sin comprimir); ` +
      `se quedan ${[...QUE_SE_QUEDAN].join(', ')}`
  )
}
