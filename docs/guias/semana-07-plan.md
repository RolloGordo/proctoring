# Semana 7 · cierre del Sprint 1

**Entrega: sábado 17/10.** Ese día el sistema tiene que estar **desplegado y
funcionando en público**: web y aplicación de escritorio. Lo pidió el profesor
en la reunión del 10/10 — semanas 7, 11 y 15 con el software desplegado.

Cada uno tiene su archivo con el detalle:

- [Héctor](./hector-semana-07.md) — despliegue, revisión y correcciones
- [Rider](./rider-semana-07.md) — experiencia de uso: docente y estudiante
- [Jesús](./jesus-semana-07.md) — módulo de cámara
- [Pierreluiggi](./pierreluiggi-semana-07.md) — módulo de micrófono y voz

---

## Lo que el profesor pidió y no es código

Esto va primero porque es lo único donde dijo explícitamente que estamos mal.

### Las ceremonias

Dijo: **«hasta ahorita yo debí haber visto seis»**, y vio una, con «estudiante
uno, uno, uno» copiado y pegado. Lo que pide:

- **Dos dailies por semana.** Una donde se acuerda lo que va a hacer cada uno, y
  otra donde cada uno **expone al Scrum Master de turno** lo que hizo.
- **Grabadas.** En Discord o donde sea, le da igual la plataforma.
- **El vídeo en Drive**, no en Notion. Textual: «para que no me revientes el
  Notion, mi capacidad de disco».
- **Los acuerdos escritos en Notion**, en la sección Ceremonias, con nombres
  reales.

No es burocracia: es la mitad de lo que evalúa. Y tiene razón en el fondo — en
esa reunión quedó claro que ninguno sabía en qué andaban los otros.

### El Scrum Master rota, y revisa el backlog con cada uno

El de la semana **repasa el backlog persona por persona** y va cerrando sus
tareas una a una. Dijo también que esa persona **desarrolla menos**, porque se
le va el tiempo en coordinar. Encaja con que esta semana Héctor revise, pruebe
y despliegue en vez de escribir funcionalidad nueva.

### Higiene del backlog

«La integración con Supabase **no es una historia de usuario**». Una historia
necesita interacción de una persona; lo demás es **habilitador** o **tarea
técnica**. Conviene repasar los títulos antes de que lo vuelva a mirar.

---

## Decisiones tomadas esta semana

### Transcripción: se va faster-whisper, entra Deepgram

El profesor insistió en usar una API en vez de un modelo propio. **Tenía razón,
aunque por un motivo distinto del que dijo:** él pensaba que el modelo viaja en
el instalador. Lo comprobé y no: `faster-whisper` vive en `services/ai`, en el
servidor, y el `.exe` no lleva ningún modelo.

El problema real es otro y es más urgente: **un modelo de 1 GB no entra cómodo
en un Hugging Face Space gratuito.** Arranque en frío eterno y memoria justa. Si
queremos el servicio de IA desplegado el sábado, Deepgram es el camino.

Va **en el worker de `services/ai`**, no en el navegador: la clave no puede
acabar en la máquina del estudiante.

### Los detectores del navegador ya no se caen en producción

Esto ya está arreglado y subido. Lo cuento porque explica un fallo que nos
habría costado la demo: `vision.ts` pedía `/mediapipe/wasm` y
`face_landmarker.task`, esa carpeta estaba en `.gitignore` y el script que la
prepara no estaba enganchado al build. **En Vercel habrían sido 404.**

Y no se habría visto: `useSupervision` descarta un detector que no carga y deja
seguir el examen. La web publicada habría corrido todos los exámenes **sin
visión y sin avisar a nadie**.

Ahora los `.wasm` se copian de `node_modules` en el `prebuild` —igual que
Pierreluiggi ya hacía con el VAD—, el modelo está versionado con su licencia y
su hash, y **si falta, el build falla** en vez de publicar un examen ciego.

### El estudiante ve las alertas durante el examen, con detalle

Hasta ahora las veía al terminar. A partir de esta semana se le avisa en el
momento y **diciéndole qué se detectó**: «se detectó una segunda persona», no un
genérico.

Es la opción más transparente y la más defendible: el sistema es un auditor, no
una trampa. Quien tiene mala luz o a quien se le cruzó alguien puede corregirlo;
quien va a copiar, de todas formas lo va a descubrir a la segunda.

---

## El reparto

| Quién | De qué se encarga |
|---|---|
| **Héctor** | Despliegue completo (web + escritorio), revisar los avances, probar la aplicación y corregir lo que aparezca |
| **Rider** | Que crear exámenes, calificarlos, el banco y la edición se entiendan y se usen sin pelearse. Más vistas de estudiante. Descarga de la app en la portada. Que no se pueda rendir desde el navegador |
| **Jesús** | Módulo de cámara: capturas de lo sospechoso, calibración, métricas |
| **Pierreluiggi** | Módulo de micrófono y voz: Deepgram, permiso de micrófono antes del examen, guardado de fragmentos |
| **Jesús + Pierreluiggi** | Las alertas que el estudiante ve durante el examen |

---

## Antes de empezar, los cuatro

```bash
git checkout develop && git pull
```

```bash
npm install --prefix apps/web
```

```bash
docker compose up -d --build api
```

El `npm install` importa esta semana: cambió el `package.json` de la web y hay un
paso nuevo de preparación de assets. El `--build` del contenedor tampoco es
opcional, nunca lo es: la API no recarga sola y el error parece del código recién
bajado.

---

## Cómo sabemos que la semana está cerrada

- [ ] Web desplegada y accesible desde fuera de nuestras máquinas
- [ ] API desplegada, con la web apuntando a ella
- [ ] Instalador descargable desde la portada, y funcionando contra la web desplegada
- [ ] Un examen completo rendido de punta a punta en el sistema desplegado
- [ ] Dos ceremonias grabadas, con el vídeo en Drive y los acuerdos en Notion
- [ ] Backlog revisado por el Scrum Master con cada integrante
