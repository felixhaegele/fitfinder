-- Account deletion (#31, ADR 0005): deleting the auth user must remove every row that
-- belongs to them. The web app deletes the user through the Auth admin API; Postgres
-- foreign-key cascades do the rest. Storage objects are purged separately (Storage API).
begin;
create extension if not exists pgtap with schema extensions;
select plan(8);

-- Guard for future tables: any foreign key into the user-owned chain must cascade or
-- set null, otherwise deleting a user would fail (restrict / no action) or the table
-- would need its own cleanup step.
select is_empty(
  $$select c.conrelid::regclass::text || '.' || c.conname
    from pg_constraint c
    where c.contype = 'f'
      and c.confrelid in ('auth.users'::regclass, 'public.profiles'::regclass,
                          'public.submissions'::regclass, 'public.measurements'::regclass)
      and c.connamespace = 'public'::regnamespace
      and c.confdeltype not in ('c', 'n')$$,
  'every foreign key to user-owned rows cascades or sets null'
);

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000a', 'a@example.com'),
  ('00000000-0000-0000-0000-00000000000b', 'b@example.com');
insert into public.shoe_models (id, brand, model, year, created_by)
  values ('10000000-0000-0000-0000-000000000001', 'Testbrand', 'Alpha', 2023,
          '00000000-0000-0000-0000-00000000000a');
insert into public.submissions (id, user_id, shoe_model_id, size, size_system, image_path, consent_at, status, insole_condition)
  values
    ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-00000000000a',
     '10000000-0000-0000-0000-000000000001', 43, 'eu',
     '00000000-0000-0000-0000-00000000000a/one.jpg', now(), 'done', 'new'),
    ('20000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-00000000000b',
     '10000000-0000-0000-0000-000000000001', 42, 'eu',
     '00000000-0000-0000-0000-00000000000b/two.jpg', now(), 'done', 'new');
insert into public.measurements
  (id, submission_id, pipeline_version, length_mm, ball_width_mm, heel_width_mm, arch_width_mm)
  values
    ('30000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001',
     '1.0.0', 272.5, 98.2, 62.1, 74.0),
    ('30000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002',
     '1.0.0', 268.0, 97.0, 61.0, 73.0);
insert into public.classifications (measurement_id, classifier_version, width_class, arch_class, toe_box_shape)
  values
    ('30000000-0000-0000-0000-000000000001', '1.0.0', 'regular', 'medium', 'round'),
    ('30000000-0000-0000-0000-000000000002', '1.0.0', 'wide', 'low', 'square');

-- What auth.admin.deleteUser() does in the database (hard delete)
delete from auth.users where id = '00000000-0000-0000-0000-00000000000a';

select is_empty(
  $$select id from public.profiles where id = '00000000-0000-0000-0000-00000000000a'$$,
  'profile is deleted'
);
select is_empty(
  $$select id from public.submissions where user_id = '00000000-0000-0000-0000-00000000000a'$$,
  'submissions are deleted'
);
select is_empty(
  $$select id from public.measurements where id = '30000000-0000-0000-0000-000000000001'$$,
  'measurements are deleted'
);
select is_empty(
  $$select id from public.classifications where measurement_id = '30000000-0000-0000-0000-000000000001'$$,
  'classifications are deleted'
);
select is(
  (select created_by from public.shoe_models where id = '10000000-0000-0000-0000-000000000001'),
  null,
  'shoe models they added stay in the catalogue, without the link to them'
);

-- Other users are untouched
select is(
  (select count(*) from public.submissions where user_id = '00000000-0000-0000-0000-00000000000b')::int,
  1,
  'other users keep their submissions'
);
select is(
  (select count(*) from public.classifications where measurement_id = '30000000-0000-0000-0000-000000000002')::int,
  1,
  'other users keep their results'
);

select * from finish();
rollback;
