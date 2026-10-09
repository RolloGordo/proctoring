-- SPEC-009 / HU-022: canal de monitoreo en vivo, sin grabar nada.
--
-- El docente ve la camara del estudiante mientras rinde. El fotograma viaja por
-- Realtime como mensaje de broadcast y se pierde: no pasa por la API, no entra
-- en Storage y no queda en ninguna tabla. Lo unico que se conserva al terminar
-- el examen son las capturas de los eventos que fueron alerta y los fragmentos
-- de audio marcados, que ya tienen su propio camino.
--
-- Eso no es un detalle de implementacion: es la promesa que la pantalla de
-- consentimiento le hace al estudiante. Un canal que guardara los fotogramas
-- seria grabacion continua de video con otro nombre.
--
-- El canal es **privado**, asi que Realtime comprueba RLS sobre
-- `realtime.messages` al unirse y al publicar. Hoy esa tabla tiene RLS activo y
-- cero politicas, o sea que nadie puede ni enviar ni recibir; esto es lo que lo
-- abre, y solo para quien corresponde. Ojo del otro lado: sin `private: true`
-- en el cliente el canal no es privado y RLS no se aplica en absoluto.

-- Un canal por estudiante: `monitoreo:<session_id>:<student_id>`.
--
-- Por estudiante y no por sesion a proposito. Con un canal por sesion, para
-- publicar su propio fotograma el estudiante tendria que poder unirse al canal
-- comun, y unirse implica poder recibir: veria la camara de sus companeros.
--
-- El nombre del canal lo escribe el cliente, asi que se comprueba la forma
-- antes de convertir a uuid. Sin el `~`, un topic cualquiera reventaria el cast
-- y el error de la politica llegaria al cliente como un fallo de conexion sin
-- explicacion.
create or replace function private.monitoring_topic_session() returns uuid
language sql stable
set search_path = ''
as $$
  select case
    when realtime.topic() ~ '^monitoreo:[0-9a-fA-F-]{36}:[0-9a-fA-F-]{36}$'
    then split_part(realtime.topic(), ':', 2)::uuid
  end
$$;

create or replace function private.monitoring_topic_student() returns uuid
language sql stable
set search_path = ''
as $$
  select case
    when realtime.topic() ~ '^monitoreo:[0-9a-fA-F-]{36}:[0-9a-fA-F-]{36}$'
    then split_part(realtime.topic(), ':', 3)::uuid
  end
$$;

comment on function private.monitoring_topic_session is
  'El examen que nombra el canal de monitoreo, o nulo si el nombre no tiene esa forma.';
comment on function private.monitoring_topic_student is
  'El estudiante que nombra el canal de monitoreo, o nulo si el nombre no tiene esa forma.';

-- Recibir: el docente dueno del examen, y el propio estudiante.
--
-- Que el estudiante reciba su propio canal no abre nada —es su camara— y hace
-- falta por dos motivos: para poder unirse al canal al que publica, y para
-- enterarse por presencia de que el docente esta mirando.
drop policy if exists monitoring_receive on realtime.messages;
create policy monitoring_receive on realtime.messages
  for select to authenticated
  using (
    private.monitoring_topic_session() is not null
    and realtime.messages.extension in ('broadcast', 'presence')
    and (
      private.is_session_teacher(private.monitoring_topic_session())
      or (
        -- Matriculado tambien aqui, no solo al publicar: si no, un estudiante
        -- podria unirse a un canal con su propio id y un examen cualquiera. No
        -- filtraria nada —ahi no puede publicar nadie— pero no tiene por que
        -- poder hacerse.
        private.monitoring_topic_student() = (select auth.uid())
        and private.is_session_participant(private.monitoring_topic_session())
      )
    )
  );

-- Publicar, separado por tipo de mensaje:
--
-- - **broadcast** (el fotograma): solo el propio estudiante, y solo si esta
--   matriculado en ese examen. Sin la primera condicion cualquiera publicaria
--   video en el canal de otro; sin la segunda, alguien ajeno al examen podria
--   inundar la pantalla del docente.
-- - **presence** (quien esta en el canal): tambien el docente. Es lo que le
--   permite anunciarse, y de eso depende que el estudiante empiece a enviar:
--   mientras nadie mira, el fotograma no sale del equipo del estudiante.
--
-- El `else false` cierra la puerta a cualquier otra extension que Realtime
-- anada mas adelante. Que un mecanismo nuevo quede denegado por defecto en un
-- canal que lleva la cara de alguien es exactamente lo que se quiere.
drop policy if exists monitoring_send on realtime.messages;
create policy monitoring_send on realtime.messages
  for insert to authenticated
  with check (
    private.monitoring_topic_session() is not null
    and case realtime.messages.extension
      when 'broadcast' then
        private.monitoring_topic_student() = (select auth.uid())
        and private.is_session_participant(private.monitoring_topic_session())
      when 'presence' then
        private.is_session_teacher(private.monitoring_topic_session())
        or (
          private.monitoring_topic_student() = (select auth.uid())
          and private.is_session_participant(private.monitoring_topic_session())
        )
      else false
    end
  );
