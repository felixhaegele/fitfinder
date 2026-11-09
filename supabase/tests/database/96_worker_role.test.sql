-- worker role (#33): exactly what the worker needs, nothing more.
begin;
create extension if not exists pgtap with schema extensions;
select plan(26);

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000a', 'a@example.com');
insert into public.shoe_models (id, brand, model, year)
  values ('10000000-0000-0000-0000-000000000001', 'Testbrand', 'Alpha', 2023);
-- The insert trigger puts this submission's job on the queue.
insert into public.submissions (id, user_id, shoe_model_id, size, size_system, image_path, consent_at, insole_condition)
  values ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-00000000000a',
          '10000000-0000-0000-0000-000000000001', 43, 'eu',
          '00000000-0000-0000-0000-00000000000a/one.jpg', now(), 'new');
select pgmq.create('other_queue');

select results_eq(
  $$select rolsuper, rolbypassrls, rolcreaterole, rolcreatedb from pg_roles where rolname = 'worker'$$,
  $$values (false, false, false, false)$$,
  'worker is an ordinary role: no superuser, no RLS bypass, cannot create roles or databases'
);

-- The full list of the worker's rights. A new grant has to be added here on purpose.
select set_eq(
  $$
    select n.nspname || ' ' || a.privilege_type
    from pg_namespace n, aclexplode(n.nspacl) a
    where a.grantee = 'worker'::regrole
    union all
    select c.oid::regclass::text || ' ' || a.privilege_type
    from pg_class c, aclexplode(c.relacl) a
    where a.grantee = 'worker'::regrole
    union all
    select c.oid::regclass::text || '.' || att.attname || ' ' || a.privilege_type
    from pg_attribute att
    join pg_class c on c.oid = att.attrelid, aclexplode(att.attacl) a
    where a.grantee = 'worker'::regrole
  $$,
  $$
    values
      ('pgmq USAGE'),
      ('pgmq.q_submissions SELECT'), ('pgmq.q_submissions UPDATE'), ('pgmq.q_submissions DELETE'),
      ('pgmq.a_submissions INSERT'), ('pgmq.a_submissions.msg_id SELECT'),
      ('submissions.id SELECT'), ('submissions.user_id SELECT'),
      ('submissions.image_path SELECT'), ('submissions.status SELECT'),
      ('submissions.status UPDATE'), ('submissions.rejection_reason UPDATE'),
      ('submissions.processed_image_path UPDATE'),
      ('measurements INSERT'), ('measurements.id SELECT'),
      ('classifications INSERT')
  $$,
  'worker has exactly the expected grants'
);

set local role worker;

-- What store.py does
select is(
  (select (message->>'submission_id')::uuid from pgmq.read('submissions', 30, 1)),
  '20000000-0000-0000-0000-000000000001'::uuid,
  'worker reads the job'
);
select lives_ok(
  $$select pgmq.set_vt('submissions', (select msg_id from pgmq.q_submissions), 0)$$,
  'worker changes a message''s visibility'
);
select results_eq(
  $$select id, user_id, image_path, status from public.submissions$$,
  $$values ('20000000-0000-0000-0000-000000000001'::uuid, '00000000-0000-0000-0000-00000000000a'::uuid,
            '00000000-0000-0000-0000-00000000000a/one.jpg', 'queued')$$,
  'worker sees every user''s submission'
);
select lives_ok(
  $$select status from public.submissions where id = '20000000-0000-0000-0000-000000000001' for update$$,
  'worker locks a submission'
);
select lives_ok(
  $$update public.submissions set status = 'done', rejection_reason = null,
      processed_image_path = '00000000-0000-0000-0000-00000000000a/processed/one.jpg'
    where id = '20000000-0000-0000-0000-000000000001'$$,
  'worker sets the result columns'
);
select lives_ok(
  $$insert into public.measurements
    (id, submission_id, pipeline_version, length_mm, ball_width_mm, heel_width_mm, arch_width_mm, side, outline_mm)
    values ('30000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001',
            '1.0.0', 270, 98, 62, 74, 'left',
            (select jsonb_agg(jsonb_build_array(0, i)) from generate_series(0, 255) i))
    returning id$$,
  'worker inserts a measurement and reads back its id'
);
select lives_ok(
  $$insert into public.classifications (measurement_id, classifier_version, width_class, arch_class, toe_box_shape, toe_shape)
    values ('30000000-0000-0000-0000-000000000001', '1.0.0', 'regular', 'medium', 'round', 'roman')$$,
  'worker inserts a classification'
);
select ok(
  pgmq.archive('submissions', (select msg_id from pgmq.q_submissions)),
  'worker archives the job'
);

-- What it must not do: queue
select throws_ok(
  $$select pgmq.send('submissions', '{"submission_id": "x"}'::jsonb)$$,
  '42501', null, 'worker cannot put jobs on the queue'
);
select throws_ok(
  $$select pgmq.read('other_queue', 30, 1)$$,
  '42501', null, 'worker cannot read other queues'
);
select throws_ok(
  $$select * from pgmq.a_submissions$$,
  '42501', null, 'worker cannot read the archive'
);

-- submissions
select throws_ok(
  $$update public.submissions set image_path = '00000000-0000-0000-0000-00000000000a/other.jpg'$$,
  '42501', null, 'worker cannot change which photo a submission points to'
);
select throws_ok(
  $$update public.submissions set user_id = '00000000-0000-0000-0000-00000000000b'$$,
  '42501', null, 'worker cannot change who a submission belongs to'
);
select throws_ok(
  $$select consent_at from public.submissions$$,
  '42501', null, 'worker cannot read columns it doesn''t need'
);
select throws_ok(
  $$delete from public.submissions$$,
  '42501', null, 'worker cannot delete submissions'
);
select throws_ok(
  $$insert into public.submissions (shoe_model_id, size, size_system, image_path, consent_at, insole_condition)
    values ('10000000-0000-0000-0000-000000000001', 43, 'eu', 'x/y.jpg', now(), 'new')$$,
  '42501', null, 'worker cannot create submissions'
);

-- results
select throws_ok(
  $$select length_mm from public.measurements$$,
  '42501', null, 'worker cannot read measurements back'
);
select throws_ok(
  $$update public.measurements set length_mm = 1$$,
  '42501', null, 'worker cannot change measurements'
);
select throws_ok(
  $$delete from public.classifications$$,
  '42501', null, 'worker cannot delete classifications'
);

-- everything else
select throws_ok($$select * from public.profiles$$, '42501', null, 'worker cannot read profiles');
select throws_ok($$select * from public.shoe_models$$, '42501', null, 'worker cannot read shoe models');
select throws_ok($$select * from auth.users$$, '42501', null, 'worker cannot read auth users');
select throws_ok($$select * from storage.objects$$, '42501', null, 'worker cannot read storage');
select throws_ok($$select * from private.latest_fit_results$$, '42501', null, 'worker cannot read the private schema');

select * from finish();
rollback;
