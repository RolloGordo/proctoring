-- SEC-02 y SEC-10: el perfil no lo edita su dueño, y un docente solo ve a sus
-- estudiantes.
--
-- SEC-02. `profiles_update_own` dejaba a cada usuario reescribir su fila. El
-- trigger `prevent_role_change` protegía el rol, pero no el correo, el nombre
-- ni el código. Con eso un estudiante podía:
--   * ponerse el nombre y el código de un compañero, y el docente lo veía así
--     en participantes, resultados y en la revisión de caso;
--   * quedarse con el correo de un compañero que aún no se registró (el correo
--     es único), y el registro de ese compañero fallaba en `handle_new_user`;
--   * hacer que «Matricular por correo» lo inscribiera a él en su lugar.
-- Ningún cliente edita perfiles: la web solo lee el propio y la API escribe con
-- la service role. El perfil sale del registro y lo cambia un administrador.
--
-- SEC-10. `profiles_select_own_or_teacher` dejaba a cualquier docente leer
-- todos los perfiles, con el correo de cada estudiante de la universidad.
-- Ahora ve el suyo y los de estudiantes matriculados en sus cursos o que
-- participan en sus exámenes.

drop policy if exists profiles_update_own on public.profiles;
revoke insert, update, delete, truncate on public.profiles from anon, authenticated;

create or replace function private.is_teacher_of_student(p_student_id uuid)
returns boolean
language sql
stable
security definer
set search_path to ''
as $$
  select exists (
      select 1
      from public.course_enrollments e
      join public.courses c on c.id = e.course_id
      where e.student_id = p_student_id
        and c.teacher_id = (select auth.uid())
    )
    or exists (
      select 1
      from public.session_participants p
      join public.exam_sessions s on s.id = p.session_id
      where p.student_id = p_student_id
        and s.teacher_id = (select auth.uid())
    );
$$;

revoke all on function private.is_teacher_of_student(uuid) from public;
grant execute on function private.is_teacher_of_student(uuid) to authenticated;

drop policy if exists profiles_select_own_or_teacher on public.profiles;

create policy profiles_select_own_or_own_students on public.profiles
  for select to authenticated
  using (id = (select auth.uid()) or private.is_teacher_of_student(id));
