# Semana 6 — Héctor Silva Vega

Rama `feat/EN-002-exam-screens`. Lo que faltaba para que un examen se pueda
**crear, rendir y entregar** de principio a fin.

## Qué se hizo

### API — respuestas del estudiante (lo que faltaba de verdad)

Hasta ahora un estudiante podía recibir las preguntas y entregar, pero **no
había dónde guardar lo que respondía**. La tabla `answers` existía desde la
migración inicial y ningún endpoint la tocaba: entregar era marcar una hora y
nada más.

Se añadió, siguiendo la arquitectura hexagonal de siempre:

| Capa | Archivo |
|---|---|
| Dominio | `domain/answer.py` — `Answer`, `InvalidAnswerError` |
| Puerto | `application/ports/answer_repository.py` |
| Casos de uso | `application/use_cases/manage_answers.py` — `SaveAnswers`, `ListMyAnswers` |
| Adaptadores | `adapters/outbound/{memory,supabase}/answer_repository.py` |
| HTTP | `adapters/inbound/http/routers/answers.py` |

Dos endpoints nuevos:

- `PUT /api/v1/exam/{session_id}/answers` — guarda. Es `PUT` porque responder
  otra vez **reemplaza**: la clave es `(participant_id, question_id)`, la misma
  restricción única que tiene la tabla.
- `GET /api/v1/exam/{session_id}/answers` — devuelve lo ya respondido, para
  retomar el examen donde se quedó.

Decisiones que vale la pena justificar:

- **La validación recibe una `ExamQuestion`, no una `Question`.** Es la vista de
  la pregunta que no tiene la respuesta correcta, así que el módulo de
  respuestas no puede filtrar lo que no debe ni por error.
- **`AnswerResponse` no lleva `is_correct` ni `points_awarded`.** Devolverlos al
  guardar le diría al estudiante si acertó mientras rinde. Hay una prueba que
  falla si alguna vez aparecen en el cuerpo.
- **Se construyen todas las respuestas antes de guardar ninguna.** Si la tercera
  del lote viene mal, el estudiante no se queda con dos guardadas y un error.
- **Una opción tiene que ser de esa pregunta.** Mandar el id de una opción de
  otra pregunta guardaría una respuesta que después nadie podría calificar.
- **Las mismas cinco condiciones que para leer las preguntas**: matriculado, con
  consentimiento, con la identidad resuelta, sin haber entregado y con la
  ventana del examen abierta.

### Web — las pantallas que faltaban

| Ruta | Pantalla | Para quién |
|---|---|---|
| `/sesiones/:id/preguntas` | Crear y listar preguntas del examen | Docente |
| `/sesiones/:id/participantes` | Sala de espera: admitir o rechazar identidad | Docente |
| `/examen/:id/sala` | Consentimiento informado + espera | Estudiante |
| `/examen/:id/rendir` | Rendir el examen y entregar | Estudiante |

La pantalla del examen **guarda al responder, no al entregar**: un examen
supervisado corre en un equipo que se puede reiniciar o quedarse sin batería.
Las respuestas viajan en lotes cada medio segundo y el estado ("Guardando…",
"Guardado", "No se pudo guardar") se muestra mientras el estudiante todavía
puede hacer algo al respecto.

La sala de espera del estudiante **consulta sola** cada 10 segundos mientras su
identidad no esté resuelta: está esperando a que su docente lo admita y no tiene
por qué recargar la página para enterarse.

## Cómo se comprobó

Flujo completo contra la API en Docker (`services/api` en `localhost:8000`):

```
examen sin matricula                          403
matricularse sin aceptar                      400
aceptar la supervision                        201
examen sin verificar identidad                403
el docente lo admite a mano                   200
recibe el examen                              200
guarda 4 respuestas                           200
cambia una respuesta                          200
recupera 4 respuestas (no 5)                  200
responder con texto una de opciones           400
responder una pregunta de otro examen         400
entrega                                       200
responder despues de entregar                 403
```

Y el mismo recorrido a mano en el navegador, con las cuatro pantallas nuevas:
crear una pregunta desde el formulario, entrar con el código, aceptar la
supervisión, ser admitido por el docente, responder, **recargar la página y
recuperar lo respondido**, y entregar.

Puertas del proyecto, todas en verde:

```
ruff format · ruff check          sin cambios, sin errores
mypy                              119 archivos, sin incidencias
pytest                            417 pruebas
lint-imports                      2 contratos, 0 rotos
eslint · tsc · vite build         sin errores
```

## Correcciones de paso

- `.campo > label` no casaba con nada: todas las pantallas escriben
  `<label class="campo"><span>…`, así que las etiquetas de los formularios
  estaban sin estilo desde el principio.
- ESLint estaba revisando `.vite/deps`, la caché de dependencias de Vite, y
  reportaba errores de código que no es nuestro.
- El editor de opciones permitía marcar varias correctas, pero una respuesta
  guardada apunta a **una** opción (`selected_option_id`). Marcar dos habría
  creado una pregunta que nadie puede responder entera; ahora el editor produce
  solo lo que el sistema sabe calificar. El dominio de la API sigue admitiendo
  varias: hará falta al importar QTI.

## Capturas

| Archivo | Qué muestra |
|---|---|
| `01-docente-preguntas.jpg` | Pantalla de preguntas del docente, con la correcta marcada |
| `02-estudiante-examen.jpg` | Examen del estudiante, con el contador y el guardado automático |
| `03-docente-sala-de-espera.jpg` | Sala de espera tras admitir a mano a un estudiante |
