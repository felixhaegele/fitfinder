-- measurements + classifications: owners can read results of their own submissions;
-- only the worker (service role) writes them.
begin;
create extension if not exists pgtap with schema extensions;
select plan(9);

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000a', 'a@example.com'),
  ('00000000-0000-0000-0000-00000000000b', 'b@example.com');
insert into public.shoe_models (id, brand, model, year)
  values ('10000000-0000-0000-0000-000000000001', 'Testbrand', 'Alpha', 2023);
insert into public.submissions (id, user_id, shoe_model_id, size, size_system, image_path, consent_at, status, insole_condition)
  values ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-00000000000a',
          '10000000-0000-0000-0000-000000000001', 43, 'eu',
          '00000000-0000-0000-0000-00000000000a/one.jpg', now(), 'done', 'new');
insert into public.measurements
  (id, submission_id, pipeline_version, length_mm, ball_width_mm, heel_width_mm, arch_width_mm, toe_taper)
  values ('30000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001',
          '1.0.0', 272.5, 98.2, 62.1, 74.0, 0.4210);
insert into public.classifications (measurement_id, classifier_version, width_class, arch_class, toe_box_shape)
  values ('30000000-0000-0000-0000-000000000001', '1.0.0', 'regular', 'medium', 'round');

select throws_ok(
  $$insert into public.measurements
    (submission_id, pipeline_version, length_mm, ball_width_mm, heel_width_mm, arch_width_mm)
    values ('20000000-0000-0000-0000-000000000001', '1.0.0', 270, 98, 62, 74)$$,
  '23505', null,
  'one measurement per submission and pipeline version'
);

-- As user A (owner)
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000a", "role": "authenticated"}', true);

select is((select count(*) from public.measurements)::int, 1, 'owner sees their measurement');
select is((select count(*) from public.classifications)::int, 1, 'owner sees their classification');
select throws_ok(
  $$insert into public.measurements
    (submission_id, pipeline_version, length_mm, ball_width_mm, heel_width_mm, arch_width_mm)
    values ('20000000-0000-0000-0000-000000000001', '9.9.9', 1, 1, 1, 1)$$,
  '42501', null,
  'users cannot write measurements'
);
select throws_ok(
  $$insert into public.classifications (measurement_id, classifier_version, width_class, arch_class, toe_box_shape)
    values ('30000000-0000-0000-0000-000000000001', '9.9.9', 'wide', 'high', 'square')$$,
  '42501', null,
  'users cannot write classifications'
);

-- As user B
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000b", "role": "authenticated"}', true);

select is_empty('select id from public.measurements', 'other users cannot see measurements');
select is_empty('select id from public.classifications', 'other users cannot see classifications');

-- As anon
set local role anon;
select set_config('request.jwt.claims', '{"role": "anon"}', true);

select is_empty('select id from public.measurements', 'anon cannot see measurements');

-- As admin: deleting the submission removes its results
reset role;
delete from public.submissions where id = '20000000-0000-0000-0000-000000000001';
select is_empty('select id from public.classifications', 'deleting a submission deletes its results');

select * from finish();
rollback;
