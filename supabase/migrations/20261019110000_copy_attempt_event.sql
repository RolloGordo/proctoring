-- Registrar intentos de copiar bloqueados por el cliente de escritorio.
alter type public.event_type add value if not exists 'copy_attempt';
