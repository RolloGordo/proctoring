-- Instructor-controlled review policy. Existing exams keep the safe default.
alter table public.exam_sessions
  add column if not exists show_answers_after_submission boolean not null default false;

-- Network availability is a technical diagnostic, not an infraction or risk event.
alter table public.supervision_diagnostics
  drop constraint supervision_diagnostics_code_check;

alter table public.supervision_diagnostics
  add constraint supervision_diagnostics_code_check check (code in (
    'camera_interrupted', 'camera_no_image', 'camera_recovered',
    'vision_module_failed', 'vision_module_recovered',
    'vision_module_summary', 'audio_segment_lost', 'image_evidence_lost',
    'signal_rejected', 'signal_queue_stuck',
    'network_disconnected', 'network_reconnected'
  ));
