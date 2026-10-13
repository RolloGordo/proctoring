# Héctor · semana 7

**Entrega: sábado 17/10.** Despliegue público de web y aplicación, cierre del
Sprint 1.

Esta semana desarrollas poco y coordinas mucho, que es lo que el profesor dijo
que le toca al Scrum Master de turno. Tu trabajo: **desplegar, revisar, probar y
corregir**.

---

## 1. El despliegue

Plan de `CLAUDE.md`, todo en capa gratuita. Las cuentas están **por crear**.

| Qué | Dónde | Qué hace falta |
|---|---|---|
| Web | **Vercel** | Cuenta, importar el repo, raíz `apps/web`, variables `VITE_*` |
| API | **Render** | Cuenta, servicio desde `services/api/Dockerfile`, todas las variables del `.env` |
| Servicio de IA | **Hugging Face Spaces** (Docker) | Cuenta, Space desde `services/ai/Dockerfile`, clave de Deepgram |
| Redis | **Upstash** | Cuenta, base, y su URL a la API y al worker |
| Aplicación | **GitHub Releases** | Ya existe el repositorio; falta publicar (es de Rider) |
| Base de datos | **Supabase Cloud** | Ya está |

### El orden importa

1. **Supabase** ya está. Nada que hacer.
2. **Upstash** primero: la API y el worker lo necesitan.
3. **API en Render**. Anota la URL pública.
4. **Web en Vercel** con `VITE_API_URL` apuntando a esa URL.
5. **CORS**: añade el dominio de Vercel a `CORS_ORIGINS` en Render. Si no, la web
   publicada no puede hablar con la API y el error es un `Failed to fetch` que no
   explica nada. Ya nos pasó en local.
6. **Servicio de IA** en Spaces, cuando Pierreluiggi haya quitado faster-whisper.
   Con el modelo de 1 GB dentro no va a arrancar bien.
7. **Instalador** apuntando a la web publicada, y Release.

### Dos cosas que se van a romper, sobre aviso

**El instalador apunta a localhost.** `apps/desktop/src/main/web.ts`:

```ts
return process.env['PROCTORING_WEB_URL'] ?? 'http://localhost:5173'
```

En un `.exe` instalado esa variable no existe, así que va a `localhost:5173`,
donde no hay nada. **Es el error que Rider no podía resolver** en la otra
computadora. Hay que construir el instalador con esa variable apuntando a Vercel,
o cambiar el valor por defecto. Decídelo antes de que Rider publique el Release,
porque si no publica uno roto.

**Los secretos.** La clave de servicio de Supabase y la de Deepgram van en las
variables de Render y del Space, y en GitHub Secrets para el CI. Nunca en el
repositorio, ni en un `.env.example` con valor.

---

## 2. Revisar, probar y corregir

Es la mitad de tu semana y lo que el profesor espera del Scrum Master.

### Lo que nadie ha probado todavía

Tres pantallas están construidas, pasan pruebas, y **nadie las ha visto
funcionar con sesión iniciada**:

- **Cámaras en vivo** (cuadrícula de Rider) — que conecte de verdad entre docente
  y estudiante
- **Evidencia del caso** — que una captura se abra y un audio suene
- **Verificación facial** — que el panel aparezca en la sala tras el
  consentimiento

Son las tres capturas que además te faltan para el Notion, así que mátalas de un
tiro.

### Un recorrido completo, en lo desplegado

Cuando esté publicado, hazlo entero una vez: crear examen → código → estudiante
descarga la app → entra → verificación facial → rinde → se detecta algo → alerta
al docente → entrega → nota → revisión del caso con evidencia → decisión
justificada.

Si eso funciona de punta a punta en público, el sprint está cerrado. **Grábalo**:
ese vídeo vale por toda la presentación.

---

## 3. Lo que el profesor pidió y no es código

### Las ceremonias — esto es lo más urgente

Dijo «hasta ahorita yo debí haber visto seis» y vio una, con «estudiante uno,
uno, uno» copiado y pegado. Pide **dos dailies por semana**, grabadas, **vídeo en
Drive** (no en Notion, por el espacio) y **acuerdos escritos en Notion** con
nombres reales.

Es la mitad de lo que evalúa y es lo único donde dijo claramente que estamos
mal. Y en el fondo tiene razón: en esa reunión quedó claro que ninguno sabía en
qué andaban los otros.

### Revisar el backlog con cada uno

Te toca a ti esta semana: pasar por cada integrante, ver qué hizo y **cerrar sus
tareas una a una**. Es la segunda daily.

### Higiene del backlog

«La integración con Supabase no es una historia de usuario». Una historia
necesita interacción de una persona; lo demás es **habilitador** o **tarea
técnica**. Repasa los títulos antes de que lo vuelva a mirar — es una corrección
barata y la va a buscar.

---

## 4. Ya hecho esta semana

**Los assets de MediaPipe.** Un despliegue habría servido `/mediapipe/wasm` y
`face_landmarker.task` como 404, y la web publicada habría corrido **todos los
exámenes sin detección de visión, sin un solo error visible**. Los `.wasm` ahora
se copian de `node_modules` en el `prebuild`, el modelo está versionado con su
licencia y su hash, y si falta **el build falla** en vez de publicar un examen
ciego.

---

## Cómo sabemos que la semana está cerrada

- [ ] Web desplegada y accesible desde fuera
- [ ] API desplegada, con la web apuntando a ella y CORS resuelto
- [ ] Servicio de IA desplegado (depende de que Pierreluiggi quite faster-whisper)
- [ ] Instalador construido contra la web publicada y en GitHub Releases
- [ ] Un examen completo rendido de punta a punta en lo desplegado, grabado
- [ ] Dos ceremonias grabadas, vídeo en Drive, acuerdos en Notion
- [ ] Backlog revisado con cada integrante y cerrado
