-- 0001 initial schema: Sistema Proctoring (Taller Integrador 1, UPAO)
-- Tables and columns in English, snake_case.

-- ===== Enums =====
create type public.user_role as enum ('teacher', 'student');
create type public.session_status as enum ('draft', 'scheduled', 'in_progress', 'finished');
create type public.supervision_preset as enum ('basic', 'standard', 'strict', 'custom');
create type public.supervision_module as enum (
  'face_verification', 'face_reverification', 'focus_loss', 'copy_paste_block',
  'multi_monitor', 'gaze', 'extra_person', 'objects', 'external_voices',
  'ai_voice', 'live_monitoring', 'screen_capture'
);
create type public.question_type as enum ('multiple_choice', 'true_false', 'numeric', 'fill_blank', 'essay');
create type public.verification_status as enum ('pending', 'verified', 'failed', 'manually_approved', 'rejected');
create type public.event_type as enum (
  'focus_lost', 'gaze_away', 'face_absent', 'extra_person', 'extra_display',
  'suspicious_process', 'screen_share', 'speech_detected', 'identity_check'
);
create type public.alert_severity as enum ('low', 'medium', 'high');
create type public.decision_type as enum ('confirmed', 'dismissed', 'retake');

-- ===== Helper: updated_at =====
create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ===== Users =====
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  full_name text not null,
  email text unique,
  role public.user_role not null default 'student',
  student_code text unique,
  created_at timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, full_name, email, role)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.email),
    new.email,
    coalesce((new.raw_user_meta_data ->> 'role')::public.user_role, 'student')
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ===== Courses =====
create table public.courses (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  section text,
  teacher_id uuid not null references public.profiles (id) on delete restrict,
  created_at timestamptz not null default now()
);
create index courses_teacher_id_idx on public.courses (teacher_id);

create table public.course_enrollments (
  course_id uuid not null references public.courses (id) on delete cascade,
  student_id uuid not null references public.profiles (id) on delete cascade,
  enrolled_at timestamptz not null default now(),
  primary key (course_id, student_id)
);
create index course_enrollments_student_id_idx on public.course_enrollments (student_id);

-- ===== Exam sessions =====
create table public.exam_sessions (
  id uuid primary key default gen_random_uuid(),
  course_id uuid references public.courses (id) on delete set null,
  teacher_id uuid not null references public.profiles (id) on delete restrict,
  title text not null,
  description text,
  starts_at timestamptz not null,
  duration_minutes integer not null check (duration_minutes > 0),
  entry_tolerance_minutes integer not null default 10 check (entry_tolerance_minutes >= 0),
  access_code text not null unique,
  reveal_code_at_start boolean not null default false,
  preset public.supervision_preset not null default 'standard',
  max_attempts integer not null default 1 check (max_attempts > 0),
  shuffle_questions boolean not null default true,
  shuffle_options boolean not null default true,
  question_pool_size integer check (question_pool_size is null or question_pool_size > 0),
  allow_back_navigation boolean not null default true,
  show_answers_at timestamptz,
  status public.session_status not null default 'draft',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index exam_sessions_teacher_id_idx on public.exam_sessions (teacher_id);
create index exam_sessions_course_id_idx on public.exam_sessions (course_id);
create trigger exam_sessions_set_updated_at
  before update on public.exam_sessions
  for each row execute function public.set_updated_at();

-- Modules enabled per session, with their thresholds in settings
-- e.g. {"min_duration_ms": 5000} for focus_loss, {"yaw_degrees": 25, "min_duration_ms": 3000} for gaze.
create table public.session_modules (
  session_id uuid not null references public.exam_sessions (id) on delete cascade,
  module public.supervision_module not null,
  enabled boolean not null default true,
  settings jsonb not null default '{}'::jsonb,
  primary key (session_id, module)
);

-- ===== Questions =====
create table public.questions (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.exam_sessions (id) on delete cascade,
  position integer not null check (position > 0),
  question_type public.question_type not null,
  statement text not null,
  points numeric(5, 2) not null default 1 check (points >= 0),
  correct_numeric_answer numeric,
  numeric_tolerance numeric check (numeric_tolerance is null or numeric_tolerance >= 0),
  correct_text_answer text,
  source_format text,
  created_at timestamptz not null default now(),
  unique (session_id, position)
);

create table public.question_options (
  id uuid primary key default gen_random_uuid(),
  question_id uuid not null references public.questions (id) on delete cascade,
  position integer not null check (position > 0),
  option_text text not null,
  is_correct boolean not null default false,
  unique (question_id, position)
);

-- ===== Participation and answers =====
create table public.session_participants (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.exam_sessions (id) on delete cascade,
  student_id uuid not null references public.profiles (id) on delete cascade,
  attempt integer not null default 1 check (attempt > 0),
  verification_status public.verification_status not null default 'pending',
  verified_at timestamptz,
  verification_reviewed_by uuid references public.profiles (id),
  consent_at timestamptz,
  requested_in_person boolean not null default false,
  started_at timestamptz,
  submitted_at timestamptz,
  score numeric(6, 2),
  unique (session_id, student_id, attempt)
);
create index session_participants_student_id_idx on public.session_participants (student_id);

create table public.answers (
  id uuid primary key default gen_random_uuid(),
  participant_id uuid not null references public.session_participants (id) on delete cascade,
  question_id uuid not null references public.questions (id) on delete cascade,
  selected_option_id uuid references public.question_options (id) on delete set null,
  text_answer text,
  numeric_answer numeric,
  is_correct boolean,
  points_awarded numeric(5, 2),
  answered_at timestamptz not null default now(),
  unique (participant_id, question_id)
);
create index answers_question_id_idx on public.answers (question_id);
create index answers_selected_option_id_idx on public.answers (selected_option_id);

create table public.reference_faces (
  student_id uuid primary key references public.profiles (id) on delete cascade,
  storage_path text not null,
  embedding double precision[],
  model_version text,
  registered_at timestamptz not null default now()
);

-- ===== Proctoring events and analysis =====
create table public.events (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.exam_sessions (id) on delete cascade,
  student_id uuid not null references public.profiles (id) on delete cascade,
  question_id uuid references public.questions (id) on delete set null,
  event_type public.event_type not null,
  started_at timestamptz not null,
  duration_ms integer not null default 0 check (duration_ms >= 0),
  metadata jsonb not null default '{}'::jsonb,
  evidence_path text,
  created_at timestamptz not null default now()
);
create index events_session_student_started_idx on public.events (session_id, student_id, started_at);
create index events_student_id_idx on public.events (student_id);
create index events_question_id_idx on public.events (question_id);

create table public.audio_analyses (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null unique references public.events (id) on delete cascade,
  transcript text,
  similarity real check (similarity is null or (similarity >= 0 and similarity <= 1)),
  synthetic_voice_score real check (synthetic_voice_score is null or (synthetic_voice_score >= 0 and synthetic_voice_score <= 1)),
  matched_question_id uuid references public.questions (id) on delete set null,
  processing_ms integer check (processing_ms is null or processing_ms >= 0),
  model_versions jsonb not null default '{}'::jsonb,
  processed_at timestamptz not null default now()
);
create index audio_analyses_matched_question_id_idx on public.audio_analyses (matched_question_id);

create table public.alerts (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events (id) on delete cascade,
  session_id uuid not null references public.exam_sessions (id) on delete cascade,
  student_id uuid not null references public.profiles (id) on delete cascade,
  severity public.alert_severity not null,
  reason text not null,
  created_at timestamptz not null default now()
);
create index alerts_session_id_idx on public.alerts (session_id, created_at);
create index alerts_event_id_idx on public.alerts (event_id);
create index alerts_student_id_idx on public.alerts (student_id);

create table public.risk_scores (
  session_id uuid not null references public.exam_sessions (id) on delete cascade,
  student_id uuid not null references public.profiles (id) on delete cascade,
  score real not null check (score >= 0 and score <= 1),
  breakdown jsonb not null default '{}'::jsonb,
  computed_at timestamptz not null default now(),
  primary key (session_id, student_id)
);
create index risk_scores_student_id_idx on public.risk_scores (student_id);

create table public.decisions (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.exam_sessions (id) on delete cascade,
  student_id uuid not null references public.profiles (id) on delete cascade,
  teacher_id uuid not null references public.profiles (id) on delete restrict,
  decision public.decision_type not null,
  justification text not null check (char_length(btrim(justification)) >= 10),
  decided_at timestamptz not null default now()
);
create index decisions_session_student_idx on public.decisions (session_id, student_id, decided_at desc);
create index decisions_student_id_idx on public.decisions (student_id);
create index decisions_teacher_id_idx on public.decisions (teacher_id);
create index session_participants_reviewed_by_idx on public.session_participants (verification_reviewed_by);
