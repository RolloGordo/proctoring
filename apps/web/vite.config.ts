import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // strictPort: si el 5173 esta ocupado, falla en vez de mudarse al 5174 en
  // silencio. La app de escritorio carga el examen desde el 5173, asi que una
  // mudanza silenciosa se nota mucho mas tarde y en otro sitio.
  server: { port: 5173, strictPort: true },
  // `vitest/config` ya aporta los tipos de `test`, sin necesidad de una
  // referencia triple-slash (que el lint prohibe).
  test: { environment: 'node', include: ['src/**/*.test.ts'] }
})
