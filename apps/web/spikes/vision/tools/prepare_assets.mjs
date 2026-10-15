/** Prepara MediaPipe dentro del mismo origen que el kiosco.
 * No usa CDN en el examen. El build falla si falta el modelo facial.
 */
import { mkdir, copyFile, readdir, readFile, writeFile, stat } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { resolve, join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const from = join(webRoot, 'node_modules/@mediapipe/tasks-vision/wasm')
const to = join(webRoot, 'public/mediapipe/wasm')
const model = join(webRoot, 'public/mediapipe/face_landmarker.task')
const provenance = join(webRoot, 'public/mediapipe/provenance.json')

await mkdir(to, { recursive: true })
const files = (await readdir(from)).filter((name) => /\.(wasm|js)$/.test(name))
if (!files.length) throw new Error('No existen recursos WASM de MediaPipe. Ejecuta npm ci.')
for (const name of files) await copyFile(join(from, name), join(to, name))
const modelFlag = process.argv.indexOf('--model')
if (modelFlag !== -1 && process.argv[modelFlag + 1]) {
  await copyFile(resolve(process.argv[modelFlag + 1]), model)
  console.log('Modelo facial copiado desde la ruta autorizada.')
}
try {
  if ((await stat(model)).size < 10_000) throw new Error('Modelo de tamaño inválido')
} catch {
  throw new Error('Falta public/mediapipe/face_landmarker.task. Consigue el modelo oficial con licencia y usa npm run vision:prepare -- --model RUTA. No publiques el examen sin modelo.')
}
const hash = createHash('sha256').update(await readFile(model)).digest('hex')
await writeFile(provenance, JSON.stringify({
  file: 'face_landmarker.task',
  sha256: hash,
  origin: 'Modelo local aportado por el equipo; verificar origen/licencia antes de desplegar',
  model_usage: 'landmarks, detección de rostros y pose; NO proporciona embeddings de identidad',
  wasm_files: files
}, null, 2) + '\n')
console.log(`MediaPipe listo: ${files.length} recursos, sha256 ${hash}`)
