-- submissions queue: one job per new submission, unreachable for users.
begin;
create extension if not exists pgtap with schema extensions;
select plan(6);

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000a', 'a@example.com');
insert into public.shoe_models (id, brand, model, year)
  values ('10000000-0000-0000-0000-000000000001', 'Testbrand', 'Alpha', 2023);

select is(
  (select count(*) from pgmq.q_submissions)::int, 0,
  'queue starts empty'
);

-- As user A
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000a", "role": "authenticated"}', true);

insert into public.submissions (shoe_model_id, size, size_system, image_path, consent_at)
  values ('10000000-0000-0000-0000-000000000001', 43, 'eu',
          '00000000-0000-0000-0000-00000000000a/one.jpg', now());

-- A rejected insert (no consent) must not leave a job behind; checked by the count below.
select throws_ok(
  $$insert into public.submissions (shoe_model_id, size, size_system, image_path)
    values ('10000000-0000-0000-0000-000000000001', 43, 'eu', '00000000-0000-0000-0000-00000000000a/two.jpg')$$,
  '23502', null,
  'an invalid submission is rejected'
);

select throws_ok(
  $$select pgmq.read('submissions', 30, 10)$$,
  '42501', null,
  'users cannot read the queue'
);
select throws_ok(
  $$select pgmq.send('submissions', '{"submission_id": "x"}'::jsonb)$$,
  '42501', null,
  'users cannot put jobs on the queue'
);

-- As admin
reset role;

select results_eq(
  $$select message from pgmq.q_submissions$$,
  $$select jsonb_build_object('submission_id', id) from public.submissions$$,
  'one job per valid submission, carrying its id'
);

-- The worker (database owner connection) can read the job
select results_eq(
  $$select (message->>'submission_id')::uuid from pgmq.read('submissions', 30, 1)$$,
  $$select id from public.submissions$$,
  'the worker can read the job'
);

select * from finish();
rollback;
