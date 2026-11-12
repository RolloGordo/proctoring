# Cambios implementados: reconexión y revisión de respuestas

**Fecha:** 10 de noviembre de 2026  
**Áreas:** app web del estudiante, panel docente, API y esquema de Supabase.

## Resumen

Se implementaron dos mejoras que estaban pendientes:

1. Si durante un examen se pierde la conexión, la pantalla del estudiante se reemplaza por una pantalla blanca con el mensaje **«Reconectando…»**. Las respuestas que aún no llegaron al servidor se conservan localmente y se reintentan cuando vuelve la conexión.
2. El docente puede decidir si el estudiante podrá revisar la clave de respuestas después de entregar. La API solo entrega esa clave después de la entrega y cuando la opción está habilitada.

Las interrupciones de red se guardan como **diagnósticos técnicos**, separados de las infracciones y del cálculo de riesgo.

## 1. Pantalla de reconexión durante el examen

### Detección de la conexión

La pantalla del examen ahora comprueba periódicamente los servicios necesarios:

- Consulta el endpoint `/health` de la API cada dos segundos, con un tiempo máximo de espera.
- Cuando Supabase está configurado, también comprueba que responda una lectura autenticada del perfil del estudiante.
- Responde inmediatamente al evento `offline` del navegador.

Esto cubre tanto la pérdida de red que detecta el navegador como el caso en que la API o Supabase dejan de responder mientras el equipo todavía informa que está conectado.

### Bloqueo visual y del portapapeles

Al detectar que no se puede llegar a los servicios, React reemplaza el contenido del examen por una pantalla blanca de ventana completa. Muestra **«Reconectando…»** y explica que el examen está bloqueado temporalmente.

Mientras aparece esa pantalla, la web bloquea atajos de copiar, cortar, pegar y seleccionar todo, además de los eventos del portapapeles y el menú contextual. También limpia cualquier selección de texto que hubiera quedado activa. Al volver la conexión, la pantalla del examen reaparece.

### Respuestas pendientes y recuperación

La cola de guardado mantiene la respuesta más reciente de cada pregunta. Las respuestas que esperan reintento se guardan en `localStorage`, separadas por examen y estudiante. Así pueden recuperarse después de una recarga o un cierre accidental de la ventana.

Al volver la conexión:

1. Se vuelve a comprobar la API y, si está configurado, Supabase.
2. Se reintenta el envío de las respuestas que quedaron pendientes.
3. Si el envío final del examen se confirma, se elimina la copia local pendiente para no dejar datos obsoletos en el equipo.
4. Se registra la recuperación de la conexión y el tiempo que duró la interrupción.

También se recuperan las respuestas pendientes en el formulario después de recargar, para que el estudiante vea lo que había contestado mientras el servidor no respondía.

### Diagnósticos de conexión para el docente

Se añadieron los códigos técnicos `network_disconnected` y `network_reconnected`. La interrupción se encola localmente si Supabase no está disponible y se intenta persistir cuando vuelve la conexión. La cola queda separada por estudiante.

En la revisión del caso, el docente ve **«Conexión interrumpida»** y **«Conexión recuperada»**; la recuperación muestra la duración. Estos diagnósticos no son eventos de proctoring, no se consideran infracciones y no suman puntos de riesgo.

## 2. Revisión de respuestas correctas después de entregar

### Configuración docente

Se agregó una casilla en los formularios de creación y edición de exámenes:

> Permitir revisar respuestas correctas después de entregar

La opción está desactivada por defecto. Si el docente la habilita, el estudiante puede revisar las alternativas correctas y las respuestas esperadas en preguntas numéricas o de texto, una vez entregado el examen.

### Protección en la API

La clave no se agrega a los endpoints que sirven preguntas durante el examen ni al endpoint de respuestas previamente existente. Se creó un endpoint separado:

```text
GET /api/v1/exam/{session_id}/submitted-review
```

La API verifica que:

- quien solicita sea estudiante y no docente;
- pertenezca al examen;
- ya haya entregado;
- el docente haya habilitado la revisión de respuestas correctas.

El endpoint de repaso que ya existía sigue devolviendo preguntas sin la clave. El nuevo endpoint solo devuelve preguntas con sus respuestas correctas cuando se cumplen las condiciones anteriores.

### Vista del estudiante

En el detalle del examen entregado se muestran las respuestas del estudiante como antes. Si el endpoint protegido autoriza la revisión, la página además identifica las alternativas correctas y muestra las respuestas esperadas de los tipos numérico y texto. Si el docente no habilitó la opción, se informa que la clave no está disponible.

## 3. Persistencia y migración de Supabase

Se agregó la columna `show_answers_after_submission` a `exam_sessions`, con `false` como valor predeterminado. Los exámenes existentes mantienen así el comportamiento seguro de no revelar la clave.

La misma migración actualiza la restricción de códigos permitidos en `supervision_diagnostics` para incluir los dos diagnósticos de conexión.

Archivo:

- [supabase/migrations/20261110090000_exam_review_and_network_diagnostics.sql](../supabase/migrations/20261110090000_exam_review_and_network_diagnostics.sql)

Hay que aplicar esta migración en cada base de datos antes de desplegar el backend y la web actualizados. No se modificó directamente una base remota desde este cambio.

## 4. Privacidad y almacenamiento local

Se actualizó el aviso de almacenamiento y la página de privacidad para explicar que el navegador conserva temporalmente las respuestas que todavía no llegaron al servidor. Se borran al confirmarse el guardado; si hay un corte de red, permanecen hasta que se puedan reenviar.

No se guardan capturas ni audio en esta cola: contiene únicamente las respuestas pendientes y los diagnósticos de disponibilidad de red.

## 5. Archivos principales modificados

- `apps/web/src/pages/RendirExamen.tsx`: comprobación de disponibilidad, bloqueo y reintento de respuestas.
- `apps/web/src/lib/cola-de-guardado.ts`: persistencia y recuperación de respuestas pendientes.
- `apps/web/src/lib/api.ts`: comprobación de conectividad y contrato de la nueva revisión.
- `apps/web/src/supervision/diagnostics.ts`: cola de diagnósticos de conexión y persistencia.
- `apps/web/src/pages/RevisionCaso.tsx`: etiquetas y detalle de las interrupciones de red.
- `apps/web/src/pages/NuevaSesion.tsx` y `apps/web/src/pages/EditarSesion.tsx`: configuración de revisión de respuestas correctas.
- `apps/web/src/pages/DetalleExamenEstudiante.tsx`: presentación de respuestas correctas autorizadas.
- `services/api/src/proctoring_api/domain/exam_session.py`: nueva propiedad de configuración.
- `services/api/src/proctoring_api/application/use_cases/create_exam_session.py` y `edit_exam_session.py`: creación y edición de la opción.
- `services/api/src/proctoring_api/application/use_cases/manage_questions.py`: validación de entrega y permiso antes de revelar la clave.
- `services/api/src/proctoring_api/adapters/inbound/http/routers/questions.py`: ruta protegida de revisión.
- `services/api/src/proctoring_api/adapters/inbound/http/schemas.py` y `routers/sessions.py`: contratos de la API.
- `services/api/src/proctoring_api/adapters/outbound/supabase/exam_session_repository.py`: lectura y escritura del nuevo campo.
- `packages/contracts/database.types.ts`: tipo de la nueva columna.
- `apps/web/src/pages/Privacidad.tsx` y `apps/web/src/components/AvisoAlmacenamiento.tsx`: aviso sobre respuestas locales pendientes.
- `apps/web/src/styles/base.css`: estilos de la pantalla blanca de reconexión.

## 6. Verificación realizada

- `npx tsc -b --pretty false`: completó sin errores.
- `git diff --check`: completó sin errores.
- No se ejecutó la suite de pruebas.
- No fue posible ejecutar revisión o compilación de Python: en el entorno no estaban disponibles Python ni `uv`.

## 7. Pendientes y límites conocidos

- Aplicar la migración de Supabase antes de usar el cambio con la base de datos.
- Probar manualmente una desconexión real durante un examen, tanto en navegador como en la app Electron, y confirmar que el docente ve los dos diagnósticos.
- Probar la revisión habilitada y deshabilitada con un estudiante que ya haya entregado, además de confirmar que la clave nunca aparece durante el examen.
- Los escritorios virtuales de Windows no se enumeran explícitamente. La app existente registra `focus_lost` cuando la ventana pierde el foco; queda pendiente comprobar en un equipo Windows si cambiar de escritorio virtual genera esa pérdida de foco y registra la duración esperada.
- La duración oficial del examen sigue dependiendo de la hora de cierre del servidor; esta implementación no pausa ni amplía el examen automáticamente por una interrupción de red.

