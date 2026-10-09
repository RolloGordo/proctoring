-- SPEC-006: cerrar accesos directos no contemplados para estudiantes.
-- La API usa service_role; los estudiantes deben usar endpoints validados.
-- Las decisiones del docente se consultan mediante la API, no directamente.
drop policy if exists decisions_student_select on public.decisions;

-- Evitar que el estudiante se otorgue la condición verified, modifique score,
-- submitted_at o campos de revisión mediante PATCH directo a PostgREST.
drop policy if exists session_participants_student_update on public.session_participants;

-- Un estudiante podría escribir is_correct/points_awarded de sus propias
-- respuestas: limitar el UPDATE a los campos de respuesta, si ese canal se usa.
-- Se revoca el UPDATE de tabla y se conceden únicamente columnas de respuesta;
-- el docente/servicio sigue trabajando con service_role (bypassa privilegios).
revoke update on public.answers from authenticated;
grant update (selected_option_id, text_answer, numeric_answer, answered_at)
  on public.answers to authenticated;

-- La inserción original de respuestas aún permite escribir is_correct/points_awarded
-- mediante PostgREST si el estudiante usa el rol authenticated. La API provee
-- escrituras seguras; restringir columna por columna también el INSERT.
revoke insert on public.answers from authenticated;
grant insert (participant_id, question_id, selected_option_id, text_answer, numeric_answer, answered_at)
  on public.answers to authenticated;
