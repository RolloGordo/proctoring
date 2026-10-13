# Héctor · semana 7

**Lunes 12/10 → viernes 16/10.** Revisión del sprint el sábado 17.

Esta semana desarrollas poco y coordinas mucho, que es lo que el profesor dijo
que le toca al Scrum Master de turno: **revisar, probar, corregir y dejar el
despliegue preparado**.

**6 tareas, 9 puntos.**

---

## TA-079 · Recorrido completo y registro de defectos · 2 pt

Es lo primero y de aquí sale todo lo demás. Recorre el sistema entero como lo
haría un docente y un estudiante, anotando **todo** lo que falle o confunda.

**Recorrido:** crear examen → código → estudiante entra → verificación facial →
rinde → se detecta algo → alerta al docente → entrega → nota → revisión del caso
con evidencia → decisión justificada.

**Las tres pantallas que nadie ha visto funcionar** con sesión iniciada:

- [ ] **Cámaras en vivo** (cuadrícula de Rider) — que conecte entre docente y estudiante
- [ ] **Evidencia del caso** — que una captura se abra y un audio suene
- [ ] **Verificación facial** — que el panel aparezca en la sala tras el consentimiento

Cada fallo que encuentres, anótalo con **cómo reproducirlo**. Eso alimenta
`BU-006`.

Y grábalo: ese vídeo vale por toda la presentación del sábado.

---

## BU-006 · Corregir los defectos del Sprint 1 · 2 pt

Lo que salga de `TA-079`, más lo que ya sabemos:

- El aviso «Supervisión activa» en `Capas.tsx` es **texto fijo**: se muestra haya
  o no supervisión. Si la cámara falla, el estudiante igual lee que lo están
  supervisando. En un sistema cuya promesa es ser honesto sobre lo que observa,
  eso está al revés.
- Lo que aparezca al probar lo de tus compañeros.

---

## TA-078 · Dejar el despliegue preparado, sin publicar · 2 pt

**Preparado, no publicado.** Publicar algo sin probar es enseñar una demo que se
rompe.

| Qué | Dónde | Qué hace falta |
|---|---|---|
| Web | **Vercel** | Cuenta, importar repo, raíz `apps/web`, variables `VITE_*` |
| API | **Render** | Cuenta, servicio desde `services/api/Dockerfile`, variables del `.env` |
| Servicio de IA | **Hugging Face Spaces** | Cuenta, Space Docker, clave de Deepgram |
| Redis | **Upstash** | Cuenta, base, URL a la API y al worker |
| Base de datos | **Supabase Cloud** | Ya está |

### El orden importa

1. **Upstash** primero: la API y el worker lo necesitan.
2. **API en Render**. Anota la URL pública.
3. **Web en Vercel** con `VITE_API_URL` apuntando ahí.
4. **CORS**: el dominio de Vercel en `CORS_ORIGINS` de Render. Si no, la web
   publicada no habla con la API y el error es un `Failed to fetch` que no
   explica nada. Ya nos pasó en local.
5. **Servicio de IA** en Spaces, **cuando Pierreluiggi haya quitado
   faster-whisper** (`TA-070`). Con el modelo de 1 GB dentro no arranca bien.

### Dos cosas que se van a romper, sobre aviso

**El instalador apunta a localhost.** `apps/desktop/src/main/web.ts`:

```ts
return process.env['PROCTORING_WEB_URL'] ?? 'http://localhost:5173'
```

En un `.exe` instalado esa variable no existe. **Es el error que Rider no podía
resolver** en la otra computadora. Decide el valor **antes** de que publique el
Release, o publicará uno roto.

**Los secretos.** Clave de servicio de Supabase y clave de Deepgram van en las
variables de Render y del Space, y en GitHub Secrets para el CI. Nunca en el
repositorio, ni en un `.env.example` con valor.

### La condición para publicar

`EN-012` (publicar) está en la semana 8 y **depende de que estén en verde**:

- `TA-063` — prueba de humo (Rider)
- `TA-064` — worker de audio con Redis y Storage reales (Pierreluiggi)
- `TA-065` — verificación facial con el modelo real (Jesús)

Si las tres llegan esta semana, publicas el viernes y cumplimos lo que pidió el
profesor. Si no, se publica en cuanto lleguen y **se dice por qué**.

---

## DO-031 · Revisar el backlog con cada integrante · 1 pt

El profesor fue explícito: el que lleva la semana revisa el backlog **junto con**
su equipo, no cada uno por su lado. Es la segunda daily.

- [ ] Revisado con los cuatro, uno por uno
- [ ] Cada tarea queda cerrada o con lo que le falta anotado
- [ ] **Títulos corregidos**: lo que no tiene interacción de usuario no es historia de usuario. Él lo señaló con «la integración con Supabase»
- [ ] Grabado, acuerdos escritos en Notion

---

## DO-007 · Las ceremonias · 1 pt · **lo más urgente que no es código**

Dijo «hasta ahorita yo debí haber visto seis» y vio una, con «estudiante uno,
uno, uno» copiado y pegado.

- [ ] **Dos dailies esta semana.** Una de acuerdos, otra donde cada uno expone
- [ ] Grabadas, en Discord o donde sea
- [ ] **El vídeo en Drive**, no en Notion — textual: «para que no me revientes el Notion, mi capacidad de disco»
- [ ] **Los acuerdos escritos en Notion**, con nombres reales

Es la mitad de lo que evalúa y es lo único donde dijo claramente que estamos
mal. Y en el fondo tiene razón: en esa reunión quedó claro que ninguno sabía en
qué andaban los otros.

---

## DO-006 · Guion de la demo y Sprint Review 1 · 1 pt

Para el sábado. Que la demo siga el recorrido de `TA-079` y que cada cosa que se
enseñe tenga su evidencia detrás.

---

## Lo que ya hice esta semana

**Los assets de MediaPipe.** Un despliegue habría servido `/mediapipe/wasm` y
`face_landmarker.task` como 404, y la web publicada habría corrido **todos los
exámenes sin detección de visión, sin un solo error visible**. El modelo no
estaba ni en este checkout: solo existía en la máquina de Jesús.

Ahora los `.wasm` se copian de `node_modules` en el `prebuild`, el modelo está
versionado con licencia y hash, y **si falta, el build falla**.

**El backlog.** Tres tareas (`HU-011`, `SP-010`, `HU-015`) decían «Sprint 2» con
fechas del Sprint 1. Corregido. Y lo que no se cerró en la semana 6 pasó a la 7
con nota de que viene de atrás, en vez de quedar escondido.
