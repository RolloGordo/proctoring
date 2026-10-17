# Por qué existe `vercel.json`

La web es una SPA: el enrutado lo hace React en el navegador, no el servidor.
Sin una reescritura, pedirle a Vercel `/estudiante/cursos/abc` le hace buscar un
archivo con ese nombre, no lo encuentra y responde **404**.

No pasa navegando dentro de la aplicación —ahí no hay petición al servidor—,
así que es un fallo que no aparece hasta que alguien:

- recarga la página, que es lo primero que hace un estudiante si algo se traba
  **en mitad de un examen**;
- abre un enlace directo, como el de la sala de espera que le pasa su docente;
- vuelve con el botón de atrás después de un rato.

La reescritura manda todo a `index.html` y deja que React resuelva la ruta. Los
archivos estáticos no se ven afectados: Vercel los sirve primero y solo reescribe
lo que no existe en disco, así que `/vad/`, `/mediapipe/` y `/portada/` siguen
llegando tal cual.

Puede que Vercel aplique esta reescritura sola al detectar Vite. Dejarlo escrito
no cuesta nada y no depende de que siga haciéndolo.

# Las cabeceras COOP/COEP

Sin ellas el navegador no da `SharedArrayBuffer`, y el runtime de ONNX que usa
la detección de habla es el **multihilo**: lo necesita.

Estaban solo en el servidor de desarrollo, así que el VAD funcionaba en local y
en producción no, sin que nada fallara a la vista — `useSupervision` descarta en
silencio los detectores que no consiguen prepararse. Comprobado en la web
desplegada antes de añadirlas: `crossOriginIsolated: false`.

Se usa `credentialless` y no `require-corp` a propósito. Con `require-corp`, un
recurso de otro origen que no declare `Cross-Origin-Resource-Policy` deja de
cargar, y las capturas de evidencia vienen de Supabase Storage. `credentialless`
los deja pasar sin credenciales, que es justo lo que necesita una URL firmada.

**Al cambiar esto hay que volver a desplegar**, y conviene comprobarlo en la
consola del navegador:

```js
self.crossOriginIsolated   // tiene que ser true
```

## Lo que hay que poner en Vercel al desplegar

| Variable | Qué es |
|---|---|
| `VITE_API_URL` | La URL de la API en Render, sin barra final |
| `VITE_SUPABASE_URL` | La del proyecto Supabase |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | La clave **publicable**, nunca la de servicio |

Las tres se **hornean al construir**, no se leen en el navegador: cambiarlas
obliga a reconstruir, no basta con reiniciar.

Y después del primer despliegue, acordarse de poner el dominio de Vercel en
`CORS_ORIGINS` de la API y en las URL de redirección de Supabase Auth. Sin eso
el navegador bloquea todo y parece un fallo del código.
