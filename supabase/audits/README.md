# J5 — Auditoría RLS / SPEC-006

## Hallazgos en revisión estática (no pruebas reales)

1. La política `decisions_student_select` permite leer las decisiones propias. El equipo ha decidido **conservarla**: el estudiante puede consultar la justificación, pero las decisiones de otros estudiantes deben permanecer ocultas. La primera migración de endurecimiento la eliminó, y la migración correctiva posterior la restaura.
2. `session_participants_student_update` permitía al estudiante modificar cualquier columna de su fila, incluidas `verification_status`, `score` y `submitted_at`. Se elimina la política: esos cambios se administran por la API.
3. `answers_student_insert/update` no impedían escribir columnas `is_correct` / `points_awarded` en la propia respuesta mediante PostgREST. La migración nueva revoca las escrituras a nivel tabla para `authenticated` y concede solo columnas de respuesta seguras. Revisar con el equipo antes de aplicar en Supabase.
4. La revisión estática NO demuestra el aislamiento del proyecto desplegado: se requiere ejecutar script de auditoría con dos estudiantes y registros existentes.

## Ejecución controlada

En un entorno de prueba autorizado, crear dos alumnos y una sesión con eventos y respuestas para cada uno, y una decisión docente. Obtener JWT del primer estudiante y usar solamente la clave publicable (no `service_role`). No guardarlos en el ZIP. Definir `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` y `AUDIT_STUDENT_JWT` localmente. Ejecutar desde la raíz:

```bash
python supabase/audits/audit_rls.py --student-id <UUID_1> --other-student-id <UUID_2> --other-participant-id <UUID_PARTICIPANTE_2> --session-id <UUID_SESION> --output supabase/audits/results/rls.json
```

Para la prueba de falsificación `INSERT`, añadir `--allow-write` **solo en un proyecto de pruebas**, nunca en producción. Revisar que los `GET` de `events`, `answers`, `question_options` y las `decisions` de otros estudiantes no devuelvan datos no autorizados, que la escritura sea rechazada, y guardar el JSON de resultados. Si se encuentra una vulnerabilidad no cubierta, crear otra migración fechada; no cambiar SQL manualmente en el dashboard.

**Estado:** el compañero indicó que la primera migración RLS ya fue aplicada y comprobada en su entorno. La **migración restauradora de decisiones propias aún necesita aplicarse allí** y verificar su resultado con JWT/fixtures; este ZIP no ejecuta cambios remotos.

## Decisión de producto aprobada: lectura de la propia decisión

El equipo decidió **mantener `decisions_student_select`**, porque el alumno puede
consultar la justificación de una decisión relativa a él. La primera migración de
endurecimiento eliminaba esa política; como puede estar aplicada, **no se reescribe
la migración histórica**. Ejecutar, en orden, la nueva migración
`20261009120000_restore_decisions_student_select.sql` para restaurar únicamente
SELECT de decisiones propias. Se mantiene el bloqueo a escrituras directas sobre
`session_participants`, notas y `answers` sensibles. Las operaciones de aplicación
y migraciones en Supabase deben ejecutarse por el responsable del despliegue.

El script de auditoría ya comprueba **0 decisiones de otros estudiantes** en
lugar de exigir 0 decisiones en total. Se permite leer **las propias**.
