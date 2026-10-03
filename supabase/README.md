# `supabase` — Base de datos, Auth, Storage y Realtime

**Responsable:** Limay Capristan, Jesús
**Backlog:** EN-006 / TA-00x (modelo de datos y migraciones)

## Objetivo

Las migraciones SQL del proyecto. **Todo en inglés y `snake_case`** — el docente lo pidió
explícitamente en la reunión del 03/10 ("la base de datos en inglés, todos los campos en inglés,
las tablas también en inglés, y utilizas también con guion bajo").

La API ya está escrita contra **exactamente** estos nombres de tabla y columna
([`CLAUDE.md`](../CLAUDE.md) §7). Si cambias un nombre, se rompe el adaptador de Supabase de la
API: avísale a Héctor en el mismo PR.

## Primer entregable

`migrations/0001_initial_schema.sql` con el modelo completo:

| Tabla | Notas |
|---|---|
| `profiles` | `id` = usuario de `auth.users`, `full_name`, `role` (`teacher` \| `student`) |
| `courses` | |
| `exam_sessions` | `teacher_id`, `title`, `starts_at`, `duration_minutes`, `access_code`, `preset`, `settings jsonb` |
| `session_modules` | qué módulos de detección se activan en esa sesión |
| `questions` | `session_id`, `statement`, `question_type`, `points`, `position` |
| `question_options` | |
| `session_participants` | `session_id`, `student_id`, `verification_status`, `consent_at` |
| `answers` | |
| `events` | `session_id`, `student_id`, `question_id`, `event_type`, `started_at`, `duration_ms`, `metadata`, `evidence_path` |
| `audio_analyses` | `event_id`, `transcript`, `similarity`, `synthetic_score` |
| `alerts` | `event_id`, `severity`, `reason` |
| `risk_scores` | riesgo desglosado **por señal**, no un solo número |
| `decisions` | `session_id`, `student_id`, `teacher_id`, `decision` (`confirmed` \| `dismissed` \| `retake`), `justification NOT NULL`, `decided_at` |
| `reference_faces` | rostro de referencia para la verificación de identidad |

Dos detalles de diseño que vienen de los requisitos, no son opcionales:

- `decisions.justification` es **`NOT NULL`**. El sistema es auditor, no juez: el docente decide y
  está obligado a justificar.
- `risk_scores` guarda el riesgo **desglosado por señal**. Un número único no sirve como evidencia.

## `event_type`

Usa el mismo conjunto que el contrato compartido
([`packages/contracts/event.schema.json`](../packages/contracts/event.schema.json)):

```sql
create type event_type as enum (
  'focus_lost', 'gaze_away', 'face_absent', 'extra_person', 'extra_display',
  'suspicious_process', 'screen_share', 'speech_detected', 'identity_check'
);
```

## Lo que hay que añadir además del DDL

1. **Índices** para las consultas reales: `events (session_id, student_id, started_at)`,
   `events (event_type)`, `answers (session_id, student_id)`.
2. **RLS activado en todas las tablas**, con políticas:
   - el estudiante ve y escribe solo sus propias filas;
   - el docente ve las filas de las sesiones que él creó;
   - nadie modifica ni borra `events` después de insertarlos (es evidencia: solo `insert` y `select`).
3. **Bucket de Storage** `evidences`, privado. Las subidas van con URL firmada que genera la API;
   nunca con la clave de servicio en el cliente.
4. **Realtime** habilitado en `alerts` (y en `events` si hace falta): así llegan las alertas en
   vivo al docente sin que la web pregunte cada segundo.

## Cómo trabajar en local

```bash
npx supabase init
```

```bash
npx supabase start && npx supabase db reset
```

Alternativa sin Docker: crea un proyecto gratuito de desarrollo en
[supabase.com](https://supabase.com/) y pega el SQL en el editor. Las credenciales van en tu `.env`
local (mira [`.env.example`](../.env.example)), **nunca** en el repositorio.

## Criterios de aceptación

- [ ] `0001_initial_schema.sql` corre de cero sin errores (`supabase db reset`).
- [ ] Todas las tablas y columnas en inglés y `snake_case`.
- [ ] Claves foráneas y `on delete` definidos; `decisions.justification` es `NOT NULL`.
- [ ] RLS activado en todas las tablas, con al menos las tres políticas de arriba.
- [ ] Un estudiante autenticado **no** puede leer eventos de otro (probado y documentado).
- [ ] Diagrama entidad-relación exportado a `docs/` o a la carpeta de evidencias.
- [ ] La API con `EVENT_REPOSITORY=supabase` inserta y lee de `events` (se prueba con Héctor).

## Evidencia para la semana

Captura del SQL corriendo limpio, del diagrama entidad-relación en inglés y de la prueba de RLS
fallando para un usuario ajeno. Guárdalo en `docs/evidencias/semana-05/jesus/`.
