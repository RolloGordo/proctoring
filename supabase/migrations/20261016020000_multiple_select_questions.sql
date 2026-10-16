-- Preguntas con varias respuestas correctas (punto 9 de la revisión de HU-026).
--
-- Se añade un **tipo nuevo** en vez de dejar que `multiple_choice` admita
-- varias correctas. Cambiarle el significado al tipo que ya existe habría
-- cambiado en silencio cómo se califican los exámenes ya rendidos, y la nota de
-- alguien no se toca por una mejora de la interfaz.
--
-- `add value` sobre un enum no se puede revertir, así que va primero y solo si
-- falta: repetir la migración no debe romper.

do $$
begin
  if not exists (
    select 1
    from pg_enum e
    join pg_type t on t.oid = e.enumtypid
    where t.typname = 'question_type' and e.enumlabel = 'multiple_select'
  ) then
    alter type public.question_type add value 'multiple_select';
  end if;
end
$$;

-- Las respuestas elegidas, cuando son varias.
--
-- Columna aparte y no un cambio de `selected_option_id` a array: esa columna
-- tiene clave ajena a `question_options`, que es lo que impide guardar la
-- opción de otra pregunta, y un `uuid[]` no puede tener clave ajena. Mantener
-- las dos deja intacta esa garantía para los tipos de una sola respuesta, que
-- son la mayoría.
alter table public.answers
  add column if not exists selected_option_ids uuid[] not null default '{}';

-- Una respuesta usa una forma u otra, nunca las dos: si no, no se sabría cuál
-- califica.
alter table public.answers
  drop constraint if exists answers_one_selection_shape;
alter table public.answers
  add constraint answers_one_selection_shape
  check (selected_option_id is null or cardinality(selected_option_ids) = 0);

-- El estudiante escribe sus propias respuestas directamente contra la base
-- (ver `20261009010000_harden_student_direct_rls.sql`), así que la columna
-- nueva necesita el mismo permiso o guardar fallaría solo en producción.
grant update (selected_option_ids) on public.answers to authenticated;
grant insert (selected_option_ids) on public.answers to authenticated;
