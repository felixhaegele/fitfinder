-- Public shoe fit summary (#92, ADR 0011).
--
-- Anyone, logged in or not, can see how shoes fit: per shoe model (and per size) the number
-- of measured insoles, median measurements and the most common classification labels.
--
-- The rows behind those numbers stay private. RLS on submissions, measurements and
-- classifications is unchanged: anon still can't read a single row. Instead, two
-- functions run with their owner's rights (security definer), aggregate, and return
-- shoe-level columns only. The owner decided to show a shoe from one submission, so
-- nothing per person may be returned: no user_id, image paths, dates or outlines.
--
-- Why a function and not a view: see ADR 0011.

-- ---------------------------------------------------------------------------
-- private schema: helpers the API must not serve
-- ---------------------------------------------------------------------------

-- PostgREST only serves the schemas listed in supabase/config.toml (public,
-- graphql_public), and anon/authenticated get no rights here. So objects in this schema
-- can only be reached through a function that is allowed to use them.
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

-- One row per done submission, using the newest measurement of the submission and the
-- newest classification of that measurement. Re-processing adds new versions next to the
-- old ones (ADR 0002); only the newest counts. "Newest" is by created_at, like the status
-- page, not by the version text ('1.10.0' sorts before '1.9.0').
--
-- A measured submission without a classification yet still counts; its labels are null.
--
-- security_invoker: whoever queries the view is checked against the tables' RLS. The
-- definer functions below query it as the owner, which RLS doesn't restrict; anyone
-- else only ever sees their own rows, even if this view were exposed by mistake.
create view private.latest_fit_results
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
  c.toe_shape
from public.submissions s
join lateral (
  select m.id, m.length_mm, m.ball_width_mm, m.heel_width_mm, m.arch_width_mm
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

revoke all on private.latest_fit_results from public, anon, authenticated;

-- ---------------------------------------------------------------------------
-- shoe_fit_summaries: one row per shoe model with at least one measured insole
-- ---------------------------------------------------------------------------

-- security definer: runs as the function owner, so it can read every done submission even
-- though the caller can't. That makes the output column list the privacy boundary:
-- shoe-level values only. supabase/tests/database/95_shoe_fit_summary.test.sql pins it.
--
-- search_path = '' and fully qualified names: a definer function must not resolve names
-- through a search_path the caller controls (they could put a fake "submissions" first).
--
-- search: every whitespace-separated word must appear in "brand model year",
-- case-insensitive, as plain text (strpos, so % and _ are not wildcards).
-- Medians are rounded to 0.01 mm, like the stored measurements. With a tie, mode() takes
-- the first label in alphabetical order.
create function public.shoe_fit_summaries(search text default null)
returns table (
  shoe_model_id uuid,
  brand text,
  model text,
  year smallint,
  submission_count integer,
  median_length_mm numeric,
  median_ball_width_mm numeric,
  median_heel_width_mm numeric,
  median_arch_width_mm numeric,
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
    sm.id,
    sm.brand,
    sm.model,
    sm.year,
    count(*)::integer,
    (percentile_cont(0.5) within group (order by r.length_mm))::numeric(6, 2),
    (percentile_cont(0.5) within group (order by r.ball_width_mm))::numeric(6, 2),
    (percentile_cont(0.5) within group (order by r.heel_width_mm))::numeric(6, 2),
    (percentile_cont(0.5) within group (order by r.arch_width_mm))::numeric(6, 2),
    mode() within group (order by r.width_class),
    mode() within group (order by r.arch_class),
    mode() within group (order by r.toe_box_shape),
    mode() within group (order by r.toe_shape)
  from private.latest_fit_results r
  join public.shoe_models sm on sm.id = r.shoe_model_id
  where not exists (
    select 1
    from regexp_split_to_table(lower(trim(coalesce(search, ''))), '\s+') as w (word)
    where w.word <> ''
      and strpos(lower(sm.brand || ' ' || sm.model || ' ' || sm.year), w.word) = 0
  )
  group by sm.id
  order by lower(sm.brand), lower(sm.model), sm.year desc;
$$;

-- ---------------------------------------------------------------------------
-- shoe_fit_by_size: the same numbers for one shoe model, per size and size system
-- ---------------------------------------------------------------------------

create function public.shoe_fit_by_size(shoe_model uuid)
returns table (
  size numeric,
  size_system text,
  submission_count integer,
  median_length_mm numeric,
  median_ball_width_mm numeric,
  median_heel_width_mm numeric,
  median_arch_width_mm numeric,
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
    r.size,
    r.size_system,
    count(*)::integer,
    (percentile_cont(0.5) within group (order by r.length_mm))::numeric(6, 2),
    (percentile_cont(0.5) within group (order by r.ball_width_mm))::numeric(6, 2),
    (percentile_cont(0.5) within group (order by r.heel_width_mm))::numeric(6, 2),
    (percentile_cont(0.5) within group (order by r.arch_width_mm))::numeric(6, 2),
    mode() within group (order by r.width_class),
    mode() within group (order by r.arch_class),
    mode() within group (order by r.toe_box_shape),
    mode() within group (order by r.toe_shape)
  from private.latest_fit_results r
  where r.shoe_model_id = shoe_model
  group by r.size_system, r.size
  order by r.size_system, r.size;
$$;

-- ---------------------------------------------------------------------------
-- Who may call them
-- ---------------------------------------------------------------------------

-- Postgres lets every role (PUBLIC) execute a new function, and Supabase's default
-- privileges add anon and authenticated. Start from nothing, then allow exactly the two
-- API roles. service_role keeps its default grant (it bypasses RLS anyway).
revoke execute on function public.shoe_fit_summaries(text) from public, anon, authenticated;
revoke execute on function public.shoe_fit_by_size(uuid) from public, anon, authenticated;
grant execute on function public.shoe_fit_summaries(text) to anon, authenticated;
grant execute on function public.shoe_fit_by_size(uuid) to anon, authenticated;

comment on function public.shoe_fit_summaries(text) is
  'Public fit summary per shoe model: measured-insole count, median mm and most common '
  'labels over done submissions (newest results only). Shoe-level data only (ADR 0011).';
comment on function public.shoe_fit_by_size(uuid) is
  'Public fit summary of one shoe model per size and size system. Shoe-level data only (ADR 0011).';
