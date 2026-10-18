-- processed_image_path: the worker's cleaned copy. Users can't set it; it must sit in the
-- owner's processed/ folder.
begin;
create extension if not exists pgtap with schema extensions;
select plan(5);

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000a', 'a@example.com');
insert into public.shoe_models (id, brand, model, year)
  values ('10000000-0000-0000-0000-000000000001', 'Testbrand', 'Alpha', 2023);
insert into public.submissions
  (id, user_id, shoe_model_id, size, size_system, image_path, consent_at, insole_condition)
  values ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-00000000000a',
          '10000000-0000-0000-0000-000000000001', 43, 'eu',
          '00000000-0000-0000-0000-00000000000a/one.jpg', now(), 'new');

select is(
  (select processed_image_path from public.submissions),
  null,
  'a new submission has no processed photo yet'
);

-- As user A
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000a", "role": "authenticated"}', true);

select throws_ok(
  $$insert into public.submissions (shoe_model_id, size, size_system, image_path, consent_at, insole_condition, processed_image_path)
    values ('10000000-0000-0000-0000-000000000001', 43, 'eu', '00000000-0000-0000-0000-00000000000a/two.jpg',
            now(), 'new', '00000000-0000-0000-0000-00000000000a/processed/two.jpg')$$,
  '42501', null,
  'users cannot set the processed photo'
);

-- As the worker (service role / owner connection)
reset role;

select lives_ok(
  $$update public.submissions
    set processed_image_path = '00000000-0000-0000-0000-00000000000a/processed/20000000-0000-0000-0000-000000000001.jpg'
    where id = '20000000-0000-0000-0000-000000000001'$$,
  'the worker can record the processed photo'
);
select throws_ok(
  $$update public.submissions set processed_image_path = '00000000-0000-0000-0000-00000000000b/processed/x.jpg'$$,
  '23514', null,
  'the processed photo must be in the owner''s folder'
);
select throws_ok(
  $$update public.submissions set processed_image_path = '00000000-0000-0000-0000-00000000000a/x.jpg'$$,
  '23514', null,
  'the processed photo must be in the processed/ subfolder'
);

select * from finish();
rollback;
