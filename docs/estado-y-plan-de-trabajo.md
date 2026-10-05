# Estado del proyecto y plan de trabajo

**Corte:** 5 de octubre de 2026 (semana 6) · **Repositorio:** <https://github.com/RolloGordo/proctoring> · rama `develop`

Este documento está pensado para quien organiza las tareas del equipo **sin haber visto el código**. Dice
qué hay, qué falta, cómo se conectan las piezas y qué puede hacer cada integrante, con criterios de
aceptación medibles. Las horas son estimaciones y asumen **10 h por persona y semana**: ajústalas al
calendario real.

---

## 1. En una frase

Plataforma de **proctoring** para exámenes remotos que aloja sus propios exámenes, supervisa al estudiante
mientras los rinde y entrega al **docente** la evidencia y un riesgo desglosado. **Es un auditor, no un
juez:** nada anula un examen solo; decide el docente, con justificación escrita.

**El diferencial** es detectar la consulta a un asistente de IA **por voz**: se compara lo que el
estudiante dice en voz alta con el enunciado de la pregunta en curso **y** se detecta una segunda voz
sintética. **Solo hay alerta si se cumplen las dos condiciones**; leer la pregunta en voz alta para
concentrarse no debe alertar.

**Metas medibles (objetivo SMART):** 4 tipos de detección (identidad, foco de ventana, mirada, IA por voz)
con **accuracy ≥ 80 %** y **tasa de falsos positivos (FPR) < 20 %** por módulo · alerta de navegador o
cámara al docente en **< 5 s** · alerta de IA por voz en **< 10 s** · verificación facial **P90 < 500 ms** ·
despliegue con CI/CD hasta la semana 15.

---

## 2. Estado actual

**Cifras verificadas:** 65 commits · 21 pull requests · 7 jobs de CI en verde · **582 pruebas** (API 527,
IA 24, escritorio 19, web 12) · 28 endpoints de negocio · 15 pantallas web · 15 tablas con RLS · 10 ADR.

### Hecho y funcionando

| Área | Qué hay | Responsable |
|---|---|---|
| API principal (FastAPI, hexagonal) | Autenticación JWT, sesiones, preguntas de 5 tipos, matrícula con consentimiento, respuestas guardadas al responder, **calificación automática al entregar**, cursos, alertas en vivo (Realtime), **revisión de caso y decisión con justificación**, riesgo desglosado, URLs firmadas de subida de evidencia | Héctor |
| Seguridad | 6 vulnerabilidades corregidas, rate limiting, la respuesta correcta nunca llega al estudiante (lo impone el *tipo*), autorización por rol y por dueño en cada ruta. Ver `docs/auditoria-seguridad.md` | Héctor |
| Base de datos (Supabase) | 4 migraciones, 15 tablas, RLS, Realtime, 3 buckets privados | Héctor |
| Web (React + TS) | Portada, login, panel y barra lateral por rol, crear examen, preguntas, sala de espera con nombres, revisión de caso, cursos, rendir el examen (guarda al responder) | Héctor |
| App de escritorio (Electron) | Kiosco, protección de contenido (la ventana sale en negro en capturas), bloqueo de copiar/pegar, **`focus_lost`, `extra_display`, `suspicious_process`**, envío con reintentos, sesión de la web entregada al proceso principal | Rider |
| Transcripción en español | faster-whisper: WER 16,0 % (`small`, MediaSpeech) y 7,6 % (audios propios). Un fragmento de 10 s cuesta ~2,3 s | Pierreluiggi |
| CI/CD | 7 jobs, protección de `main`, escaneo de secretos | Héctor |

### Falta (ordenado por impacto en las metas)

| Falta | Meta que bloquea | Quién |
|---|---|---|
| **Verificación de identidad por rostro** (hoy el docente admite a todos a mano) | accuracy, P90 < 500 ms | Jesús + Héctor |
| **Detección de mirada, rostro ausente y persona adicional** | accuracy, FPR | Jesús |
| **Servicio de IA real**: hoy es un esqueleto (`services/ai/tasks.py`) | IA por voz, < 10 s | Pierreluiggi + Héctor |
| **Similitud con el enunciado** y **detector de voz sintética** | IA por voz | Pierreluiggi |
| **Medir** accuracy y FPR de cada módulo (hoy solo se midió WER) | **todas las metas** | todos |
| Permiso de cámara/micrófono dentro de Electron | desbloquea visión y voz | Rider |
| Capturas como evidencia visual en la revisión de caso | utilidad para el docente | Rider + Héctor |
| Calificación manual de desarrollos por el docente | notas completas | Héctor |
| Importación QTI | SPEC-003 | Pierreluiggi |
| Despliegue (Render, Vercel, Hugging Face Spaces, Upstash) | semana 15 | Héctor |

> **Lo más importante:** el proyecto tiene la infraestructura completa, pero de los **cuatro tipos de
> detección de la meta SMART solo existe uno** (foco de ventana, dentro de lo que detecta el escritorio).
> Faltan identidad, mirada e IA por voz, y **ninguno se ha medido todavía** contra accuracy y FPR. Lo que
> sigue es, casi todo, IA y medición.

---

## 3. Cómo se conectan las piezas

```
 ESTUDIANTE                                             DOCENTE
 ┌──────────────────────────────────────┐              ┌──────────────────┐
 │ App de escritorio (Electron)         │              │ Web (navegador)  │
 │  ├─ main:  foco, monitores, procesos │──┐           │  alertas en vivo │
 │  └─ renderer = la MISMA web del      │  │           │  revisión, nota  │
 │       examen (React)                 │  │           └────────▲─────────┘
 │       aquí corren MediaPipe y        │  │ POST /events        │ Supabase
 │       Silero VAD (cliente)           │  │ (JSON, con token)   │ Realtime
 └─────────────┬────────────────────────┘  │                     │ (tabla alerts)
               │ sube captura/audio        ▼                     │
               │ DIRECTO a Storage   ┌───────────────┐            │
               │ (URL firmada)       │ API (FastAPI) ├────────────┘
               ▼                     │ hexagonal     │  escribe events, alerts
        ┌─────────────┐              └──────┬────────┘
        │  Supabase   │◄────────────────────┤ encola trabajos (Redis + RQ)
        │ Postgres    │                     ▼
        │ Storage     │              ┌───────────────┐
        └─────────────┘◄─────────────┤ Servicio de IA│  faster-whisper, similitud,
                  lee audio/imagen   │ (worker RQ)   │  voz sintética, InsightFace
                                     └───────────────┘
```

**Reglas de flujo que no se rompen:**

- **Detección liviana en el cliente, lo pesado en el servidor.** No se envía video continuo: solo
  **eventos**, capturas puntuales y fragmentos de audio **con habla**.
- Los archivos **no pasan por la API**: se suben directo a Storage con una URL firmada
  (`POST /api/v1/evidence/upload-url`) y el evento lleva solo la ruta en `evidence_path`.
- **Un evento por condición, no uno por frame.** Cada detección con duración necesita un temporizador
  con histéresis y emite **un solo evento al cerrarse**, con `duration_ms`. Emitir por frame dispara los
  falsos positivos y rompe la meta de FPR.
- **La supervisión empieza al llegar a `/examen/:id/rendir`, no antes**: el consentimiento se da en
  `/sala`. Antes de eso la app no manda nada.

### Dónde se enchufa cada detector

| Detector | Dónde corre | Cómo reporta |
|---|---|---|
| `gaze_away`, `face_absent`, `extra_person` | **Navegador** (renderer, MediaPipe) | `POST /api/v1/events` con el token del estudiante |
| `speech_detected` (VAD) | **Navegador** (Silero VAD) | sube el fragmento a Storage y manda el evento con `evidence_path`; la API **encola** `tasks.analyze_audio` |
| Análisis de IA por voz | **Servicio de IA** (worker RQ) | escribe `audio_analyses` y, **solo con las dos condiciones**, la alerta |
| Identidad por rostro | **Servicio de IA** | actualiza el estado del participante y emite `identity_check` |
| Foco, monitores, procesos | Electron `main` | ya funciona |

El renderer **es la misma web**: lo que Jesús y Pierreluiggi escriban para el navegador corre idéntico
dentro de la app de escritorio. El navegador ya tiene el token del estudiante (`useAuth()`), así que puede
llamar a la API directamente.

---

## 4. Contratos que hay que respetar

### Evento (`packages/contracts/event.schema.json`, con un ejemplo por tipo en `examples/`)

```json
{ "session_id": "uuid", "student_id": "uuid", "question_id": "uuid | null",
  "event_type": "focus_lost | gaze_away | face_absent | extra_person | extra_display | suspicious_process | screen_share | speech_detected | identity_check",
  "started_at": "ISO-8601 UTC", "duration_ms": 0, "metadata": {}, "evidence_path": "ruta | null" }
```

- `question_id` es **obligatorio** para `speech_detected` y `gaze_away`.
- `student_id` debe coincidir con el del token; si no, la API responde 403.
- `metadata` esperada: `gaze_away` → `yaw_deg`, `pitch_deg`, `threshold_deg`, `min_duration_ms` ·
  `face_absent` → `faces_detected`, `min_duration_ms` · `extra_person` → `faces_detected` ·
  `speech_detected` → `sample_rate`, `speech_ratio` · `identity_check` → `result`, `similarity`,
  `threshold`, `latency_ms`. **Pon siempre `source`.** Los números guardados son lo que sostiene después el
  informe de accuracy y FPR.
- Tope: 8 KB y 50 claves de `metadata`.

### Umbrales ya definidos (`DEFAULT_MODULE_SETTINGS`, en `services/api/.../domain/exam_session.py`)

| Módulo | Umbral |
|---|---|
| `gaze` | `yaw_degrees: 25`, `min_duration_ms: 3000` |
| `extra_person` | `min_faces: 2` |
| `face_verification` | `similarity_threshold: 0.45` |
| `face_reverification` | `interval_minutes: 10` |
| `ai_voice` | `similarity_threshold: 0.6`, `synthetic_threshold: 0.5` |
| `external_voices` | `min_speakers: 2` |
| `focus_loss` | `min_duration_ms: 5000` |

**Son un punto de partida razonado, no un resultado medido.** El trabajo de visión y de IA es, en buena
parte, **calibrarlos con datos** hasta cumplir accuracy ≥ 80 % y FPR < 20 %. Si el dato dice otra cosa,
se cambia el número (vive en un solo sitio) y se documenta por qué.

### Severidad y riesgo (`domain/severity.py` y `domain/risk.py`)

`speech_detected` es **siempre baja**: por sí sola no significa nada. Solo el análisis del servicio de IA
puede escalarla. El riesgo suma puntos por señal (baja 1, media 8, alta 25), con tope de 50 por tipo de
señal. Los pesos también son razonados, no medidos.

---

## 5. Plan por persona

> Cada tarea trae **qué entrega**, **cómo se sabe que terminó** y **de qué depende**. Marcar `[desbloquea]`
> significa que otra persona está esperando.

### Jesús Limay — visión computacional y base de datos

**Hoy tiene 0 commits.** Su carpeta está preparada: `apps/web/spikes/vision/` (con README) y `supabase/`.
Su trabajo es casi todo **entrenar/calibrar y medir**, y es el que más rápido puede aportar.

| # | Tarea | Horas | Entrega y criterio de aceptación |
|---|---|---|---|
| J1 | **Dataset de visión** | 4 | 3 a 4 personas **del equipo, con consentimiento por escrito**, grabadas en condiciones distintas (luz buena y mala, con y sin lentes, mirando a otro lado, una segunda persona, foto de otra persona frente a la cámara, ausencia). Cada clip con etiqueta por segmento. Un `manifest.csv` y un `provenance.json` con **hashes SHA-256**, como el que ya hizo Pierreluiggi en `services/ai/datasets/`. **Los videos no se suben al repo.** |
| J2 | **Spike de MediaPipe** `[desbloquea medir]` | 6 | Página en `apps/web/spikes/vision` que abre la cámara y calcula **nº de rostros**, **yaw/pitch** de la cabeza y mirada. Emite eventos con la **forma del contrato** (en consola, sin enviarlos todavía) usando los umbrales de la tabla de arriba y **histéresis** (un evento al cerrar la condición). Un script de evaluación sobre J1 que escriba `results/*.json` con **accuracy y FPR por detector** (`gaze_away`, `face_absent`, `extra_person`). |

**Siguiente (semana 7):**

| # | Tarea | Horas | Entrega |
|---|---|---|---|
| J3 | **Verificación facial** con un modelo preentrenado (candidato: InsightFace/ArcFace) | 8 | Comparación de embeddings con pares reales/impostores del propio equipo. Curva **FAR/FRR**, umbral recomendado (hoy 0,45) y **latencia P90 < 500 ms en CPU**. Spike offline en `services/ai/spikes/` antes de integrarlo. |
| J4 | **Auditoría de RLS** | 4 | Un script que, usando la clave pública (no la de servicio), compruebe que un estudiante **no puede leer** eventos, respuestas ni evidencia de otro. Cualquier hallazgo va como **nueva migración** en `supabase/migrations/`, nunca editando el panel. |

**Cómo "entrenar" aquí (no hace falta entrenar desde cero):** MediaPipe y el modelo de rostros ya vienen
preentrenados. Lo que se hace es (a) convertir sus salidas (landmarks, pose de cabeza) en reglas con
umbral, (b) **calibrar** esos umbrales con J1, y (c) si la mirada sigue con muchos falsos positivos, probar
un clasificador pequeño (regresión logística o árbol) sobre características como yaw, pitch y posición del
iris, entrenado con los clips etiquetados. Comparar siempre contra la regla simple: si no mejora, no se usa.

### Pierreluiggi Zevallos — IA de audio

**Ya tiene:** transcripción con medición de WER y un dataset con procedencia. Falta lo que define al
proyecto.

| # | Tarea | Horas | Entrega y criterio de aceptación |
|---|---|---|---|
| P1 | **Similitud con el enunciado** | 4 | `spikes/similarity.py`. Un conjunto de **≥ 60 pares** etiquetados: (a) el estudiante **lee la pregunta en voz alta** → **no** debe alertar, (b) le **dicta la pregunta a un asistente**, (c) habla de otra cosa. Embeddings multilingües (candidato: `paraphrase-multilingual-MiniLM-L12-v2`). **Curva ROC**, umbral elegido (hoy 0,6) y el **FPR** a ese umbral. |
| P2 | **Detector de voz sintética** `[parte del diferencial]` | 6 | Dataset de **voz real vs. voz de TTS en español**: reales de Common Voice (es) y propias; sintéticas generadas con **al menos 3 motores distintos** (por ejemplo Piper, XTTS, edge-tts). Un clasificador base (candidato: embeddings de wav2vec2/XLS-R + regresión logística) y, para comparar, un modelo ya entrenado (candidato: AASIST) sin reentrenar. Reportar **EER, accuracy y FPR**, y **evaluar con un motor TTS que no se usó para entrenar**: es lo que dice si generaliza. |

**Siguiente (semana 7):**

| # | Tarea | Horas | Entrega |
|---|---|---|---|
| P3 | **Worker real `tasks.analyze_audio`** `[depende de H1]` | 8 | Descarga el audio de Storage, transcribe, calcula similitud, detecta voz sintética y devuelve el resultado a la API. **Alerta solo si se cumplen las dos condiciones**, con una prueba que lo fije (leer en voz alta no alerta). **Presupuesto total < 10 s**: la transcripción con `small` ya consume ~2,3 s de cada fragmento de 10 s, quedan ~7,7 s para el resto. |
| P4 | **Parser de importación QTI** | 6 | Función pura, con fixtures, que convierta un QTI a la estructura de `NewQuestion` (los 5 tipos). Héctor la expone como endpoint. Se puede hacer sin esperar a nadie. |
| P5 | **VAD en el navegador (Silero)** | 6 | Detecta habla y graba solo esos fragmentos. Depende de R1 (permiso de micrófono). |

**Escenario realista a medir en P2:** la voz de la IA sale por los parlantes del equipo y el micrófono la
capta **mezclada con la del estudiante**. Conviene grabar así, no solo audios limpios.

### Rider Rodriguez — escritorio y UI

**Ya tiene:** la app de escritorio completa. Faltan permisos, evidencia visual y la evidencia de sus
criterios de aceptación. Es también el dueño de la **UI** de `apps/web`.

| # | Tarea | Horas | Entrega y criterio de aceptación |
|---|---|---|---|
| R1 | **Permiso de cámara y micrófono en Electron** `[desbloquea a Jesús y Pierreluiggi]` | 3 | `session.setPermissionRequestHandler`: conceder `media` **solo al origen del examen** y denegar todo lo demás; CSP que permita los `wasm` de MediaPipe. Una prueba que compruebe que otro origen **no** recibe el permiso. |
| R2 | **Captura de evidencia en eventos de severidad alta** | 4 | Al detectar `suspicious_process`, `extra_display` o `screen_share`, captura la pantalla (`desktopCapturer`), la sube con la URL firmada y rellena `evidence_path`. **Solo cuando hay evento, nunca de forma continua** (regla del proyecto). Límite de tamaño y de frecuencia. |
| R3 | **Medir y documentar los criterios del README** | 3 | Video corto: Alt+Tab → `focus_lost`; segundo monitor → `extra_display` en **< 5 s**; abrir Zoom/AnyDesk → `suspicious_process` en **< 15 s**; captura de pantalla → ventana en negro. Marcar los 7 criterios de `apps/desktop/README.md`. (La evidencia va a Notion, no al repo.) |

**Sin IA, para cuando termine:** pantalla de **resultados y notas** del docente · UI de **calificación
manual de desarrollos** (necesita el endpoint de H4) · galería de capturas en la revisión de caso (necesita
H3) · revisión de accesibilidad y de móvil · instalador con `electron-builder` y publicación en GitHub
Releases.

### Héctor Silva — arquitectura, API, infraestructura

| # | Tarea | Horas | Entrega y criterio de aceptación |
|---|---|---|---|
| H1 | **Contrato del trabajo de IA** `[desbloquea a Pierreluiggi]` | 3 | Endpoint **interno** (con secreto compartido, no con token de usuario) para que el worker escriba `audio_analyses` y pida crear la alerta. La **regla de alertar solo con las dos condiciones vive en la API** (dominio, con prueba), no en el worker. Documentar el payload del job `tasks.analyze_audio`. |
| H2 | **Verificación facial, lado API** `[desbloquea a Jesús]` | 3 | Registrar la cara de referencia (bucket `reference-faces`), encolar `verify_face`, y un caso de uso que aplique el resultado al participante (`verified` / `failed`) y emita `identity_check`. |
| H3 | **URLs firmadas de lectura de evidencia** | 2 | `GET` que devuelva la URL firmada de una evidencia, **solo al docente dueño de la sesión**. Mostrarla en la revisión de caso. |
| H4 | **Calificación manual de desarrollos** | 2 | Endpoint para que el docente ponga nota a un desarrollo; recalcula el puntaje y quita la marca "parcial". |

**Después:** despliegue (Render, Vercel, Hugging Face Spaces, Upstash) con CI/CD hasta la semana 15 ·
rate limit en Redis (hoy es por instancia) · registro de auditoría de accesos · persistir `risk_scores`.

---

## 6. Dependencias y orden recomendado

```
 H1 ───────────────► P3 (worker real)
 R1 ──┬────────────► J2 (cámara en Electron)   ┐
      └────────────► P5 (micrófono)            │  J2 y P1/P2 se pueden empezar YA
 J1 ──► J2 ──► medir accuracy/FPR de visión    │  en el navegador y sin servidor:
 P1, P2 ──► medir accuracy/FPR de voz          ┘  no esperan a nadie
 H2 ──► J3 (verificación facial integrada)
 H3 ──► R2 (evidencia visible) · H4 ──► UI de notas
```

**Se puede empezar hoy, sin esperar a nadie:** J1, J2 (en el navegador, sin Electron), P1, P2, P4, R3, H1.

**Orden sugerido de la semana 6:** primero lo que **desbloquea** (H1, R1), y en paralelo todo el trabajo
de **datos y medición** (J1, J2, P1, P2), porque es lo más largo y lo que más pesa en las metas.

---

## 7. Protocolo común de evaluación

Es lo que convierte "creo que funciona" en una cifra que se puede defender.

1. **Separar desde el principio un conjunto de prueba final** que **no se usa para calibrar** umbrales.
   Pierreluiggi ya marca sus resultados como `exploratory_not_final_test`: mantener ese rigor. Calibrar con
   una parte y reportar con otra.
2. **Reportar siempre accuracy y FPR**, y la **matriz de confusión**. La meta es por módulo:
   accuracy ≥ 80 % y FPR < 20 %.
3. **Medir en condiciones difíciles**, no solo en las buenas: poca luz, lentes, ruido de ventilador, voz de
   IA mezclada con la propia. Si solo se mide en lo fácil, el FPR real será mucho mayor.
4. **Cada resultado se guarda** en `results/*.json` con los parámetros, los hashes de los datos y el
   entorno (como ya hace `services/ai`). Una prueba debería **recalcular** la cifra desde lo guardado: así
   los números no se pueden desviar de su evidencia.
5. **Datos personales:** rostros y voces son datos sensibles. Solo personas del equipo, con
   **consentimiento escrito**, y **nunca al repositorio** (`.gitignore`). Se versionan solo manifiestos,
   procedencia y resultados.

---

## 8. Convenciones (de `CLAUDE.md`)

- Identificadores, endpoints, tablas y **commits en inglés**; la interfaz en español. Base de datos en
  `snake_case`.
- Ramas `feat/<codigo-backlog>-<descripcion>`; commits en *Conventional Commits* (`feat:`, `fix:`, `test:`,
  `docs:`); PR a `develop`; `main` solo por PR.
- **Definición de terminado:** PR a `develop`, **CI en verde**, una prueba que cubra el criterio de
  aceptación, README o docstring actualizado y evidencia (va a Notion).
- Cada integrante toca **solo su carpeta**. Quien sube una copia desactualizada de otra carpeta revierte sin
  querer el trabajo ajeno.
- Los umbrales **no se escriben fijos en el código de un detector**: se leen de la configuración del
  módulo, que viaja con la sesión.

---

## 9. Riesgos

| Riesgo | Por qué importa | Mitigación |
|---|---|---|
| **Falsos positivos de mirada** | Mirar al teclado o pensar mirando al techo no es trampa; es lo más difícil de medir bien | Histéresis de 3 s, medir en condiciones reales, comparar la regla simple contra un clasificador |
| **El detector de voz sintética no generaliza** | Si solo se entrena con un motor TTS, falla con otro | Evaluar con un motor no visto (P2) |
| **Presupuesto de 10 s** de la alerta de IA | La transcripción ya gasta ~2,3 s | Medir de punta a punta en P3, no por partes |
| **Latencia de verificación facial** en el plan gratuito | P90 < 500 ms en CPU compartida | Modelo pequeño, medir en el entorno real de despliegue |
| **Datos personales** en el repo | Rostros y voces son sensibles | `.gitignore`, solo manifiestos, consentimiento escrito |
| **Planes gratuitos** (Render duerme, HF Spaces con CPU limitada) | Afecta los tiempos de las metas | Probar el despliegue pronto, no en la semana 15 |

---

## 10. Cómo ver el sistema funcionando

Está en `docs/como-ver-los-avances.md`: cómo levantar la API, la web y la app de escritorio, el recorrido
completo de docente y estudiante, y cómo crear las dos cuentas de prueba.
