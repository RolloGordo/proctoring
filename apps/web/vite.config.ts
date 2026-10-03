import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  // `vitest/config` ya aporta los tipos de `test`, sin necesidad de una
  // referencia triple-slash (que el lint prohibe).
  test: { environment: 'node', include: ['src/**/*.test.ts'] }
})
