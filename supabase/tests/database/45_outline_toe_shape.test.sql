-- measurements.side / outline_mm and classifications.toe_shape (#52): shape constraints,
-- and the existing RLS policies covering the new columns.
begin;
create extension if not exists pgtap with schema extensions;
select plan(22);

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000a', 'a@example.com'),
  ('00000000-0000-0000-0000-00000000000b', 'b@example.com');
insert into public.shoe_models (id, brand, model, year)
  values ('10000000-0000-0000-0000-000000000001', 'Testbrand', 'Alpha', 2023);
insert into public.submissions (id, user_id, shoe_model_id, size, size_system, image_path, consent_at, status, insole_condition)
  values ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-00000000000a',
          '10000000-0000-0000-0000-000000000001', 43, 'eu',
          '00000000-0000-0000-0000-00000000000a/one.jpg', now(), 'done', 'new');

-- Inserts a measurement with the given side and outline under a fresh pipeline version.
create function pg_temp.insert_measurement(p_side text, p_outline jsonb) returns void
language sql as $$
  insert into public.measurements
    (submission_id, pipeline_version, length_mm, ball_width_mm, heel_width_mm, arch_width_mm, side, outline_mm)
  values ('20000000-0000-0000-0000-000000000001', gen_random_uuid()::text, 270, 98, 62, 74, p_side, p_outline);
$$;

-- n points: the heel point at the origin, then a straight line up to the toe.
create function pg_temp.outline(n int) returns jsonb
language sql as $$
  select jsonb_agg(jsonb_build_array(0, i * 1.05) order by i) from generate_series(0, n - 1) i;
$$;

-- Columns
select col_not_null('public', 'measurements', 'side', 'side is required');
select col_not_null('public', 'measurements', 'outline_mm', 'outline_mm is required');
select col_type_is('public', 'measurements', 'outline_mm', 'jsonb', 'outline_mm is jsonb');
select col_not_null('public', 'classifications', 'toe_shape', 'toe_shape is required');

-- side
select lives_ok($$select pg_temp.insert_measurement('left', pg_temp.outline(256))$$, 'a left insole is accepted');
select lives_ok($$select pg_temp.insert_measurement('right', pg_temp.outline(256))$$, 'a right insole is accepted');
select throws_ok($$select pg_temp.insert_measurement('both', pg_temp.outline(256))$$, '23514', null,
  'side must be left or right');

-- outline_mm
select throws_ok($$select pg_temp.insert_measurement('left', pg_temp.outline(255))$$, '23514', null,
  'an outline with 255 points is rejected');
select throws_ok($$select pg_temp.insert_measurement('left', pg_temp.outline(257))$$, '23514', null,
  'an outline with 257 points is rejected');
select throws_ok($$select pg_temp.insert_measurement('left', '{"x": [0], "y": [0]}')$$, '23514', null,
  'an outline that is not an array is rejected');
select throws_ok(
  $$select pg_temp.insert_measurement('left', jsonb_set(pg_temp.outline(256), '{10}', '[1, 2, 3]'))$$,
  '23514', null,
  'a point with three coordinates is rejected');
select throws_ok(
  $$select pg_temp.insert_measurement('left', jsonb_set(pg_temp.outline(256), '{10}', '12.5'))$$,
  '23514', null,
  'a point that is a bare number is rejected');
select throws_ok(
  $$select pg_temp.insert_measurement('left', jsonb_set(pg_temp.outline(256), '{10}', '["1", 2]'))$$,
  '23514', null,
  'a coordinate that is a string is rejected');
select throws_ok(
  $$select pg_temp.insert_measurement('left', jsonb_set(pg_temp.outline(256), '{10}', '[null, 2]'))$$,
  '23514', null,
  'a null coordinate is rejected');
select throws_ok(
  $$select pg_temp.insert_measurement('left', jsonb_set(pg_temp.outline(256), '{0}', '[0, 3]'))$$,
  '23514', null,
  'an outline that does not start at the heel point (origin) is rejected');

-- toe_shape
insert into public.measurements
  (id, submission_id, pipeline_version, length_mm, ball_width_mm, heel_width_mm, arch_width_mm, side, outline_mm)
  values ('30000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001',
          '1.0.0', 272.5, 98.2, 62.1, 74.0, 'left', pg_temp.outline(256));

select lives_ok(
  $$insert into public.classifications (measurement_id, classifier_version, width_class, arch_class, toe_box_shape, toe_shape)
    values ('30000000-0000-0000-0000-000000000001', 'a', 'regular', 'medium', 'square', 'roman'),
           ('30000000-0000-0000-0000-000000000001', 'b', 'regular', 'medium', 'round', 'egyptian'),
           ('30000000-0000-0000-0000-000000000001', 'c', 'regular', 'medium', 'pointed', 'greek')$$,
  'egyptian, roman and greek are accepted');
select throws_ok(
  $$insert into public.classifications (measurement_id, classifier_version, width_class, arch_class, toe_box_shape, toe_shape)
    values ('30000000-0000-0000-0000-000000000001', 'd', 'regular', 'medium', 'round', 'germanic')$$,
  '23514', null,
  'toe_shape must be egyptian, roman or greek');
select throws_ok(
  $$insert into public.classifications (measurement_id, classifier_version, width_class, arch_class, toe_box_shape)
    values ('30000000-0000-0000-0000-000000000001', 'e', 'regular', 'medium', 'round')$$,
  '23502', null,
  'toe_shape cannot be left out');

-- RLS: the existing row policies cover the new columns
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000a", "role": "authenticated"}', true);

select is(
  (select jsonb_array_length(outline_mm) from public.measurements where id = '30000000-0000-0000-0000-000000000001'),
  256,
  'the owner can read the outline'
);
select is(
  (select toe_shape from public.classifications where classifier_version = 'c'),
  'greek',
  'the owner can read toe_shape'
);

set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-00000000000b", "role": "authenticated"}', true);

select is_empty('select outline_mm from public.measurements', 'other users cannot read outlines');
select is_empty('select toe_shape from public.classifications', 'other users cannot read toe_shape');

select * from finish();
rollback;
