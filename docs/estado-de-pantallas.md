# Estado de las pantallas

Qué vistas existen hoy, cuáles faltan y de quién son. Contrastado con el
prototipo (`Prototipo_Sistema_Proctoring_v2`) y con los SPEC.

Última revisión: 5 de octubre de 2026.

## Docente (web)

| Pantalla | Ruta | Estado | SPEC | Responsable |
|---|---|---|---|---|
| Portada pública | `/` | ✅ | SPEC-001 | Héctor |
| Entrar | `/login` | ✅ | SPEC-001 | Héctor |
| **Panel**: qué pide atención ahora | `/docente` | ✅ | SPEC-009 | Héctor |
| Mis exámenes | `/sesiones` | ✅ | SPEC-002 | Héctor |
| Crear examen | `/sesiones/nueva` | ✅ | SPEC-002 | Héctor |
| Examen en vivo (alertas y señales) | `/sesiones/:id` | ✅ | SPEC-009 | Héctor |
| Preguntas del examen | `/sesiones/:id/preguntas` | ✅ | SPEC-003 | Héctor |
| Sala de espera (con nombre y correo; admitir identidad) | `/sesiones/:id/participantes` | ✅ | SPEC-004 | Héctor |
| Mis cursos | `/cursos` | ✅ | SPEC-002 | Héctor |
| Un curso: matricular por correo | `/cursos/:id` | ✅ | SPEC-002 | Héctor |
| Importar QTI | — | ❌ | SPEC-003 | Pierreluiggi |
| **Revisión de un caso y decisión con justificación** | `/sesiones/:id/estudiantes/:id` | ✅ | SPEC-009 | Héctor |
| Resultados y notas | — | ❌ | SPEC-003 | Héctor |
| Galería de capturas | — | ❌ | SPEC-007 | Jesús |
| Monitoreo en vivo por cámara | — | ❌ | SPEC-007 | Jesús |

## Estudiante (web dentro de la app de escritorio)

| Pantalla | Ruta | Estado | SPEC | Responsable |
|---|---|---|---|---|
| Entrar | `/login` | ✅ | SPEC-001 | Héctor |
| **Panel**: por rendir y entregados | `/estudiante` | ✅ | SPEC-004 | Héctor |
| Código de acceso | `/examen` | ✅ | SPEC-002 | Héctor |
| Consentimiento informado y espera | `/examen/:id/sala` | ✅ | SPEC-004 | Héctor |
| Rendir el examen y entregar | `/examen/:id/rendir` | ✅ | SPEC-004 | Héctor |
| Entregado | (dentro de `/rendir`) | ✅ | SPEC-004 | Héctor |
| **Verificación de identidad por rostro** | — | ❌ | SPEC-005 | Jesús |
| Aviso de supervisión en curso | — | ❌ | SPEC-006 | Rider |
| Revisión antes de entregar | — | ❌ | SPEC-004 | Héctor |

## App de escritorio (Electron)

| Capacidad | Estado | SPEC | Responsable |
|---|---|---|---|
| Ventana en kiosco con protección de contenido | ✅ | SPEC-006 | Rider |
| Carga el examen de la web en esa ventana | ✅ | SPEC-004 | Rider |
| Navegación atada al origen del examen | ✅ | SPEC-006 | Rider |
| Foco de ventana (`focus_lost`) | ✅ | SPEC-006 | Rider |
| Monitores adicionales (`extra_display`) | ✅ | SPEC-006 | Rider |
| Procesos sospechosos (`suspicious_process`) | ✅ | SPEC-006 | Rider |
| Envío de eventos a la API con reintentos | ✅ | SPEC-006 | Rider |
| Panel local de eventos (diagnóstico) | ✅ | — | Rider |
| Cámara y MediaPipe en el renderer | ❌ | SPEC-005/007 | Jesús |
| Detección de habla (Silero VAD) | ❌ | SPEC-008 | Pierreluiggi |
| Login del estudiante dentro de la app | ❌ | SPEC-001 | Rider |

La app **no reimplementa el examen**: carga la web. Así que las pantallas del
estudiante de la tabla anterior se ven dentro del kiosco sin escribirlas dos
veces. Lo que sí es propio de la app es lo que el navegador no puede ver.

## Navegación

Hay tres "capas", y cada pantalla pertenece a una:

| Capa | Quién | Qué tiene |
|---|---|---|
| **Pública** | Cualquiera | Portada y acceso. Cabecera con la marca y el botón de entrar. |
| **Panel** | Docente o estudiante con sesión | **Barra lateral** con lo que su rol puede hacer. El docente: Panel, Mis exámenes, Crear examen. El estudiante: Panel, Entrar a un examen. |
| **Examen** | Estudiante rindiendo | **Sin barra lateral ni un solo enlace.** Solo la marca y "Supervisión activa". Durante un examen supervisado no hay a dónde ir, y ofrecer enlaces sería ofrecer formas de abandonarlo por accidente. |

Quien inicia sesión llega a **su panel** (`/docente` o `/estudiante`), no a una pantalla suelta. La portada
es lo primero que ve quien no ha entrado; quien ya tiene sesión pasa de largo a su panel.

## Panel del estudiante

Muestra **mis clases** (con los exámenes que vienen en cada una), **por rendir** y **entregados** con su nota.

- **Mis clases:** estar en una clase **no da acceso a sus exámenes**. Para rendir uno sigue haciendo falta el código que reparte el docente; la clase solo dice cuándo es.
- **Notas:** se califican solas opción múltiple, verdadero o falso, numéricas y completar. **Los desarrollos no**: esa nota es del docente, y mientras tanto la nota se muestra como parcial ("5 de 10 · faltan desarrollos por calificar"). Que el docente pueda calificarlos a mano es lo que falta.

## Lo que falta en la API

| Endpoint | Para qué | SPEC |
|---|---|---|
| Capturas en la revisión de caso | La revisión muestra señales, alertas y riesgo. Falta la **evidencia visual**: `evidence_path` se guarda, pero no hay URL firmada de lectura para mostrarla. | SPEC-009 |
| Riesgo calibrado | El riesgo usa pesos razonados, **no medidos** (`domain/risk.py`). Calibrarlos con datos reales es lo que cumple la meta de accuracy ≥ 80 % y FPR < 20 %. | SPEC-009 |
| `GET /sessions/{id}/results` | Notas y respuestas, una vez haya calificación. | SPEC-003 |
| Que el docente califique los **desarrollos** a mano | Las demás preguntas se califican solas al entregar; los desarrollos quedan sin nota y la del estudiante, parcial. | SPEC-003 |
| `POST /sessions/{id}/questions/import` | Importar QTI. | SPEC-003 |

## La revisión de un caso

El docente abre el caso de un estudiante desde la sala de espera (**Revisar**) y ve, **antes de decidir**:

1. **Riesgo, con su desglose.** Cada punto sale de una señal concreta; un número sin origen no se puede discutir. Un mismo tipo de señal no pesa más de 50 puntos, para que cien salidas breves de la ventana no valgan como un acceso remoto.
2. **Línea de tiempo** de señales, con hora, detalle y duración.
3. **Su decisión**, con tres opciones igual de legítimas (confirmar, descartar, repetir el examen) y una **justificación obligatoria** de al menos 10 caracteres.

El sistema **no anula nada**: la decisión se registra, no se edita, y si el docente cambia de parecer registra otra; el historial queda. Hay una prueba que fija que decidir no cambia el examen del estudiante.

## Lo siguiente, por orden

1. **Decisión con justificación** (SPEC-009). Sin esto el sistema detecta y no
   resuelve nada, que es justo lo que lo distingue de un vigilante automático.
2. **Revisión de un caso** (SPEC-009). La decisión necesita una pantalla donde
   el docente vea la evidencia antes de decidir.
3. **Calificación** (SPEC-003). Hoy se guardan las respuestas pero no se
   corrigen; sin eso no hay nota que mostrar.
4. **Verificación facial** (SPEC-005). Desbloquea el estado `verified` sin que
   el docente tenga que admitir a todo el mundo a mano.
