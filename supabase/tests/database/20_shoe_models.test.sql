-- shoe_models: public catalogue; logged-in users can add, nobody can edit or delete.
begin;
create extension if not exists pgtap with schema extensions;
select plan(9);

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000a', 'a@example.com'),
  ('00000000-0000-0000-0000-00000000000b', 'b@example.com');
insert into public.shoe_models (id, brand, model, year)
  values ('10000000-0000-0000-0000-000000000001', 'Shimano', 'RC7', 2023);

-- As anon
set local role anon;
select set_config('request.jwt.claims', '{"role": "anon"}', true);

select isnt_empty('select id from public.shoe_models', 'anon can read the catalogue');
select throws_ok(
  $$insert into public.shoe_models (brand, model, year) values ('Sidi', 'Wire 2', 2022)$$,
  '42501', null,
  'anon cannot add shoe models'
);

-- As user A
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000a", "role": "authenticated"}', true);

select lives_ok(
  $$insert into public.shoe_models (brand, model, year) values ('Sidi', 'Wire 2', 2022)$$,
  'a logged-in user can add a shoe model'
);
select results_eq(
  $$select created_by from public.shoe_models where model = 'Wire 2'$$,
  $$values ('00000000-0000-0000-0000-00000000000a'::uuid)$$,
  'created_by is set to the current user'
);
select throws_ok(
  $$insert into public.shoe_models (brand, model, year, created_by)
    values ('Giro', 'Imperial', 2021, '00000000-0000-0000-0000-00000000000b')$$,
  '42501', null,
  'users cannot set created_by themselves'
);
select throws_ok(
  $$insert into public.shoe_models (brand, model, year) values (' shimano ', 'rc7', 2023)$$,
  '23505', null,
  'duplicates are rejected regardless of case and whitespace'
);
select throws_ok(
  $$update public.shoe_models set year = 2024 where model = 'RC7'$$,
  '42501', null,
  'users cannot edit shoe models'
);

delete from public.shoe_models where model = 'RC7';
reset role;
select isnt_empty(
  $$select id from public.shoe_models where model = 'RC7'$$,
  'users cannot delete shoe models'
);

-- Deleting the creator keeps the shoe model, just forgets who added it
delete from auth.users where id = '00000000-0000-0000-0000-00000000000a';
select results_eq(
  $$select created_by from public.shoe_models where model = 'Wire 2'$$,
  $$values (null::uuid)$$,
  'deleting the creator keeps the model with created_by = null'
);

select * from finish();
rollback;
