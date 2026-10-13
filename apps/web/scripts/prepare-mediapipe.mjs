/**
 * Deja los assets de MediaPipe en `public/mediapipe/`, igual que
 * `prepare-vad.mjs` hace con el VAD.
 *
 * Por qué existe: `vision.ts` pide `/mediapipe/wasm` y
 * `/mediapipe/face_landmarker.task` en tiempo de ejecución. Esa carpeta está en
 * `.gitignore`, así que en un despliegue esos archivos **no existirían** y la
 * petición daría 404. Y como `useSupervision` descarta un detector que no carga
 * y deja seguir el examen, la detección de visión se apagaría **sin un solo
 * error visible**. Un fallo silencioso en producción es peor que uno ruidoso.
 *
 * Los `.wasm` salen de `node_modules`, fijados por el `package-lock`: si el
 * paquete está, los archivos están. No puede desfasarse, y no cuesta 34 MB en
 * el repositorio.
 *
 * El modelo `face_landmarker.task` **no viene en el paquete npm**, así que ese
 * sí tiene que estar versionado. Si falta, esto avisa y falla: antes el examen
 * arrancaba sin visión y nadie se enteraba.
 */
import { copyFile, mkdir, readdir, readFile, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const paquete = resolve(root, 'node_modules/@mediapipe/tasks-vision')
const salida = resolve(root, 'public/mediapipe')
const modelo = resolve(salida, 'face_landmarker.task')

await mkdir(resolve(salida, 'wasm'), { recursive: true })

const origen = resolve(paquete, 'wasm')
const nombres = (await readdir(origen)).filter((n) => /\.(wasm|js)$/.test(n))
if (nombres.length === 0) {
  throw new Error(
    'No hay assets WASM en @mediapipe/tasks-vision. ¿Se corrió npm install?'
  )
}

const procedencia = []
for (const nombre of nombres) {
  const fuente = resolve(origen, nombre)
  await copyFile(fuente, resolve(salida, 'wasm', nombre))
  procedencia.push({
    package: '@mediapipe/tasks-vision',
    file: `wasm/${nombre}`,
    sha256: createHash('sha256')
      .update(await readFile(fuente))
      .digest('hex')
  })
}

// El modelo va versionado porque no está en npm. Si alguien lo borra, que se
// entere aquí y no en mitad de un examen.
try {
  procedencia.push({
    package: 'google/mediapipe-models (Apache-2.0)',
    file: 'face_landmarker.task',
    sha256: createHash('sha256')
      .update(await readFile(modelo))
      .digest('hex')
  })
} catch {
  console.error(
    '\nFALTA public/mediapipe/face_landmarker.task.\n' +
      'Sin el modelo no hay deteccion de rostro, mirada ni persona adicional, y\n' +
      'el examen correria sin avisar de nada. Esta versionado en el repositorio:\n' +
      'comprueba que el checkout esta completo antes de desplegar.\n'
  )
  process.exitCode = 1
}

await writeFile(resolve(salida, 'provenance.json'), JSON.stringify(procedencia, null, 2))
console.log(`MediaPipe: ${nombres.length} assets preparados en local; sin CDN durante un examen.`)
