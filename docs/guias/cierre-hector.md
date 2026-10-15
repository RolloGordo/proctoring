# Héctor · lo que falta para cerrar

**Mi fecha es el viernes 16/10**, un día después que el equipo, porque el
despliegue va después de recibir lo de todos.

## Lo que ya está hecho

- Fusionados los PR #42 (Rider) y #43 (Pierreluiggi + Jesús). `develop` al día y en
  verde: **API 853 pruebas, IA 152, web 120**, lint, tipos y build limpios.
- Worker de IA desplegable: imagen de producción de 9,71 GB a **2,14 GB** (torch
  traía 3 195 MB de CUDA y 895 MB de triton para un worker sin GPU). La mínima de
  compose, 471 MB, llega a `healthy`.
- `numpy` declarada por fin —entraba de rebote y `measure_audio` la usa en cada
  trabajo— y `av` movida a donde se usa.
- [`despliegue-y-escritorio.md`](./despliegue-y-escritorio.md) escrito.

## 1. TA-078 · Hornear `PROCTORING_WEB_URL` · **bloquea a Rider**

`apps/desktop/src/main/web.ts:22` lo lee de `process.env` en tiempo de ejecución y
**nada lo inyecta al empaquetar**. Un `.exe` publicado apunta a `localhost:5173`
en la máquina del estudiante.

De esa única variable cuelgan cuatro cosas: qué carga la ventana, a dónde puede
navegar, a qué origen se le conceden cámara y micrófono, y qué origen acepta el
enlace `proctoring://`. Que las cuatro deriven de lo mismo está bien hecho, así
que apuntarla a la web desplegada basta.

- [ ] Inyectar la URL al empaquetar (`define` de electron-vite o `extraMetadata`)
- [ ] **Que el empaquetado falle** si no está puesta, para que publicar un instalador roto sea imposible y no solo esté documentado
- [ ] Probar el `.exe` resultante en otra máquina

## 2. Las cuentas y el despliegue, en este orden

El orden importa porque cada paso necesita la URL del anterior:

- [ ] **API en Render** → da la URL de la API
- [ ] **Web en Vercel** con `VITE_API_URL`, `VITE_SUPABASE_URL` y `VITE_SUPABASE_PUBLISHABLE_KEY`. Las `VITE_*` se hornean **al construir**: cambiarlas obliga a reconstruir, no solo a reiniciar
- [ ] **`CORS_ORIGINS` de la API** con el dominio de Vercel, y las URL de redirección de Supabase Auth
- [ ] **Worker de IA** en Hugging Face Spaces + Redis en Upstash
- [ ] **Y solo entonces** el instalador, construido apuntando a Vercel

Ninguna cuenta está creada todavía. Todo en plan gratuito.

## 3. Las tres pruebas que bloquean publicar

No publico hasta que las tres estén en verde, y ninguna lo está:

| | Quién | Estado real |
|---|---|---|
| `TA-063` prueba de humo | Rider | Sin hacer |
| `TA-064` worker de audio | Pierreluiggi | **Cola verificada, latencia sin medir** |
| `TA-065` verificación facial | Yo | Sin medir (P90 < 500 ms) |

Sobre TA-064: su informe concluye que los 10 s «se cumplen holgadamente con
2.14 s», pero en esa prueba todo lo caro está simulado y aquí tarda 61 ms. **No
cerrar TA-064 en el backlog**: queda como «cola verificada, latencia pendiente».

## 4. Deuda técnica que anoté y no es de esta semana

- **No hay pruebas de componente.** vitest corre con `environment: 'node'` y sin
  testing-library, así que `PruebaMicrofono` y las demás pantallas no se pueden
  probar montadas. Meter jsdom es una decisión de herramienta para hablarla en
  equipo, no para colarla a mitad de semana.
- **No hay actualización automática del instalador.** `electron-builder.yml` trae
  todavía el marcador de la plantilla (`url: https://example.com/auto-updates`).
  Mientras siga así, cada cambio del proceso principal obliga a reinstalar.
- **TA-065** sigue sin medición de P90.

## 5. Lo que el profesor pidió y no es código

- **Dos dailies por semana**, grabadas, **el vídeo en Drive** (no en Notion, por espacio) y los **acuerdos escritos en Notion** con nombres reales. Esperaba seis ceremonias y encontró una.
- **Los títulos del backlog**: «la integración con Supabase no es una historia de usuario». Una historia necesita interacción de una persona; lo demás es habilitador o tarea técnica.
