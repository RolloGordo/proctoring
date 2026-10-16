import { defineConfig } from 'electron-vite'

export default defineConfig({
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
      __PROCTORING_WEB_URL__: JSON.stringify(process.env.PROCTORING_WEB_URL ?? '')
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
})
