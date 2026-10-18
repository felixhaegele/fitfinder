-- Condition of the insole in the photo: 'new' (never worn) or 'used' (has been worn).
--
-- Worn insoles compress and stretch, so measurements of used insoles may later be
-- flagged or weighted differently (#23, #24). Like consent_at there is no default:
-- the user must choose.
--
-- not null without a default only works because no hosted database has submissions
-- yet. Once production has data, a change like this needs a backfill step.

alter table public.submissions
  add column insole_condition text not null
    check (insole_condition in ('new', 'used'));

-- Users supply it on insert, alongside the columns granted in the core schema migration.
grant insert (insole_condition) on public.submissions to authenticated;
