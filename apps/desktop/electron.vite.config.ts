import { defineConfig } from 'electron-vite'

export default defineConfig({
  main: {},
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
