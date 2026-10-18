-- insoles bucket: private; users upload, read and delete only inside their own folder.
-- These test the policies on storage.objects directly, the same rows the Storage API
-- writes. (Size and MIME limits are enforced by the Storage API, not Postgres.)
begin;
create extension if not exists pgtap with schema extensions;
select plan(10);

-- The Storage API sets this before deleting; without it a trigger blocks direct deletes.
set local storage.allow_delete_query = 'true';

select results_eq(
  $$select public from storage.buckets where id = 'insoles'$$,
  $$values (false)$$,
  'the insoles bucket exists and is private'
);

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000a', 'a@example.com'),
  ('00000000-0000-0000-0000-00000000000b', 'b@example.com');

-- As user A
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000a", "role": "authenticated"}', true);

select lives_ok(
  $$insert into storage.objects (bucket_id, name) values ('insoles', '00000000-0000-0000-0000-00000000000a/one.jpg')$$,
  'a user can upload into their own folder'
);
select throws_ok(
  $$insert into storage.objects (bucket_id, name) values ('insoles', '00000000-0000-0000-0000-00000000000b/one.jpg')$$,
  '42501', null,
  'a user cannot upload into someone else''s folder'
);
select throws_ok(
  $$insert into storage.objects (bucket_id, name) values ('insoles', 'one.jpg')$$,
  '42501', null,
  'a user cannot upload outside any folder'
);
select is(
  (select count(*) from storage.objects where bucket_id = 'insoles')::int, 1,
  'a user sees their own photo'
);
update storage.objects set name = '00000000-0000-0000-0000-00000000000a/renamed.jpg'
  where name = '00000000-0000-0000-0000-00000000000a/one.jpg';
select is(
  (select count(*) from storage.objects where name = '00000000-0000-0000-0000-00000000000a/one.jpg')::int, 1,
  'a user cannot overwrite or rename a photo'
);

-- As user B
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000b", "role": "authenticated"}', true);

select is_empty(
  $$select id from storage.objects where bucket_id = 'insoles'$$,
  'other users cannot see the photo'
);
delete from storage.objects where bucket_id = 'insoles';

-- As anon
set local role anon;
select set_config('request.jwt.claims', '{"role": "anon"}', true);

select is_empty(
  $$select id from storage.objects where bucket_id = 'insoles'$$,
  'anon cannot see photos'
);

-- As user A again
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000a", "role": "authenticated"}', true);

select is(
  (select count(*) from storage.objects where bucket_id = 'insoles')::int, 1,
  'other users cannot delete the photo'
);
delete from storage.objects where bucket_id = 'insoles';
select is_empty(
  $$select id from storage.objects where bucket_id = 'insoles'$$,
  'a user can delete their own photo'
);

select * from finish();
rollback;
