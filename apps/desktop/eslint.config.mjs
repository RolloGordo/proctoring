import { defineConfig } from 'eslint/config'
import tseslint from '@electron-toolkit/eslint-config-ts'
import eslintConfigPrettier from '@electron-toolkit/eslint-config-prettier'

export default defineConfig(
  { ignores: ['**/node_modules', '**/dist', '**/out'] },
  tseslint.configs.recommended,
  // Los scripts de construccion son JavaScript suelto que corre en Node, no
  // codigo de la aplicacion: pedirles anotaciones de tipo de TypeScript no
  // tiene sentido y no se puede cumplir sin convertirlos a .ts.
  {
    files: ['scripts/**/*.mjs'],
    rules: { '@typescript-eslint/explicit-function-return-type': 'off' }
  },
  eslintConfigPrettier
)
