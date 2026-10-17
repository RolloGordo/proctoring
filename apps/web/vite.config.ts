import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig, type Plugin } from 'vitest/config'
import react from '@vitejs/plugin-react'

/**
 * Sirve los artefactos del VAD desde `public/vad/` tal cual, en desarrollo.
 *
 * onnxruntime-web importa su `.mjs` en tiempo de ejecucion, y el servidor de
 * desarrollo intenta transformarlo como si fuera codigo fuente nuestro: «This
 * file is in /public and will be copied as-is during build... and therefore
 * should not be imported from source code». En produccion no hace falta,
 * porque ahi los ficheros de `public/` ya se sirven estaticos.
 */
function vadEstatico(): Plugin {
  return {
    name: 'vad-static-middleware',
    configureServer(server) {
      const tipos: Record<string, string> = {
        '.mjs': 'text/javascript',
        '.js': 'text/javascript',
        '.wasm': 'application/wasm',
        '.onnx': 'application/octet-stream'
      }
      server.middlewares.use((req, res, siguiente) => {
        const ruta = req.url ? req.url.split('?')[0] : ''
        if (!ruta.startsWith('/vad/')) return siguiente()
        const fichero = resolve(process.cwd(), 'public', ruta.slice(1))
        if (!existsSync(fichero)) return siguiente()
        const extension = Object.keys(tipos).find((e) => ruta.endsWith(e))
        if (extension) res.setHeader('Content-Type', tipos[extension])
        res.end(readFileSync(fichero))
      })
    }
  }
}

export default defineConfig({
  plugins: [react(), vadEstatico()],
  // strictPort: si el 5173 esta ocupado, falla en vez de mudarse al 5174 en
  // silencio. La app de escritorio carga el examen desde el 5173, asi que una
  // mudanza silenciosa se nota mucho mas tarde y en otro sitio.
  server: {
    port: 5173,
    strictPort: true,
    // Habilitan `SharedArrayBuffer`, que es lo que deja a onnxruntime-web
    // correr el wasm con varios hilos.
    //
    // OJO, y esto hay que resolverlo antes de desplegar: **solo valen aqui**.
    // En Vercel no estan, asi que el VAD correra con un solo hilo y mas lento
    // que en desarrollo. Cualquier latencia medida en local es optimista.
    // Ponerlas tambien en produccion no es gratis: con COEP, los recursos de
    // otro origen que no declaren CORP dejan de cargar, y las capturas de
    // evidencia vienen de Supabase Storage.
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'credentialless'
    }
  },
  // `vitest/config` ya aporta los tipos de `test`, sin necesidad de una
  // referencia triple-slash (que el lint prohibe).
  test: { environment: 'node', include: ['src/**/*.test.ts'] }
})
