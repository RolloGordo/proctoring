# Jesús · lo que falta para cerrar

**Fecha límite del equipo: jueves 15/10.** Tu HU-025 está fusionada en `develop`.

> Si pegas esto en un chat de IA: el proyecto es una plataforma de proctoring para
> exámenes remotos (UPAO, Taller Integrador 1). Tu parte es la visión por
> computadora en `apps/web/src/supervision/` (rostro, mirada, persona adicional)
> y el mantenimiento de la base de datos en `supabase/migrations`. **Código,
> identificadores y commits en inglés; la interfaz en español. Tablas y columnas
> en snake_case.** Lee `CLAUDE.md` en la raíz antes de tocar nada.
>
> **El sistema es auditor, no juez:** nunca anula un examen ni expulsa a nadie.
> Registra evidencia y el docente decide, con justificación obligatoria.

## Antes de empezar

```bash
git checkout develop && git pull && npm install --prefix apps/web
```

---

## Lo que YA entró (no lo rehagas)

- **HU-025** — los avisos al estudiante. **Se quedó tu redacción**, porque nombra la
  señal concreta en vez de dar un genérico, y porque en `speech_detected` dice con
  todas las letras que hablar no es una infracción. Esa frase es la promesa del
  proyecto. Lo que se tomó de Pierreluiggi fue solo el anti-rebote, que ahora es
  `GestorDeAvisos` en `apps/web/src/supervision/avisos.ts`.
- Tu comprobación de tamaño del modelo entró en `apps/web/scripts/prepare-mediapipe.mjs`:
  el build **falla** si `face_landmarker.task` no está o pesa menos de 10 KB. Buena idea,
  porque sin eso los detectores se caían en silencio.
- El detector de pérdida de cámara ya escucha el evento `ended` de la pista
  (`useSupervision.ts:153`).

---

## 1. TA-083 · La cámara sigue encendida todo el examen · 2 pt

De la daily del 13/10: «que se quede prendido durante todo el examen». No basta
con pedirla al empezar.

Ya detectas el evento `ended` de la pista. **Lo que falta es cerrar el círculo:**

- [ ] Que el **docente** vea que ese estudiante se quedó sin cámara, en vivo
- [ ] Que el estudiante reciba el aviso (usa `GestorDeAvisos`, no montes otra caja encima del enunciado)
- [ ] **Quedarse sin cámara NO expulsa**: queda registrado y decide el docente
- [ ] **Probado desenchufando la cámara a mitad de examen**, no solo con una prueba unitaria
- [ ] Funciona en la web **y** en la aplicación de escritorio

Ojo con un caso que el evento `ended` no cubre: si otra aplicación se queda la
cámara, o el estudiante la tapa, la pista sigue «viva» pero no llega imagen.
Piensa si quieres detectar también fotogramas congelados o completamente negros.

## 2. Calibración · no existe todavía

Busqué «calibra» en todo `apps/web/src` y no hay nada. Hace falta, porque sin
calibrar, el umbral de «mirada fuera de pantalla» es el mismo para alguien con dos
monitores que para alguien con un portátil de 13 pulgadas, y ahí es donde nacen
los falsos positivos.

- [ ] Una pantalla corta antes del examen: mira al centro, a las esquinas
- [ ] Guardar el resultado por estudiante y usarlo como umbral
- [ ] Si el estudiante no calibra, usar el umbral por defecto y **dejar constancia** de que no se calibró
- [ ] Probado con dos personas distintas y dos pantallas distintas

## 3. Métricas · el objetivo SMART · **esto es lo que el profesor va a medir**

El objetivo del proyecto es **accuracy ≥ 80 % y FPR < 20 % por módulo**. De tus
dos módulos (mirada y rostro) **no hay ninguna medición todavía**.

Tienes el spike montado en `apps/web/spikes/vision/` con `datasets` y `tools`,
así que la infraestructura está. Falta correr la medición y escribir los números:

- [ ] Un conjunto de casos etiquetados: mirada dentro / fuera, rostro presente / ausente, una persona / dos
- [ ] Calcular accuracy, FPR y **FNR** por módulo
- [ ] Decir el número aunque no llegue al 80 %. Un resultado medido que no cumple vale mucho más que un «cumple» sin medir
- [ ] Grabar cómo se obtuvo, para que sea repetible

> Mira lo que le pasó a Pierreluiggi con TA-062: reportó 92,2 % de accuracy, pero
> el detalle decía que se le escapaba una de cada tres voces sintéticas. El número
> suelto no dice nada sin su FNR al lado.

## 4. Capturas de actividad sospechosa

`apps/web/src/supervision/capturasVision.ts` existe. Falta comprobar de punta a
punta que la captura llega al bucket privado y que el docente la abre desde la
revisión del caso.

- [ ] Una captura real sube a Storage con URL firmada
- [ ] El docente la ve en la pantalla de revisión del caso
- [ ] No se guarda vídeo continuo, solo el fotograma del evento

---

## Antes de subir

```bash
cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build
```

Si tocas la base de datos, **crea una migración nueva** en `supabase/migrations`.
No modifiques el esquema desde el panel de Supabase.

Las evidencias (capturas, vídeos) van **al Notion**, no al repositorio.
