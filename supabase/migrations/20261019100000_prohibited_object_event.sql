-- El detector de objetos informa celulares como una señal revisable del examen.
alter type public.event_type add value if not exists 'prohibited_object';
