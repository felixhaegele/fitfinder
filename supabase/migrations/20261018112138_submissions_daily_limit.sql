-- At most 20 submissions per user in any 24 hours.
--
-- Protects against someone filling storage and the queue (each submission is one photo
-- and one job). Enforced in the database, so it holds even for clients that skip our UI.
-- The web app shows the error as "You've reached today's upload limit".
--
-- Counts existing rows, so deleting a submission frees up a slot. Good enough for v1.

create function public.enforce_submissions_daily_limit()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  daily_limit constant int := 20;
  recent int;
begin
  -- Serialize inserts per user, so two parallel uploads can't both slip in at 19.
  perform pg_advisory_xact_lock(hashtext('submissions_daily_limit:' || new.user_id::text));

  select count(*) into recent
  from public.submissions
  where user_id = new.user_id
    and created_at > now() - interval '24 hours';

  if recent >= daily_limit then
    raise exception 'submission limit reached: % per 24 hours', daily_limit
      using errcode = 'P0429', -- custom code the web app maps to a friendly message
            hint = 'Try again later.';
  end if;

  return new;
end;
$$;

revoke execute on function public.enforce_submissions_daily_limit() from public, anon, authenticated;

create trigger submissions_daily_limit
  before insert on public.submissions
  for each row execute function public.enforce_submissions_daily_limit();
