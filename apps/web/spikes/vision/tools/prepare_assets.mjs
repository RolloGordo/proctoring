import { mkdir, copyFile, readdir } from 'node:fs/promises'
import { resolve, join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const from = join(webRoot, 'node_modules/@mediapipe/tasks-vision/wasm')
const to = join(webRoot, 'public/mediapipe/wasm')
await mkdir(to, { recursive: true })
const files = (await readdir(from)).filter(name => /\.(wasm|js)$/.test(name))
for (const name of files) await copyFile(join(from, name), join(to, name))
const modelFlag = process.argv.indexOf('--model')
if (modelFlag !== -1 && process.argv[modelFlag + 1]) {
  await copyFile(resolve(process.argv[modelFlag + 1]), join(webRoot, 'public/mediapipe/face_landmarker.task'))
  console.log('Modelo copiado solo en disco local; no debe versionarse')
}
console.log(`${files.length} assets WASM/Javascript copiados al origen local`)
