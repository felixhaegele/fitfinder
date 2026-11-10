-- Public insoles (#122, ADR 0014, which amends ADR 0011).
--
-- The shoe page lists every measured insole of a shoe, and anyone can download one insole's
-- outline as a 1:1 PDF to stand on. So, unlike the aggregates of ADR 0011, these functions
-- return one row per done submission. The owner decided (2026-11-10) that this is fine for
-- the shoe's data (size, measurements, labels, insole condition, side, outline): it
-- describes the shoe, not the person. Still never returned: user_id, image paths, dates,
-- rejection reasons or the submission id.
--
-- RLS on submissions, measurements and classifications is unchanged; anon still can't read
-- a single row of them. Same pattern as ADR 0011: security-definer functions with a fixed
-- column list, over the private "newest results" view.

-- ---------------------------------------------------------------------------
-- submissions.public_id: the id the public pages use for an insole
-- ---------------------------------------------------------------------------

-- Not the submission id: that one is the owner's (their status page is /submissions/<id>),
-- and keeping the two apart means a public link never names a private row. Not the
-- measurement id either: re-processing adds a new measurement, and the PDF link should
-- keep working. The column grants of the core schema migration mean users can't choose it.
--
-- volatile default + not null: Postgres fills existing rows with one value each.
alter table public.submissions
  add column public_id uuid not null default gen_random_uuid(),
  add constraint submissions_public_id_key unique (public_id);

-- ---------------------------------------------------------------------------
-- private.latest_fit_results: add the per-insole columns
-- ---------------------------------------------------------------------------

-- create or replace may only append columns, so the existing ones keep their order. The
-- view stays private (no rights for anon/authenticated) and security_invoker.
create or replace view private.latest_fit_results
with (security_invoker = true)
as
select
  s.shoe_model_id,
  s.size,
  s.size_system,
  m.length_mm,
  m.ball_width_mm,
  m.heel_width_mm,
  m.arch_width_mm,
  c.width_class,
  c.arch_class,
  c.toe_box_shape,
  c.toe_shape,
  s.public_id,
  s.insole_condition,
  m.side,
  m.outline_mm
from public.submissions s
join lateral (
  select m.id, m.length_mm, m.ball_width_mm, m.heel_width_mm, m.arch_width_mm, m.side, m.outline_mm
  from public.measurements m
  where m.submission_id = s.id
  order by m.created_at desc, m.id desc
  limit 1
) m on true
left join lateral (
  select c.width_class, c.arch_class, c.toe_box_shape, c.toe_shape
  from public.classifications c
  where c.measurement_id = m.id
  order by c.created_at desc, c.id desc
  limit 1
) c on true
where s.status = 'done';

-- ---------------------------------------------------------------------------
-- shoe_insoles: every measured insole of one shoe model, without outlines
-- ---------------------------------------------------------------------------

-- Ordered by size and length, not by upload date: the order mustn't reveal who uploaded
-- when. public_id breaks ties, and it's random.
create function public.shoe_insoles(shoe_model uuid)
returns table (
  insole_id uuid,
  size numeric,
  size_system text,
  insole_condition text,
  side text,
  length_mm numeric,
  ball_width_mm numeric,
  heel_width_mm numeric,
  arch_width_mm numeric,
  width_class text,
  arch_class text,
  toe_box_shape text,
  toe_shape text
)
language sql
stable
security definer
set search_path = ''
as $$
  select
    r.public_id,
    r.size,
    r.size_system,
    r.insole_condition,
    r.side,
    r.length_mm,
    r.ball_width_mm,
    r.heel_width_mm,
    r.arch_width_mm,
    r.width_class,
    r.arch_class,
    r.toe_box_shape,
    r.toe_shape
  from private.latest_fit_results r
  where r.shoe_model_id = shoe_model
  order by r.size_system, r.size, r.length_mm, r.public_id;
$$;

-- ---------------------------------------------------------------------------
-- shoe_insole: one insole with its shoe and outline, for the PDF
-- ---------------------------------------------------------------------------

create function public.shoe_insole(insole uuid)
returns table (
  insole_id uuid,
  shoe_model_id uuid,
  brand text,
  model text,
  year smallint,
  size numeric,
  size_system text,
  insole_condition text,
  side text,
  length_mm numeric,
  ball_width_mm numeric,
  heel_width_mm numeric,
  arch_width_mm numeric,
  width_class text,
  arch_class text,
  toe_box_shape text,
  toe_shape text,
  outline_mm jsonb
)
language sql
stable
security definer
set search_path = ''
as $$
  select
    r.public_id,
    sm.id,
    sm.brand,
    sm.model,
    sm.year,
    r.size,
    r.size_system,
    r.insole_condition,
    r.side,
    r.length_mm,
    r.ball_width_mm,
    r.heel_width_mm,
    r.arch_width_mm,
    r.width_class,
    r.arch_class,
    r.toe_box_shape,
    r.toe_shape,
    r.outline_mm
  from private.latest_fit_results r
  join public.shoe_models sm on sm.id = r.shoe_model_id
  where r.public_id = insole;
$$;

-- ---------------------------------------------------------------------------
-- Who may call them (same as ADR 0011: start from nothing, then the two API roles)
-- ---------------------------------------------------------------------------

revoke execute on function public.shoe_insoles(uuid) from public, anon, authenticated;
revoke execute on function public.shoe_insole(uuid) from public, anon, authenticated;
grant execute on function public.shoe_insoles(uuid) to anon, authenticated;
grant execute on function public.shoe_insole(uuid) to anon, authenticated;

comment on function public.shoe_insoles(uuid) is
  'Public list of the measured insoles of one shoe model (newest results of done '
  'submissions). Shoe data only: no user, image path, date or submission id (ADR 0014).';
comment on function public.shoe_insole(uuid) is
  'One public insole with its shoe and 1:1 outline, for the printable PDF. Shoe data only (ADR 0014).';
