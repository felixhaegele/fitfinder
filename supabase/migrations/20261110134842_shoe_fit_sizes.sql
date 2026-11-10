-- Per-size fit of every shoe, for "find by model" (ADR 0014).
--
-- The page matches a foot (length + wiggle room, width) against insoles, which only works
-- per size: a shoe's median over all sizes says nothing about one size. shoe_fit_by_size
-- returns these rows for one shoe; this returns them for all shoes at once, with the shoe's
-- name. Every value here is already public on the /shoes/[id] pages, so the privacy
-- boundary of ADR 0011 doesn't move: shoe-level columns only, nothing per person.
--
-- Same rules as the other two: security definer, empty search_path, fully qualified names,
-- execute for anon and authenticated only.

create function public.shoe_fit_sizes()
returns table (
  shoe_model_id uuid,
  brand text,
  model text,
  year smallint,
  size numeric,
  size_system text,
  submission_count integer,
  median_length_mm numeric,
  median_ball_width_mm numeric,
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
    r.size,
    r.size_system,
    count(*)::integer,
    (percentile_cont(0.5) within group (order by r.length_mm))::numeric(6, 2),
    (percentile_cont(0.5) within group (order by r.ball_width_mm))::numeric(6, 2),
    mode() within group (order by r.width_class),
    mode() within group (order by r.arch_class),
    mode() within group (order by r.toe_box_shape),
    mode() within group (order by r.toe_shape)
  from private.latest_fit_results r
  join public.shoe_models sm on sm.id = r.shoe_model_id
  group by sm.id, r.size_system, r.size
  order by lower(sm.brand), lower(sm.model), sm.year desc, r.size_system, r.size;
$$;

revoke execute on function public.shoe_fit_sizes() from public, anon, authenticated;
grant execute on function public.shoe_fit_sizes() to anon, authenticated;

comment on function public.shoe_fit_sizes() is
  'Public fit summary of every shoe model per size and size system, for matching a foot '
  'to a size. Shoe-level data only (ADR 0011, ADR 0014).';
