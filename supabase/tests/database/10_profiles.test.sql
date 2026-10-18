-- profiles: created on sign-up, readable only by their owner, never written by users.
begin;
create extension if not exists pgtap with schema extensions;
select plan(6);

-- Two users. Inserting into auth.users fires the sign-up trigger.
insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000a', 'a@example.com'),
  ('00000000-0000-0000-0000-00000000000b', 'b@example.com');

select results_eq(
  'select id from public.profiles order by id',
  $$values ('00000000-0000-0000-0000-00000000000a'::uuid), ('00000000-0000-0000-0000-00000000000b'::uuid)$$,
  'sign-up creates a profile'
);

-- As user A
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000a", "role": "authenticated"}', true);

select results_eq(
  'select id from public.profiles',
  $$values ('00000000-0000-0000-0000-00000000000a'::uuid)$$,
  'a user sees only their own profile'
);

select throws_ok(
  $$insert into public.profiles (id) values ('00000000-0000-0000-0000-00000000000c')$$,
  '42501', null,
  'users cannot insert profiles'
);

-- As anon
set local role anon;
select set_config('request.jwt.claims', '{"role": "anon"}', true);

select is_empty('select id from public.profiles', 'anon sees no profiles');

-- As admin: deleting the auth user removes the profile
reset role;

delete from auth.users where id = '00000000-0000-0000-0000-00000000000a';
select is_empty(
  $$select id from public.profiles where id = '00000000-0000-0000-0000-00000000000a'$$,
  'deleting the auth user deletes the profile'
);
select isnt_empty(
  $$select id from public.profiles where id = '00000000-0000-0000-0000-00000000000b'$$,
  'other profiles are untouched'
);

select * from finish();
rollback;
