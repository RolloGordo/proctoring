# Jesús · correcciones del primer examen real

Héctor rindió un examen completo contra el **sistema desplegado** el 16/10.
Durante el examen habló, miró el celular, se salió del encuadre y miró a los
costados. **No se registró ni una sola señal de cámara, ni una captura.**

Tus detecciones de proceso y foco (las de la app de escritorio) sí funcionaron
perfectamente. Lo que no produjo nada fue la visión.

> **Contexto si pegas esto en un chat de IA:** plataforma de proctoring para
> exámenes remotos (UPAO, Taller Integrador 1). Tu parte es la visión por
> computadora en `apps/web/src/supervision/` y el mantenimiento de la base en
> `supabase/migrations`. **Código y commits en inglés; interfaz en español;
> tablas en snake_case.** Lee `CLAUDE.md`. **El sistema es auditor, no juez:**
> nunca expulsa a nadie, registra y decide el docente.

```bash
git checkout develop && git pull && npm install --prefix apps/web
```

Web desplegada: **https://proctoring-brown.vercel.app**

---

## Lo que ya arreglé, para que no lo busques

En producción faltaban las cabeceras COOP/COEP, así que no había
`SharedArrayBuffer` y el runtime de ONNX multihilo no arrancaba. Ya están en
`apps/web/vercel.json`. **Eso era condición necesaria, no la causa única.**

Antes de nada, abre la web desplegada, pulsa **F12** → pestaña **Console**, y
escribe:

```js
self.crossOriginIsolated
```

Tiene que decir `true`. Si dice `false`, avísame antes de seguir.

## 1 · Por qué no se registró nada (punto 9) · 3 pt · **lo primero**

`useSupervision` **descarta en silencio** los detectores que no consiguen
prepararse. Por eso no hubo ningún error en pantalla: simplemente no había
detector.

Averigua cuál es el caso. Con la consola abierta durante un examen real:

- [ ] ¿Se prepara el detector de visión, o lanza al prepararse?
- [ ] ¿Llega el `MediaStream` de la cámara al detector?
- [ ] ¿Se emiten señales y fallan al subirse, o no se emiten?

Y **que deje de fallar en silencio**: si un detector no arranca, el estudiante
tiene que verlo y el docente tiene que saber que ese módulo no estuvo activo
durante el examen. Una supervisión que no supervisó y nadie se entera es peor
que no tenerla.

- [ ] Un detector que no arranca se registra y se avisa, no se descarta callando
- [ ] Probado de punta a punta: mirar a un lado genera `gaze_away` y llega al docente
- [ ] Probado que la captura sube a Storage y el docente la abre desde la revisión

## 2 · La verificación facial no sirvió (punto 10) · 2 pt

Héctor tuvo que admitirse a mano desde la cuenta del docente. La verificación
automática no resolvió.

- [ ] Averiguar si falla la captura, la subida, el worker o la comparación
- [ ] Un fallo de verificación dice **por qué**, no solo que no pudo
- [ ] La admisión manual sigue existiendo: es la salida correcta cuando la cámara no reconoce a alguien
- [ ] Probado con buena y con mala luz

## 3 · La cámara en vivo va mal (punto 12) · 2 pt

> «La calidad de la cámara en vivo es muy mala, lenta en fotogramas.»

Y eso con **un** estudiante. Con treinta hay que saber qué pasa antes de la
demo.

- [ ] Medir cuántos fotogramas por segundo llegan de verdad y con cuánto retardo
- [ ] Decidir y escribir el compromiso: ¿más calidad o más fluidez? ¿cuántos estudiantes a la vez?
- [ ] Probado con al menos tres estudiantes simultáneos (pide ayuda a los demás)

## 4 · La detección es demasiado general (punto 19) · 2 pt

> «Muy general y poco precisa al indicar si estoy mirando a un costado, tengo un
> objeto extraño en la mano o si entra alguien al cuarto.»

Esto enlaza con tus métricas, que siguen sin tomarse. El objetivo del proyecto
es **accuracy ≥ 80 % y FPR < 20 % por módulo**, y de mirada y rostro no hay
ningún número.

- [ ] Casos etiquetados: mirada dentro/fuera, rostro presente/ausente, una persona/dos
- [ ] Accuracy, FPR y **FNR** por módulo
- [ ] Decir el número aunque no llegue al 80 %: un resultado medido que no cumple vale más que un «cumple» sin medir

## 5 · Falta el nombre del estudiante (punto 11) · 1 pt · con Rider

Las alertas dicen «Estudiante e989cb23» porque **no se pide nombre y apellidos
al registrarse**. La columna `profiles.full_name` existe y está vacía.

- [ ] El registro pide nombre y apellidos y los guarda en `profiles.full_name`
- [ ] Alertas, resultados y revisión del caso muestran el nombre, no el id
- [ ] Los perfiles que ya existen sin nombre no rompen nada: se ve el correo

> El formulario de registro es de Rider; la columna y la migración, tuyas.
> Pónganse de acuerdo antes de empezar para no hacerlo dos veces.

---

## Antes de subir

```bash
cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build
```

Si tocas la base, **crea una migración nueva** en `supabase/migrations`. No
toques el esquema desde el panel de Supabase.
