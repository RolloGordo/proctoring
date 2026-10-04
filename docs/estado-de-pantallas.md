# Estado de las pantallas

Qué vistas existen hoy, cuáles faltan y de quién son. Contrastado con el
prototipo (`Prototipo_Sistema_Proctoring_v2`) y con los SPEC.

Última revisión: 3 de octubre de 2026, rama `feat/EN-002-exam-screens`.

## Docente (web)

| Pantalla | Ruta | Estado | SPEC | Responsable |
|---|---|---|---|---|
| Entrar | `/login` | ✅ | SPEC-001 | Héctor |
| Lista de exámenes | `/sesiones` | ✅ | SPEC-002 | Héctor |
| Crear examen | `/sesiones/nueva` | ✅ | SPEC-002 | Héctor |
| Examen en vivo (alertas y señales) | `/sesiones/:id` | ✅ | SPEC-009 | Héctor |
| Preguntas del examen | `/sesiones/:id/preguntas` | ✅ | SPEC-003 | Héctor |
| Sala de espera (admitir identidad) | `/sesiones/:id/participantes` | ✅ | SPEC-004 | Héctor |
| Importar QTI | — | ❌ | SPEC-003 | Pierreluiggi |
| Revisión de un caso (evidencia de un estudiante) | — | ❌ | SPEC-009 | Héctor |
| **Decisión con justificación** | — | ❌ | SPEC-009 | Héctor |
| Resultados y notas | — | ❌ | SPEC-003 | Héctor |
| Galería de capturas | — | ❌ | SPEC-007 | Jesús |
| Monitoreo en vivo por cámara | — | ❌ | SPEC-007 | Jesús |

## Estudiante (web dentro de la app de escritorio)

| Pantalla | Ruta | Estado | SPEC | Responsable |
|---|---|---|---|---|
| Entrar | `/login` | ✅ | SPEC-001 | Héctor |
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

## Lo que falta en la API

| Endpoint | Para qué | SPEC |
|---|---|---|
| `POST /sessions/{id}/decisions` | **La decisión del docente con justificación.** Es la promesa central del proyecto —auditor, no juez— y hoy la tabla `decisions` existe sin nadie que la escriba. | SPEC-009 |
| `GET /sessions/{id}/students/{id}/review` | La evidencia de un estudiante reunida: eventos, alertas, capturas, riesgo. | SPEC-009 |
| `GET /sessions/{id}/results` | Notas y respuestas, una vez haya calificación. | SPEC-003 |
| Calificación de respuestas | `answers.is_correct` y `points_awarded` se guardan vacíos: nadie califica todavía. | SPEC-003 |
| `POST /sessions/{id}/questions/import` | Importar QTI. | SPEC-003 |

## Lo siguiente, por orden

1. **Decisión con justificación** (SPEC-009). Sin esto el sistema detecta y no
   resuelve nada, que es justo lo que lo distingue de un vigilante automático.
2. **Revisión de un caso** (SPEC-009). La decisión necesita una pantalla donde
   el docente vea la evidencia antes de decidir.
3. **Calificación** (SPEC-003). Hoy se guardan las respuestas pero no se
   corrigen; sin eso no hay nota que mostrar.
4. **Verificación facial** (SPEC-005). Desbloquea el estado `verified` sin que
   el docente tenga que admitir a todo el mundo a mano.
