# J5 — Auditoría RLS / SPEC-006

## Hallazgos en revisión estática (no pruebas reales)

1. La migración inicial contenía `decisions_student_select`, que permite al estudiante leer sus decisiones, contradictorio con el criterio de J5 de **0 filas**. La migración nueva elimina esa política.
2. `session_participants_student_update` permitía al estudiante modificar cualquier columna de su fila, incluidas `verification_status`, `score` y `submitted_at`. Se elimina la política: esos cambios se administran por la API.
3. `answers_student_insert/update` no impedían escribir columnas `is_correct` / `points_awarded` en la propia respuesta mediante PostgREST. La migración nueva revoca las escrituras a nivel tabla para `authenticated` y concede solo columnas de respuesta seguras. Revisar con el equipo antes de aplicar en Supabase.
4. La revisión estática NO demuestra el aislamiento del proyecto desplegado: se requiere ejecutar script de auditoría con dos estudiantes y registros existentes.

## Ejecución controlada

En un entorno de prueba autorizado, crear dos alumnos y una sesión con eventos y respuestas para cada uno, y una decisión docente. Obtener JWT del primer estudiante y usar solamente la clave publicable (no `service_role`). No guardarlos en el ZIP. Definir `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` y `AUDIT_STUDENT_JWT` localmente. Ejecutar desde la raíz:

```bash
python supabase/audits/audit_rls.py --student-id <UUID_1> --other-student-id <UUID_2> --other-participant-id <UUID_PARTICIPANTE_2> --session-id <UUID_SESION> --output supabase/audits/results/rls.json
```

Para la prueba de falsificación `INSERT`, añadir `--allow-write` **solo en un proyecto de pruebas**, nunca en producción. Revisar que los `GET` de `events`, `answers`, `question_options` y `decisions` no devuelvan datos no autorizados, que la escritura sea rechazada, y guardar el JSON de resultados. Si se encuentra una vulnerabilidad no cubierta, crear otra migración fechada; no cambiar SQL manualmente en el dashboard.

**Estado:** código de auditoría y migración preparados para revisión. Falta validación RLS real con JWT/fixtures, ejecución de migración aprobada y reporte de salida real.
