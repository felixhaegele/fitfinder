-- submissions daily limit: 20 per user per 24 hours, counted per user.
begin;
create extension if not exists pgtap with schema extensions;
select plan(5);

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000a', 'a@example.com'),
  ('00000000-0000-0000-0000-00000000000b', 'b@example.com');
insert into public.shoe_models (id, brand, model, year)
  values ('10000000-0000-0000-0000-000000000001', 'Testbrand', 'Alpha', 2023);

-- User A already has 19 submissions today and one from two days ago
insert into public.submissions (user_id, shoe_model_id, size, size_system, image_path, consent_at, created_at, insole_condition)
select '00000000-0000-0000-0000-00000000000a', '10000000-0000-0000-0000-000000000001', 43, 'eu',
       '00000000-0000-0000-0000-00000000000a/' || i || '.jpg', now(),
       case when i = 0 then now() - interval '2 days' else now() - interval '1 hour' end,
       'new'
from generate_series(0, 19) as i;

-- As user A
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000a", "role": "authenticated"}', true);

select lives_ok(
  $$insert into public.submissions (shoe_model_id, size, size_system, image_path, consent_at, insole_condition)
    values ('10000000-0000-0000-0000-000000000001', 43, 'eu', '00000000-0000-0000-0000-00000000000a/20.jpg', now(), 'new')$$,
  'the 20th submission in 24 hours is allowed (older ones don''t count)'
);
select throws_ok(
  $$insert into public.submissions (shoe_model_id, size, size_system, image_path, consent_at, insole_condition)
    values ('10000000-0000-0000-0000-000000000001', 43, 'eu', '00000000-0000-0000-0000-00000000000a/21.jpg', now(), 'new')$$,
  'P0429', null,
  'the 21st submission in 24 hours is rejected with code P0429'
);

-- Deleting one frees a slot
delete from public.submissions where image_path = '00000000-0000-0000-0000-00000000000a/20.jpg';
select lives_ok(
  $$insert into public.submissions (shoe_model_id, size, size_system, image_path, consent_at, insole_condition)
    values ('10000000-0000-0000-0000-000000000001', 43, 'eu', '00000000-0000-0000-0000-00000000000a/22.jpg', now(), 'new')$$,
  'deleting a submission frees a slot'
);

-- As user B: A's limit doesn't affect B
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000b", "role": "authenticated"}', true);
select lives_ok(
  $$insert into public.submissions (shoe_model_id, size, size_system, image_path, consent_at, insole_condition)
    values ('10000000-0000-0000-0000-000000000001', 43, 'eu', '00000000-0000-0000-0000-00000000000b/1.jpg', now(), 'new')$$,
  'the limit is per user'
);

-- No job for the rejected submission (the trigger runs before insert)
reset role;
select is(
  (select count(*) from pgmq.q_submissions)::int,
  (select count(*) from public.submissions)::int + 1, -- +1: the job of the deleted submission stays
  'rejected submissions create no job'
);

select * from finish();
rollback;
