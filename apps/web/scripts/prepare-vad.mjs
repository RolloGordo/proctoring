import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const output = resolve(root, 'public/vad')
await mkdir(output, { recursive: true })
const files = [
  ['@ricky0123/vad-web', 'vad.worklet.bundle.min.js'],
  ['@ricky0123/vad-web', 'silero_vad_v5.onnx'],
  ['onnxruntime-web', 'ort-wasm-simd-threaded.mjs'],
  ['onnxruntime-web', 'ort-wasm-simd-threaded.wasm']
]
const hashes = []
for (const [pkg, name] of files) {
  const source = resolve(root, 'node_modules', pkg, 'dist', name)
  await copyFile(source, resolve(output, name))
  hashes.push({
    package: pkg,
    file: name,
    sha256: createHash('sha256')
      .update(await readFile(source))
      .digest('hex')
  })
}
await writeFile(resolve(output, 'provenance.json'), JSON.stringify(hashes, null, 2))
console.log('VAD assets prepared locally; no CDN requests during an exam.')
