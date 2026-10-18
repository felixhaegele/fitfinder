-- submissions: users create, read and delete only their own; status is worker-only.
begin;
create extension if not exists pgtap with schema extensions;
select plan(15);

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000a', 'a@example.com'),
  ('00000000-0000-0000-0000-00000000000b', 'b@example.com');
insert into public.shoe_models (id, brand, model, year)
  values ('10000000-0000-0000-0000-000000000001', 'Testbrand', 'Alpha', 2023);

-- As user A
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000a", "role": "authenticated"}', true);

select lives_ok(
  $$insert into public.submissions (shoe_model_id, size, size_system, image_path, consent_at, insole_condition)
    values ('10000000-0000-0000-0000-000000000001', 43, 'eu',
            '00000000-0000-0000-0000-00000000000a/one.jpg', now(), 'new')$$,
  'a user can create a submission'
);
select results_eq(
  'select user_id, status from public.submissions',
  $$values ('00000000-0000-0000-0000-00000000000a'::uuid, 'queued'::text)$$,
  'new submissions belong to the user and start as queued'
);
select throws_ok(
  $$insert into public.submissions (shoe_model_id, size, size_system, image_path, consent_at, status, insole_condition)
    values ('10000000-0000-0000-0000-000000000001', 43, 'eu',
            '00000000-0000-0000-0000-00000000000a/two.jpg', now(), 'done', 'new')$$,
  '42501', null,
  'users cannot set the status'
);
select throws_ok(
  $$insert into public.submissions (user_id, shoe_model_id, size, size_system, image_path, consent_at, insole_condition)
    values ('00000000-0000-0000-0000-00000000000b', '10000000-0000-0000-0000-000000000001', 43, 'eu',
            '00000000-0000-0000-0000-00000000000b/two.jpg', now(), 'new')$$,
  '42501', null,
  'users cannot create submissions for someone else'
);
select throws_ok(
  $$insert into public.submissions (shoe_model_id, size, size_system, image_path, consent_at, insole_condition)
    values ('10000000-0000-0000-0000-000000000001', 43, 'eu',
            '00000000-0000-0000-0000-00000000000b/two.jpg', now(), 'new')$$,
  '23514', null,
  'image_path must be inside the user''s own folder'
);
select throws_ok(
  $$insert into public.submissions (shoe_model_id, size, size_system, image_path, insole_condition)
    values ('10000000-0000-0000-0000-000000000001', 43, 'eu',
            '00000000-0000-0000-0000-00000000000a/two.jpg', 'new')$$,
  '23502', null,
  'consent is required'
);
select throws_ok(
  $$insert into public.submissions (shoe_model_id, size, size_system, image_path, consent_at, insole_condition)
    values ('10000000-0000-0000-0000-000000000001', 43, 'eu',
            '00000000-0000-0000-0000-00000000000a/two.jpg', now(), 'worn out')$$,
  '23514', null,
  'insole condition must be new or used'
);
select throws_ok(
  $$insert into public.submissions (shoe_model_id, size, size_system, image_path, consent_at)
    values ('10000000-0000-0000-0000-000000000001', 43, 'eu',
            '00000000-0000-0000-0000-00000000000a/two.jpg', now())$$,
  '23502', null,
  'insole condition is required (no default)'
);
select throws_ok(
  $$update public.submissions set status = 'done'$$,
  '42501', null,
  'users cannot update submissions'
);

-- As user B
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000b", "role": "authenticated"}', true);

select is_empty('select id from public.submissions', 'users cannot see other users'' submissions');
delete from public.submissions;

-- As anon
set local role anon;
select set_config('request.jwt.claims', '{"role": "anon"}', true);

select is_empty('select id from public.submissions', 'anon sees no submissions');
select throws_ok(
  $$insert into public.submissions (shoe_model_id, size, size_system, image_path, consent_at, insole_condition)
    values ('10000000-0000-0000-0000-000000000001', 43, 'eu', 'x/one.jpg', now(), 'new')$$,
  '42501', null,
  'anon cannot create submissions'
);

-- As admin: B's delete above did nothing
reset role;
select is(
  (select count(*) from public.submissions)::int, 1,
  'users cannot delete other users'' submissions'
);

-- As user A: delete own
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000a", "role": "authenticated"}', true);
delete from public.submissions;
reset role;
select is_empty('select id from public.submissions', 'users can delete their own submissions');

-- Worker (service role bypasses RLS) can move status along; updated_at follows
insert into public.submissions (id, user_id, shoe_model_id, size, size_system, image_path, consent_at, updated_at, insole_condition)
  values ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-00000000000a',
          '10000000-0000-0000-0000-000000000001', 43, 'eu',
          '00000000-0000-0000-0000-00000000000a/three.jpg', now(), now() - interval '1 hour', 'new');
update public.submissions set status = 'processing' where id = '20000000-0000-0000-0000-000000000001';
select ok(
  (select updated_at > now() - interval '1 minute' from public.submissions
   where id = '20000000-0000-0000-0000-000000000001'),
  'updated_at is refreshed on update'
);

select * from finish();
rollback;
