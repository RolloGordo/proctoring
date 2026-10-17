-- TA-083 / vision reliability: diagnostic records are NOT misconduct events.
-- They contain no photographs, embeddings, video or audio.
create table if not exists public.supervision_diagnostics (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.exam_sessions(id) on delete cascade,
  student_id uuid not null references public.profiles(id) on delete cascade,
  code text not null check (code in (
    'camera_interrupted', 'camera_no_image', 'camera_recovered',
    'vision_module_failed', 'vision_module_recovered',
    'vision_module_summary'
  )),
  module text,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists supervision_diagnostics_session_created_idx
  on public.supervision_diagnostics (session_id, created_at desc);
create index if not exists supervision_diagnostics_student_created_idx
  on public.supervision_diagnostics (student_id, created_at desc);
alter table public.supervision_diagnostics enable row level security;
revoke all on public.supervision_diagnostics from anon;
revoke all on public.supervision_diagnostics from authenticated;
grant select, insert on public.supervision_diagnostics to authenticated;

create policy student_inserts_own_diagnostic on public.supervision_diagnostics
  for insert to authenticated
  with check (
    student_id = (select auth.uid())
    and private.is_session_participant(session_id)
    and jsonb_typeof(details) = 'object'
    and length(details::text) <= 2048
  );
create policy student_reads_own_diagnostic on public.supervision_diagnostics
  for select to authenticated
  using (student_id = (select auth.uid()));
create policy teacher_reads_session_diagnostic on public.supervision_diagnostics
  for select to authenticated
  using (private.is_session_teacher(session_id));
-- No UPDATE or DELETE for authenticated users; service-role maintenance only.
comment on table public.supervision_diagnostics is
  'Technical availability log (not cheating accusations). No raw camera frames or secrets.';
