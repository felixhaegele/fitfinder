-- Job queue for the measurement worker (ADR 0003).
--
-- Every new submission puts one message {"submission_id": "<uuid>"} on the pgmq queue
-- "submissions", in the same transaction as the insert: a submission can't exist
-- without its job, and a rolled-back insert leaves no job behind.
--
-- The message carries only the id; the worker loads the current row itself. Retries
-- come from pgmq's visibility timeout: a message the worker read but didn't delete or
-- archive becomes visible again. The worker gives up after 3 reads (read_ct), archives
-- the message and marks the submission 'failed' (#29).
--
-- The pgmq schema isn't exposed to anon/authenticated (no USAGE), so the queue is
-- reachable only from this trigger and from the worker's database connection.

create extension if not exists pgmq;

select pgmq.create('submissions');

-- security definer: the inserting user has no access to pgmq; the function runs as its
-- owner instead. search_path is pinned so it can't be hijacked.
create function public.enqueue_submission()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform pgmq.send('submissions', jsonb_build_object('submission_id', new.id));
  return new;
end;
$$;

-- Trigger functions can't be called directly, but keep it off the public API anyway.
revoke execute on function public.enqueue_submission() from public, anon, authenticated;

create trigger submissions_enqueue
  after insert on public.submissions
  for each row execute function public.enqueue_submission();
