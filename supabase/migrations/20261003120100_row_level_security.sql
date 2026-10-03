-- 0002 row level security
-- The API uses the service role (bypasses RLS) for privileged work:
-- serving questions without correct answers, writing analyses, alerts and risk scores.
-- These policies protect direct access from the web (teacher) and the desktop app (student).

create schema if not exists private;

create or replace function private.is_session_teacher(p_session_id uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.exam_sessions s
    where s.id = p_session_id and s.teacher_id = (select auth.uid())
  );
$$;

create or replace function private.is_session_participant(p_session_id uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.session_participants p
    where p.session_id = p_session_id and p.student_id = (select auth.uid())
  );
$$;

create or replace function private.is_teacher()
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.profiles where id = (select auth.uid()) and role = 'teacher'
  );
$$;

grant usage on schema private to authenticated;
grant execute on all functions in schema private to authenticated;

alter table public.profiles enable row level security;
alter table public.courses enable row level security;
alter table public.course_enrollments enable row level security;
alter table public.exam_sessions enable row level security;
alter table public.session_modules enable row level security;
alter table public.questions enable row level security;
alter table public.question_options enable row level security;
alter table public.session_participants enable row level security;
alter table public.answers enable row level security;
alter table public.reference_faces enable row level security;
alter table public.events enable row level security;
alter table public.audio_analyses enable row level security;
alter table public.alerts enable row level security;
alter table public.risk_scores enable row level security;
alter table public.decisions enable row level security;

create policy profiles_select_own_or_teacher on public.profiles
  for select to authenticated
  using (id = (select auth.uid()) or (select private.is_teacher()));
create policy profiles_update_own on public.profiles
  for update to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));

create policy courses_teacher_all on public.courses
  for all to authenticated
  using (teacher_id = (select auth.uid())) with check (teacher_id = (select auth.uid()));
create policy courses_student_select on public.courses
  for select to authenticated
  using (exists (select 1 from public.course_enrollments e
                 where e.course_id = courses.id and e.student_id = (select auth.uid())));

create policy course_enrollments_teacher_all on public.course_enrollments
  for all to authenticated
  using (exists (select 1 from public.courses c where c.id = course_id and c.teacher_id = (select auth.uid())))
  with check (exists (select 1 from public.courses c where c.id = course_id and c.teacher_id = (select auth.uid())));
create policy course_enrollments_student_select on public.course_enrollments
  for select to authenticated
  using (student_id = (select auth.uid()));

create policy exam_sessions_teacher_all on public.exam_sessions
  for all to authenticated
  using (teacher_id = (select auth.uid())) with check (teacher_id = (select auth.uid()));
create policy exam_sessions_participant_select on public.exam_sessions
  for select to authenticated
  using ((select private.is_session_participant(id)));

create policy session_modules_teacher_all on public.session_modules
  for all to authenticated
  using ((select private.is_session_teacher(session_id)))
  with check ((select private.is_session_teacher(session_id)));
create policy session_modules_participant_select on public.session_modules
  for select to authenticated
  using ((select private.is_session_participant(session_id)));

create policy questions_teacher_all on public.questions
  for all to authenticated
  using ((select private.is_session_teacher(session_id)))
  with check ((select private.is_session_teacher(session_id)));
create policy question_options_teacher_all on public.question_options
  for all to authenticated
  using (exists (select 1 from public.questions q
                 where q.id = question_id and (select private.is_session_teacher(q.session_id))))
  with check (exists (select 1 from public.questions q
                      where q.id = question_id and (select private.is_session_teacher(q.session_id))));

create policy session_participants_teacher_all on public.session_participants
  for all to authenticated
  using ((select private.is_session_teacher(session_id)))
  with check ((select private.is_session_teacher(session_id)));
create policy session_participants_student_select on public.session_participants
  for select to authenticated
  using (student_id = (select auth.uid()));
create policy session_participants_student_update on public.session_participants
  for update to authenticated
  using (student_id = (select auth.uid())) with check (student_id = (select auth.uid()));

create policy answers_student_select on public.answers
  for select to authenticated
  using (exists (select 1 from public.session_participants p
                 where p.id = participant_id and p.student_id = (select auth.uid())));
create policy answers_student_insert on public.answers
  for insert to authenticated
  with check (exists (select 1 from public.session_participants p
                      where p.id = participant_id and p.student_id = (select auth.uid())
                        and p.submitted_at is null));
create policy answers_student_update on public.answers
  for update to authenticated
  using (exists (select 1 from public.session_participants p
                 where p.id = participant_id and p.student_id = (select auth.uid())
                   and p.submitted_at is null));
create policy answers_teacher_select on public.answers
  for select to authenticated
  using (exists (select 1 from public.session_participants p
                 where p.id = participant_id and (select private.is_session_teacher(p.session_id))));

create policy reference_faces_student_all on public.reference_faces
  for all to authenticated
  using (student_id = (select auth.uid())) with check (student_id = (select auth.uid()));

create policy events_student_insert on public.events
  for insert to authenticated
  with check (student_id = (select auth.uid()) and (select private.is_session_participant(session_id)));
create policy events_student_select on public.events
  for select to authenticated
  using (student_id = (select auth.uid()));
create policy events_teacher_select on public.events
  for select to authenticated
  using ((select private.is_session_teacher(session_id)));

create policy audio_analyses_teacher_select on public.audio_analyses
  for select to authenticated
  using (exists (select 1 from public.events e
                 where e.id = event_id and (select private.is_session_teacher(e.session_id))));
create policy alerts_teacher_select on public.alerts
  for select to authenticated
  using ((select private.is_session_teacher(session_id)));
create policy risk_scores_teacher_select on public.risk_scores
  for select to authenticated
  using ((select private.is_session_teacher(session_id)));

create policy decisions_teacher_select on public.decisions
  for select to authenticated
  using ((select private.is_session_teacher(session_id)));
create policy decisions_teacher_insert on public.decisions
  for insert to authenticated
  with check (teacher_id = (select auth.uid()) and (select private.is_session_teacher(session_id)));
create policy decisions_student_select on public.decisions
  for select to authenticated
  using (student_id = (select auth.uid()));
