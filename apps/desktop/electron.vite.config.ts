import { defineConfig, loadEnv } from 'electron-vite'

/**
 * De donde sale la direccion de la web, al construir.
 *
 * Dos sitios, y el `.env` existe por una razon concreta: la variable de entorno
 * se escribe distinto en cada consola de Windows —`$env:X="..."` en PowerShell,
 * `set X=...` en cmd— y usar la sintaxis de una en la otra no da ningun error:
 * simplemente no se define nada, la aplicacion cae a localhost y lo unico que
 * se ve es un ERR_CONNECTION_REFUSED que no explica la causa.
 *
 * Con `apps/desktop/.env` se pone una vez y deja de depender de la consola.
 * El archivo esta en `.gitignore` y `electron-builder.yml` lo excluye del
 * paquete, asi que no viaja a ninguna parte.
 */
function urlDeLaWeb(mode: string): string {
  // Sin prefijo: `loadEnv` filtra por `VITE_` si no se le dice otra cosa.
  const delArchivo = loadEnv(mode, __dirname, '')['PROCTORING_WEB_URL']
  return (process.env.PROCTORING_WEB_URL ?? delArchivo ?? '').trim()
}

export default defineConfig(({ mode }) => ({
  main: {
    // La direccion de la web viaja **dentro** del binario.
    //
    // Antes se leia de `process.env` en tiempo de ejecucion, y en un `.exe`
    // instalado esa variable no existe: la aplicacion caia a localhost y se
    // quedaba reintentando contra una maquina donde no hay nada. El `.env`
    // tampoco sirve, porque `electron-builder.yml` lo excluye del paquete a
    // proposito.
    //
    // Cadena vacia cuando no se define: `web.ts` decide que hacer con eso, y
    // `scripts/comprobar-url-web.mjs` impide empaquetar sin ella.
    define: {
      __PROCTORING_WEB_URL__: JSON.stringify(urlDeLaWeb(mode))
    }
  },
  preload: {},
  renderer: {
    // Este servidor NO sirve el examen: sirve el panel local de eventos, que
    // es la herramienta de diagnostico del proceso principal. El examen lo
    // sirve `apps/web` en el 5173. Puerto propio para que los dos no compitan
    // y para que el mensaje "Port 5173 is in use" deje de aparecer aqui.
    //
    // Sin strictPort a proposito: nada depende de este puerto, y si queda una
    // instancia anterior viva, que se mude es mejor que no poder arrancar.
    server: { port: 5180 }
  }
}))
