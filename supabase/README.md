# Base de datos — Supabase

Proyecto Supabase: **proctoring** (organización `taller1-proctoring`, región `sa-east-1`, São Paulo).

- URL: `https://uzuysjmymvtpoxfrdxnm.supabase.co`
- Project ref: `uzuysjmymvtpoxfrdxnm`
- Clave publicable (segura para el cliente): `sb_publishable_bSrgEQgpfk3cNZmU4vjAIg_e9FV7ATx`
- La **service role key** NO va en el repositorio: se copia del dashboard (Project Settings → API) al `.env` local y a GitHub Secrets.

## Migraciones (ya aplicadas en el proyecto)

| Archivo | Contenido |
|---|---|
| `20261003120000_initial_schema.sql` | 9 tipos enum y 15 tablas: `profiles`, `courses`, `course_enrollments`, `exam_sessions`, `session_modules`, `questions`, `question_options`, `session_participants`, `answers`, `reference_faces`, `events`, `audio_analyses`, `alerts`, `risk_scores`, `decisions`. Trigger que crea el perfil al registrarse. |
| `20261003120100_row_level_security.sql` | RLS en todas las tablas. El docente solo ve sus sesiones; el estudiante solo sus filas. Preguntas y opciones solo las lee el docente directamente (el estudiante las recibe por la API, sin respuestas correctas). |
| `20261003120200_realtime_and_storage.sql` | Realtime en `alerts` y `session_participants`. Buckets privados `evidences`, `audio-segments`, `reference-faces` (acceso con URLs firmadas). |
| `20261003120300_harden_signup_function.sql` | Todo registro nuevo es `student`; el rol `teacher` lo asigna un administrador. Nadie puede cambiarse el rol a sí mismo. |
| `20261006120000_question_banks.sql` | Bancos de preguntas por curso y docente (`question_banks`, `question_bank_items`, `session_question_banks`) y `questions.bank_id`. Un banco se reutiliza entre exámenes en vez de teclear las preguntas otra vez. |
| `20261007020000_exam_editing.sql` | `exam_sessions.max_score` (20 por defecto: la escala peruana) y `cancelled_at`. Un examen se cancela, no se borra: ya puede tener respuestas, y quien intente entrar tiene que oír que se canceló. |
| `20261009010000_harden_student_direct_rls.sql` | Cierra el acceso directo del estudiante a las tablas que debe leer solo por la API. |
| `20261009120000_restore_decisions_student_select.sql` | Devuelve al estudiante la lectura de **su** decisión: saber que su caso se resolvió no es información de otro.|
| `20261009180000_live_monitoring_channel.sql` | El canal privado de monitoreo en vivo. Dos funciones que leen el nombre del canal y dos políticas sobre `realtime.messages`: el fotograma lo publica solo el propio estudiante y lo recibe solo el docente dueño del examen. Nada se guarda. |

Convenciones: tablas y columnas en inglés y `snake_case`; `uuid` como llave; fechas `timestamptz` en UTC.

## Uso local

```bash
npx supabase link --project-ref uzuysjmymvtpoxfrdxnm
npx supabase db pull           # verificar que el remoto coincide
npx supabase gen types typescript --project-id uzuysjmymvtpoxfrdxnm > packages/contracts/database.types.ts
```

Para crear un docente de prueba: registrarse en Auth y luego, en el SQL Editor:
```sql
update public.profiles set role = 'teacher' where email = 'correo@upao.edu.pe';
```
